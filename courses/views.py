import uuid

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Avg, Q
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods, require_POST

from accounts.access import (
    user_has_admin_access,
    user_has_teacher_access,
    user_is_student,
    user_is_teacher,
)
from ai_engine.models import AIJob, CourseGenerationRequest
from ai_engine.rate_limit import rate_limit
from analytics.security import record_audit_event
from assessments.forms import QuestionForm, RubricForm
from assessments.models import Appeal, Attempt, GradeDecision, Question, ReviewQueueItem, RubricVersion
from enrollments.models import CourseCompletion, Enrollment, LessonProgress
from enrollments.services import mark_lesson_complete
from organizations.models import Membership

from .forms import (
    ArtifactForm,
    CourseForm,
    CourseGenerationForm,
    FinalProjectForm,
    LessonFeedbackForm,
    LessonForm,
    ModuleForm,
    ProjectSubmissionForm,
)
from .models import Course, CourseVersion, FinalProject, LessonArtifact, LessonFeedback, LessonVersion, Module, ProjectSubmission
from .services import create_draft_version


def catalog(request):
    query = request.GET.get("q", "").strip()
    courses = Course.objects.filter(status=Course.Status.PUBLISHED).select_related("organization", "created_by")
    if query:
        courses = courses.filter(
            Q(title__icontains=query)
            | Q(description__icontains=query)
            | Q(organization__name__icontains=query)
        )
    return render(request, "courses/catalog.html", {"courses": courses, "query": query})


@login_required
def course_detail(request, slug):
    course = get_object_or_404(Course, slug=slug, status=Course.Status.PUBLISHED)
    version = course.versions.filter(status=CourseVersion.Status.PUBLISHED).first()
    enrollment = Enrollment.objects.filter(
        course=course,
        student=request.user,
        status=Enrollment.Status.ACTIVE,
    ).first()
    return render(request, "courses/detail.html", {"course": course, "version": version, "enrollment": enrollment})


@login_required
@require_POST
def enroll(request, slug):
    course = get_object_or_404(Course, slug=slug, status=Course.Status.PUBLISHED)
    version = course.versions.filter(status=CourseVersion.Status.PUBLISHED).order_by("-version_number").first()
    if version is None:
        raise Http404("No published course version is available for enrollment.")
    enrollment = Enrollment.objects.filter(course=course, student=request.user).first()
    if enrollment is None:
        Enrollment.objects.create(
            course=course,
            student=request.user,
            course_version=version,
        )
    elif enrollment.status != Enrollment.Status.ACTIVE:
        enrollment.status = Enrollment.Status.ACTIVE
        enrollment.course_version = version
        enrollment.completed_at = None
        enrollment.save(update_fields=["status", "course_version", "completed_at"])
    return redirect("courses:learn", slug=course.slug)


@login_required
@require_POST
def unenroll(request, slug):
    if not user_is_student(request.user):
        return HttpResponseForbidden("You do not have access to student enrollment actions.")
    enrollment = get_object_or_404(
        Enrollment.objects.select_related("course"),
        course__slug=slug,
        student=request.user,
        status=Enrollment.Status.ACTIVE,
    )
    enrollment.status = Enrollment.Status.WITHDRAWN
    enrollment.save(update_fields=["status"])
    record_audit_event(
        action="course_unenrolled",
        actor=request.user,
        obj=enrollment,
        request=request,
        metadata={"course_id": str(enrollment.course_id)},
    )
    messages.success(request, f"You have unenrolled from {enrollment.course.title}. Your progress has been saved.")
    return redirect("dashboard:student-dashboard")


@login_required
def learn(request, slug, lesson_id=None):
    course = get_object_or_404(Course, slug=slug, status=Course.Status.PUBLISHED)
    enrollment = get_object_or_404(
        Enrollment.objects.select_related("course_version"),
        course=course,
        student=request.user,
        status=Enrollment.Status.ACTIVE,
    )
    version = enrollment.course_version
    modules = list(version.modules.prefetch_related("lessons__questions", "lessons__artifacts").all())
    lessons = [lesson for module in modules for lesson in module.lessons.all()]
    if lesson_id:
        selected_lesson = next((lesson for lesson in lessons if lesson.id == lesson_id), None)
        if selected_lesson is None:
            raise Http404("This lesson does not belong to the enrolled course version.")
    else:
        selected_lesson = lessons[0] if lessons else None
    next_lesson = None
    if selected_lesson:
        selected_index = lessons.index(selected_lesson)
        if selected_index + 1 < len(lessons):
            next_lesson = lessons[selected_index + 1]
    progress = LessonProgress.objects.filter(enrollment=enrollment)
    attempts = Attempt.objects.filter(enrollment=enrollment, question__lesson_version__in=lessons).select_related(
        "ai_grade", "grade_decision"
    )
    progress_by_lesson = {item.lesson_version_id: item for item in progress}
    attempts_by_question = {attempt.question_id: attempt for attempt in attempts}
    for lesson in lessons:
        lesson.student_progress = progress_by_lesson.get(lesson.id)
        for question in lesson.questions.all():
            question.student_attempt = attempts_by_question.get(question.id)
        active_questions = [question for question in lesson.questions.all() if question.is_active]
        lesson.assessment_graded = bool(active_questions) and all(
            getattr(question.student_attempt, "ai_grade", None) for question in active_questions
        )
        lesson.is_completed = bool(
            lesson.student_progress and lesson.student_progress.status == LessonProgress.Status.COMPLETED
        ) or lesson.assessment_graded
    for module in modules:
        module_lessons = list(module.lessons.all())
        module.is_completed = bool(module_lessons) and all(lesson.is_completed for lesson in module_lessons)
    final_project = getattr(version, "final_project", None)
    project_submission = (
        ProjectSubmission.objects.filter(enrollment=enrollment, final_project=final_project).first()
        if final_project
        else None
    )
    lesson_feedback = (
        LessonFeedback.objects.filter(enrollment=enrollment, lesson_version=selected_lesson).first()
        if selected_lesson
        else None
    )
    course_completion = CourseCompletion.objects.filter(enrollment=enrollment).first()
    return render(
        request,
        "courses/learn.html",
        {
            "course": course,
            "enrollment": enrollment,
            "modules": modules,
            "final_project": final_project,
            "first_lesson": selected_lesson,
            "selected_lesson": selected_lesson,
            "next_lesson": next_lesson,
            "is_final_lesson": bool(selected_lesson and lessons and selected_lesson.id == lessons[-1].id),
            "course_completion": course_completion,
            "progress_by_lesson": progress_by_lesson,
            "attempts_by_question": attempts_by_question,
            "project_submission": project_submission,
            "project_submission_form": ProjectSubmissionForm(instance=project_submission),
            "lesson_feedback": lesson_feedback,
            "lesson_feedback_form": LessonFeedbackForm(instance=lesson_feedback),
        },
    )


@login_required
@require_POST
@rate_limit("lesson-feedback", limit=settings.AI_RATE_LIMIT_ATTEMPT, period=3600)
def submit_lesson_feedback(request, slug, lesson_id):
    course = get_object_or_404(Course, slug=slug, status=Course.Status.PUBLISHED)
    enrollment = get_object_or_404(
        Enrollment.objects.select_related("course_version"),
        course=course,
        student=request.user,
        status=Enrollment.Status.ACTIVE,
    )
    lesson = get_object_or_404(LessonVersion, id=lesson_id, module__course_version=enrollment.course_version)
    feedback = LessonFeedback.objects.filter(enrollment=enrollment, lesson_version=lesson).first()
    form = LessonFeedbackForm(request.POST, instance=feedback)
    if form.is_valid():
        feedback = form.save(commit=False)
        feedback.enrollment = enrollment
        feedback.lesson_version = lesson
        feedback.save()
        messages.success(request, "Thanks — your lesson feedback has been saved.")
    else:
        messages.error(request, "Choose a rating from 1 to 5 before sending feedback.")
    return redirect("courses:learn-lesson", slug=course.slug, lesson_id=lesson.id)


@login_required
@require_POST
@rate_limit("project-submission", limit=settings.AI_RATE_LIMIT_ATTEMPT, period=3600)
def submit_final_project(request, slug):
    course = get_object_or_404(Course, slug=slug, status=Course.Status.PUBLISHED)
    enrollment = get_object_or_404(
        Enrollment.objects.select_related("course_version"),
        course=course,
        student=request.user,
        status=Enrollment.Status.ACTIVE,
    )
    final_project = getattr(enrollment.course_version, "final_project", None)
    if final_project is None:
        raise Http404("This course does not have a final project.")
    submission = ProjectSubmission.objects.filter(enrollment=enrollment, final_project=final_project).first()
    if submission and submission.status != ProjectSubmission.Status.FAILED:
        messages.info(request, "Your final project is already submitted. Its review will appear here when ready.")
        return _redirect_to_final_lesson(course, enrollment)
    form = ProjectSubmissionForm(request.POST, instance=submission)
    if not form.is_valid():
        messages.error(request, "Add enough detail for AI to review your final project.")
        return _redirect_to_final_lesson(course, enrollment)
    with transaction.atomic():
        submission = form.save(commit=False)
        submission.enrollment = enrollment
        submission.final_project = final_project
        submission.status = ProjectSubmission.Status.SUBMITTED
        submission.suggested_score = None
        submission.confidence = None
        submission.strengths = []
        submission.errors = []
        submission.feedback = ""
        submission.remediation = ""
        submission.provider = ""
        submission.model = ""
        submission.reviewed_at = None
        submission.save()
        job = AIJob.objects.create(
            job_type=AIJob.JobType.PROJECT_GRADING,
            entity_type="project_submission",
            entity_id=submission.id,
            status=AIJob.Status.QUEUED,
        )
        record_audit_event(
            action="final_project_submitted",
            actor=request.user,
            obj=submission,
            request=request,
            metadata={"job_id": str(job.id), "final_project_id": str(final_project.id)},
        )
        transaction.on_commit(lambda: _enqueue_project_grading(job.id))
    messages.success(request, "Your final project was submitted for AI review. We will notify you when it is ready.")
    return _redirect_to_final_lesson(course, enrollment)


def _redirect_to_final_lesson(course, enrollment):
    final_lesson = LessonVersion.objects.filter(module__course_version=enrollment.course_version).order_by(
        "module__position", "position"
    ).last()
    if final_lesson:
        return redirect("courses:learn-lesson", slug=course.slug, lesson_id=final_lesson.id)
    return redirect("courses:learn", slug=course.slug)


def _enqueue_project_grading(job_id):
    from ai_engine.tasks import grade_project_submission

    try:
        if settings.CELERY_TASK_ALWAYS_EAGER:
            grade_project_submission.apply(args=[str(job_id)])
        else:
            grade_project_submission.delay(str(job_id))
    except Exception:
        import logging

        logging.getLogger(__name__).exception("Unable to enqueue final-project grading job %s", job_id)


@login_required
@require_POST
def mark_lesson_complete_view(request, slug, lesson_id):
    course = get_object_or_404(Course, slug=slug, status=Course.Status.PUBLISHED)
    enrollment = get_object_or_404(
        Enrollment.objects.select_related("course_version", "course"),
        course=course,
        student=request.user,
        status=Enrollment.Status.ACTIVE,
    )
    lesson = get_object_or_404(LessonVersion, id=lesson_id, module__course_version=enrollment.course_version)
    try:
        mark_lesson_complete(enrollment, lesson, actor=request.user)
    except ValidationError as error:
        messages.error(request, error.message)
    else:
        messages.success(request, "Lesson completed. Continue to the next lesson.")
    return redirect("courses:learn-lesson", slug=course.slug, lesson_id=lesson.id)


@login_required
def student_dashboard(request):
    if not user_is_student(request.user):
        return HttpResponseForbidden("You do not have access to the student dashboard.")
    enrollments = list(
        Enrollment.objects.filter(student=request.user, status=Enrollment.Status.ACTIVE).select_related("course", "course_version")
    )
    average_marks = {
        item["attempt__enrollment_id"]: item["average_mark"]
        for item in GradeDecision.objects.filter(attempt__enrollment__in=enrollments)
        .values("attempt__enrollment_id")
        .annotate(average_mark=Avg("final_score"))
    }
    overall_average_mark = GradeDecision.objects.filter(attempt__enrollment__in=enrollments).aggregate(
        average_mark=Avg("final_score")
    )["average_mark"]
    for enrollment in enrollments:
        enrollment.progress_count = enrollment.lesson_progress.filter(status=LessonProgress.Status.COMPLETED).count()
        enrollment.lesson_count = LessonVersion.objects.filter(module__course_version=enrollment.course_version).count()
        enrollment.progress_percentage = round((enrollment.progress_count / enrollment.lesson_count) * 100) if enrollment.lesson_count else 0
        average_mark = average_marks.get(enrollment.id)
        enrollment.average_mark = round(float(average_mark)) if average_mark is not None else None
    return render(
        request,
        "courses/student_dashboard.html",
        {
            "enrollments": enrollments,
            "overall_average_mark": round(float(overall_average_mark)) if overall_average_mark is not None else None,
        },
    )


@login_required
def teacher_dashboard(request):
    if not user_is_teacher(request.user):
        return HttpResponseForbidden("You do not have access to the teacher dashboard.")
    courses = Course.objects.filter(created_by=request.user).select_related("organization").order_by("-updated_at")
    review_count = ReviewQueueItem.objects.filter(status=ReviewQueueItem.Status.OPEN, assigned_to=request.user).count()
    appeal_count = Appeal.objects.filter(
        attempt__question__lesson_version__module__course_version__course__created_by=request.user,
        status=Appeal.Status.PENDING,
    ).count()
    return render(
        request,
        "courses/teacher_dashboard.html",
        {"courses": courses, "review_count": review_count, "appeal_count": appeal_count},
    )


@login_required
@require_http_methods(["GET", "POST"])
def create_course(request):
    membership = (
        request.user.memberships.filter(
            role__in=[Membership.Role.OWNER, Membership.Role.ADMIN, Membership.Role.TEACHER],
        )
        .select_related("organization")
        .first()
    )
    if membership is None:
        return HttpResponseForbidden("You must belong to a teacher organization to create a course.")

    form = CourseForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            course = form.save(commit=False)
            course.organization = membership.organization
            course.created_by = request.user
            course.status = Course.Status.DRAFT
            course.save()
            draft = create_draft_version(course, actor=request.user)
        messages.success(request, "Course created. Start building the first draft version.")
        return redirect("teacher_courses:version-editor", slug=course.slug, version_id=draft.id)
    return render(request, "courses/course_form.html", {"form": form})


@login_required
@require_http_methods(["GET", "POST"])
@csrf_protect
@rate_limit("course-generation", limit=settings.AI_RATE_LIMIT_COURSE_GENERATION, period=3600)
def generate_course(request):
    membership = (
        request.user.memberships.filter(
            role__in=[Membership.Role.OWNER, Membership.Role.ADMIN, Membership.Role.TEACHER],
        )
        .select_related("organization")
        .first()
    )
    if membership is None:
        return HttpResponseForbidden("You must belong to a teacher organization to generate a course.")

    form = CourseGenerationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            course = Course.objects.create(
                organization=membership.organization,
                created_by=request.user,
                title=form.cleaned_data["title"],
                description=form.cleaned_data["objective"],
                duration_weeks=form.cleaned_data["duration_weeks"],
                status=Course.Status.DRAFT,
            )
            generation_request = CourseGenerationRequest.objects.create(
                created_by=request.user,
                course=course,
                title=form.cleaned_data["title"],
                objective=form.cleaned_data["objective"],
                duration_weeks=form.cleaned_data["duration_weeks"],
                audience=form.cleaned_data["audience"],
                free_prompt=form.cleaned_data["free_prompt"],
            )
            job = AIJob.objects.create(
                job_type=AIJob.JobType.COURSE_GENERATION,
                entity_type="course_generation_request",
                entity_id=generation_request.id,
                status=AIJob.Status.QUEUED,
                prompt_version=settings.AI_COURSE_PROMPT_VERSION,
            )
            record_audit_event(
                action="ai_course_generation_requested",
                actor=request.user,
                obj=generation_request,
                request=request,
                metadata={"job_id": str(job.id), "prompt_version": job.prompt_version},
            )
            transaction.on_commit(lambda: _enqueue_course_generation(job.id))
        messages.success(request, "Course generation started. Review the draft before publishing.")
        return redirect("teacher_courses:generation-status", request_id=generation_request.id)
    return render(request, "courses/course_generation_form.html", {"form": form})


@login_required
def generation_status(request, request_id):
    generation_request = get_object_or_404(
        CourseGenerationRequest.objects.select_related("course", "generated_version"),
        id=request_id,
        created_by=request.user,
    )
    job = AIJob.objects.filter(
        job_type=AIJob.JobType.COURSE_GENERATION,
        entity_type="course_generation_request",
        entity_id=generation_request.id,
    ).order_by("-created_at").first()
    return render(
        request,
        "courses/course_generation_status.html",
        {"generation_request": generation_request, "job": job},
    )


def _enqueue_course_generation(job_id):
    try:
        from ai_engine.tasks import generate_course

        if settings.CELERY_TASK_ALWAYS_EAGER:
            generate_course.apply(args=[str(job_id)])
        else:
            generate_course.delay(str(job_id))
    except Exception:
        import logging

        logging.getLogger(__name__).exception("Unable to enqueue course generation job %s", job_id)


@login_required
def course_studio(request, slug):
    course = get_object_or_404(Course, slug=slug)
    if not user_has_teacher_access(request.user, course.organization):
        return HttpResponseForbidden("You do not have access to this course studio.")
    versions = course.versions.prefetch_related("modules__lessons").all()
    return render(
        request,
        "courses/studio.html",
        {
            "course": course,
            "versions": versions,
            "draft_version": versions.filter(status=CourseVersion.Status.DRAFT).first(),
            "can_delete": course.created_by_id == request.user.id or user_has_admin_access(request.user, course.organization),
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def course_settings(request, slug):
    course = get_object_or_404(Course, slug=slug)
    if not user_has_teacher_access(request.user, course.organization):
        return HttpResponseForbidden("You do not have access to edit this course.")
    if course.versions.filter(status=CourseVersion.Status.PUBLISHED).exists():
        return HttpResponseForbidden("Published course settings cannot be edited. Create a new version instead.")
    form = CourseForm(request.POST or None, instance=course)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Course setup saved.")
        draft = course.versions.filter(status=CourseVersion.Status.DRAFT).order_by("-version_number").first()
        if draft:
            destination = reverse("teacher_courses:version-editor", kwargs={"slug": course.slug, "version_id": draft.id})
            first_module = draft.modules.order_by("position").first()
            if first_module:
                destination = f"{destination}#module-{first_module.id}"
            return redirect(destination)
        return redirect("teacher_courses:studio", slug=course.slug)
    return render(request, "courses/course_settings_form.html", {"course": course, "form": form})


@login_required
@require_POST
def delete_course(request, slug):
    course = get_object_or_404(Course, slug=slug)
    if not user_has_teacher_access(request.user, course.organization):
        return HttpResponseForbidden("You do not have access to delete this course.")
    if course.created_by_id != request.user.id and not user_has_admin_access(request.user, course.organization):
        return HttpResponseForbidden("Only the course creator or an organization administrator can delete this course.")
    if course.status != Course.Status.DRAFT:
        messages.error(request, "Only draft courses can be deleted. Published courses must be archived instead.")
        return redirect("teacher_courses:studio", slug=course.slug)
    if course.enrollments.exists():
        messages.error(request, "This course cannot be deleted because learners are enrolled in it.")
        return redirect("teacher_courses:studio", slug=course.slug)

    course_title = course.title
    with transaction.atomic():
        course.delete()
    messages.success(request, f'Course "{course_title}" was deleted.')
    return redirect("dashboard:teacher-dashboard")


@login_required
def preview_version(request, slug, version_id, lesson_id=None):
    course = get_object_or_404(Course, slug=slug)
    version = get_object_or_404(
        CourseVersion.objects.prefetch_related("modules__lessons__artifacts", "modules__lessons__questions"),
        id=version_id,
        course=course,
    )
    if not user_has_teacher_access(request.user, course.organization):
        return HttpResponseForbidden("You do not have access to preview this course.")
    modules = list(version.modules.all())
    lessons = [lesson for module in modules for lesson in module.lessons.all()]
    selected_lesson = lessons[0] if lessons else None
    if lesson_id:
        selected_lesson = get_object_or_404(
            LessonVersion,
            id=lesson_id,
            module__course_version=version,
        )
    return render(
        request,
        "courses/preview.html",
        {
            "course": course,
            "version": version,
            "modules": modules,
            "final_project": getattr(version, "final_project", None),
            "selected_lesson": selected_lesson,
        },
    )


@login_required
@require_POST
def create_course_version(request, slug):
    course = get_object_or_404(Course, slug=slug)
    if not user_has_teacher_access(request.user, course.organization):
        return HttpResponseForbidden("You do not have access to this course studio.")
    draft = course.versions.filter(status=CourseVersion.Status.DRAFT).first()
    if draft is None:
        draft = create_draft_version(course, actor=request.user)
    return redirect("teacher_courses:version-editor", slug=course.slug, version_id=draft.id)


@login_required
@require_http_methods(["GET", "POST"])
def final_project_form(request, slug, version_id):
    course, version, error = _get_editable_version(request, slug, version_id)
    if error:
        return error
    project = getattr(version, "final_project", None)
    if request.method == "POST":
        if project is None:
            project = FinalProject(course_version=version)
        form = FinalProjectForm(request.POST, instance=project)
        if form.is_valid():
            form.save()
            messages.success(request, "Final project saved to the draft version.")
            return redirect("teacher_courses:version-editor", slug=course.slug, version_id=version.id)
    else:
        form = FinalProjectForm(instance=project)
    return render(
        request,
        "courses/final_project_form.html",
        {"course": course, "version": version, "project": project, "form": form},
    )


def _get_editable_version(request, slug, version_id):
    course = get_object_or_404(Course, slug=slug)
    version = get_object_or_404(
        CourseVersion.objects.prefetch_related("modules__lessons__questions__rubrics"),
        id=version_id,
        course=course,
    )
    if not user_has_teacher_access(request.user, course.organization):
        return course, version, HttpResponseForbidden("You do not have access to this course version.")
    if version.status != CourseVersion.Status.DRAFT:
        return course, version, HttpResponseForbidden("Published course versions cannot be edited.")
    return course, version, None


def _editor_redirect(course, version, anchor):
    editor_url = reverse(
        "teacher_courses:version-editor",
        kwargs={"slug": course.slug, "version_id": version.id},
    )
    return redirect(f"{editor_url}#{anchor}")


@login_required
def version_editor(request, slug, version_id):
    course, version, error = _get_editable_version(request, slug, version_id)
    if error:
        return error
    modules = list(version.modules.all())
    version.module_count = len(modules)
    version.lesson_count = sum(len(module.lessons.all()) for module in modules)
    version.question_count = sum(
        len(lesson.questions.all())
        for module in modules
        for lesson in module.lessons.all()
    )
    version.rubric_count = sum(
        len(question.rubrics.all())
        for module in modules
        for lesson in module.lessons.all()
        for question in lesson.questions.all()
    )
    return render(
        request,
        "courses/version_editor.html",
        {
            "course": course,
            "version": version,
            "modules": modules,
            "first_module": modules[0] if modules else None,
            "final_project": getattr(version, "final_project", None),
            "validation_errors": _version_validation_errors(version, modules),
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def add_module(request, slug, version_id, module_id=None):
    course, version, error = _get_editable_version(request, slug, version_id)
    if error:
        return error
    module = get_object_or_404(Module, id=module_id, course_version=version) if module_id else None
    form = ModuleForm(
        request.POST or None,
        instance=module,
        initial={"position": version.modules.count() + 1} if module is None else None,
    )
    if request.method == "POST" and form.is_valid():
        saved_module = form.save(commit=False)
        saved_module.course_version = version
        saved_module.save()
        messages.success(request, "Module saved to the draft version.")
        if request.POST.get("next") == "lesson":
            first_lesson = saved_module.lessons.order_by("position").first()
            if first_lesson:
                return redirect(
                    "teacher_courses:edit-lesson",
                    slug=course.slug,
                    version_id=version.id,
                    module_id=saved_module.id,
                    lesson_id=first_lesson.id,
                )
            return redirect(
                "teacher_courses:create-lesson",
                slug=course.slug,
                version_id=version.id,
                module_id=saved_module.id,
            )
        if request.POST.get("next") == "module":
            next_module = version.modules.filter(position__gt=saved_module.position).order_by("position").first()
            if next_module:
                return redirect(
                    "teacher_courses:edit-module",
                    slug=course.slug,
                    version_id=version.id,
                    module_id=next_module.id,
                )
        return redirect("teacher_courses:version-editor", slug=course.slug, version_id=version.id)
    next_module = None
    if module:
        next_module = version.modules.filter(position__gt=module.position).order_by("position").first()
    return render(
        request,
        "courses/module_form.html",
        {
            "course": course,
            "version": version,
            "module": module,
            "form": form,
            "next_module": next_module,
        },
    )


def _renumber_modules(version):
    for position, module in enumerate(version.modules.order_by("position"), start=1):
        if module.position != position:
            module.position = position
            module.save(update_fields=["position"])


def _renumber_lessons(module):
    for position, lesson in enumerate(module.lessons.order_by("position"), start=1):
        if lesson.position != position:
            lesson.position = position
            lesson.save(update_fields=["position"])


@login_required
@require_POST
def delete_module(request, slug, version_id, module_id):
    course, version, error = _get_editable_version(request, slug, version_id)
    if error:
        return error
    module = get_object_or_404(Module, id=module_id, course_version=version)
    if Attempt.objects.filter(question__lesson_version__module=module).exists():
        messages.error(request, "This module has learner assessment attempts and cannot be removed.")
        return _editor_redirect(course, version, f"module-{module.id}")
    module_title = module.title
    lesson_count = module.lessons.count()
    with transaction.atomic():
        record_audit_event(
            action="course_module_deleted",
            actor=request.user,
            obj=module,
            request=request,
            metadata={"course_id": str(course.id), "version_id": str(version.id), "lesson_count": lesson_count},
        )
        module.delete()
        _renumber_modules(version)
    messages.success(request, f'Module "{module_title}" and its {lesson_count} lesson(s) were removed.')
    return _editor_redirect(course, version, "lessons")


@login_required
@require_http_methods(["GET", "POST"])
def artifact_form(request, slug, version_id, lesson_id, artifact_id=None):
    course, version, error = _get_editable_version(request, slug, version_id)
    if error:
        return error
    lesson = get_object_or_404(LessonVersion, id=lesson_id, module__course_version=version)
    artifact = get_object_or_404(LessonArtifact, id=artifact_id, lesson_version=lesson) if artifact_id else None
    form = ArtifactForm(
        request.POST or None,
        request.FILES or None,
        instance=artifact,
        initial={"position": lesson.artifacts.count()} if artifact is None else None,
    )
    if request.method == "POST" and form.is_valid():
        saved_artifact = form.save(commit=False)
        saved_artifact.lesson_version = lesson
        if not saved_artifact.ai_generated:
            saved_artifact.teacher_approved = True
        saved_artifact.save()
        messages.success(request, "Learning material saved to the draft version.")
        return _editor_redirect(course, version, f"lesson-{lesson.id}-materials")
    return render(
        request,
        "courses/artifact_form.html",
        {"course": course, "version": version, "lesson": lesson, "artifact": artifact, "form": form},
    )


@login_required
@require_POST
def delete_artifact(request, slug, version_id, lesson_id, artifact_id):
    course, version, error = _get_editable_version(request, slug, version_id)
    if error:
        return error
    lesson = get_object_or_404(LessonVersion, id=lesson_id, module__course_version=version)
    artifact = get_object_or_404(LessonArtifact, id=artifact_id, lesson_version=lesson)
    artifact_type = artifact.get_artifact_type_display()
    record_audit_event(
        action="lesson_artifact_deleted",
        actor=request.user,
        obj=artifact,
        request=request,
        metadata={"course_id": str(course.id), "version_id": str(version.id), "lesson_id": str(lesson.id)},
    )
    artifact.delete()
    messages.success(request, f"{artifact_type} material removed from the draft version.")
    return _editor_redirect(course, version, f"lesson-{lesson.id}-materials")


def _selected_ids(request, field_name):
    selected_ids = []
    for value in request.POST.getlist(field_name):
        try:
            selected_id = uuid.UUID(value)
        except (AttributeError, TypeError, ValueError):
            continue
        if selected_id not in selected_ids:
            selected_ids.append(selected_id)
    return selected_ids


@login_required
@require_POST
def delete_artifacts(request, slug, version_id, lesson_id):
    course, version, error = _get_editable_version(request, slug, version_id)
    if error:
        return error
    lesson = get_object_or_404(LessonVersion, id=lesson_id, module__course_version=version)
    selected_ids = _selected_ids(request, "artifact_ids")
    if not selected_ids:
        messages.error(request, "Select at least one learning material to remove.")
        return _editor_redirect(course, version, f"lesson-{lesson.id}-materials")
    artifacts = LessonArtifact.objects.filter(lesson_version=lesson, id__in=selected_ids)
    artifact_count = artifacts.count()
    if not artifact_count:
        messages.error(request, "The selected learning materials are no longer available.")
        return _editor_redirect(course, version, f"lesson-{lesson.id}-materials")
    with transaction.atomic():
        record_audit_event(
            action="lesson_artifacts_deleted",
            actor=request.user,
            obj=lesson,
            request=request,
            metadata={"course_id": str(course.id), "version_id": str(version.id), "artifact_count": artifact_count},
        )
        artifacts.delete()
    messages.success(request, f"{artifact_count} learning material(s) removed from the draft version.")
    return _editor_redirect(course, version, f"lesson-{lesson.id}-materials")


@login_required
@require_http_methods(["GET", "POST"])
def lesson_form(request, slug, version_id, module_id, lesson_id=None):
    course, version, error = _get_editable_version(request, slug, version_id)
    if error:
        return error
    module = get_object_or_404(Module, id=module_id, course_version=version)
    lesson = None
    if lesson_id:
        lesson = get_object_or_404(LessonVersion, id=lesson_id, module=module)
    form = LessonForm(request.POST or None, instance=lesson)
    if request.method == "POST" and form.is_valid():
        saved_lesson = form.save(commit=False)
        saved_lesson.module = module
        saved_lesson.status = LessonVersion.Status.DRAFT
        saved_lesson.save()
        messages.success(request, "Lesson saved to the draft version.")
        if request.POST.get("next") == "lesson":
            next_lesson = (
                LessonVersion.objects.filter(module__course_version=version)
                .select_related("module")
                .order_by("module__position", "position")
            )
            lesson_ids = list(next_lesson.values_list("id", flat=True))
            try:
                next_lesson_id = lesson_ids[lesson_ids.index(saved_lesson.id) + 1]
            except (ValueError, IndexError):
                next_lesson_id = None
            if next_lesson_id:
                next_lesson = LessonVersion.objects.select_related("module").get(id=next_lesson_id)
                return redirect(
                    "teacher_courses:edit-lesson",
                    slug=course.slug,
                    version_id=version.id,
                    module_id=next_lesson.module_id,
                    lesson_id=next_lesson.id,
                )
        return _editor_redirect(course, version, f"lesson-{saved_lesson.id}-materials")
    next_lesson = None
    if lesson:
        lessons = list(
            LessonVersion.objects.filter(module__course_version=version)
            .select_related("module")
            .order_by("module__position", "position")
        )
        for index, candidate in enumerate(lessons):
            if candidate.id == lesson.id and index + 1 < len(lessons):
                next_lesson = lessons[index + 1]
                break
    return render(
        request,
        "courses/lesson_form.html",
        {
            "course": course,
            "version": version,
            "module": module,
            "lesson": lesson,
            "form": form,
            "next_lesson": next_lesson,
        },
    )


@login_required
@require_POST
def delete_lesson(request, slug, version_id, module_id, lesson_id):
    course, version, error = _get_editable_version(request, slug, version_id)
    if error:
        return error
    module = get_object_or_404(Module, id=module_id, course_version=version)
    lesson = get_object_or_404(LessonVersion, id=lesson_id, module=module)
    if Attempt.objects.filter(question__lesson_version=lesson).exists():
        messages.error(request, "This lesson has learner assessment attempts and cannot be removed.")
        return _editor_redirect(course, version, f"lesson-{lesson.id}")
    lesson_title = lesson.title
    with transaction.atomic():
        record_audit_event(
            action="course_lesson_deleted",
            actor=request.user,
            obj=lesson,
            request=request,
            metadata={"course_id": str(course.id), "version_id": str(version.id), "module_id": str(module.id)},
        )
        lesson.delete()
        _renumber_lessons(module)
    messages.success(request, f'Lesson "{lesson_title}" was removed from the draft version.')
    return _editor_redirect(course, version, f"module-{module.id}")


@login_required
@require_http_methods(["GET", "POST"])
def question_form(request, slug, version_id, lesson_id, question_id=None):
    course, version, error = _get_editable_version(request, slug, version_id)
    if error:
        return error
    lesson = get_object_or_404(LessonVersion, id=lesson_id, module__course_version=version)
    question = get_object_or_404(Question, id=question_id, lesson_version=lesson) if question_id else None
    rubric = question.rubrics.order_by("-version_number").first() if question else None
    question_form = QuestionForm(request.POST or None, instance=question)
    rubric_form = RubricForm(
        request.POST or None,
        initial={
            "criteria_text": "\n".join(item.get("criterion", "") for item in (rubric.criteria if rubric else [])),
            "total_score": rubric.total_score if rubric else 100,
        },
    )
    if request.method == "POST" and question_form.is_valid() and rubric_form.is_valid():
        with transaction.atomic():
            saved_question = question_form.save(commit=False)
            saved_question.lesson_version = lesson
            saved_question.save()
            criteria = [
                {"criterion": criterion, "weight": round(100 / len(rubric_form.cleaned_data["criteria_text"]), 2)}
                for criterion in rubric_form.cleaned_data["criteria_text"]
            ]
            RubricVersion.objects.update_or_create(
                question=saved_question,
                version_number=1,
                defaults={
                    "criteria": criteria,
                    "total_score": rubric_form.cleaned_data["total_score"],
                    "approved_by": None,
                    "approved_at": None,
                },
            )
        messages.success(request, "Question and rubric saved to the draft version.")
        return _editor_redirect(course, version, f"lesson-{lesson.id}-assessments")
    return render(
        request,
        "courses/question_form.html",
        {
            "course": course,
            "version": version,
            "lesson": lesson,
            "question": question,
            "question_form": question_form,
            "rubric_form": rubric_form,
        },
    )


@login_required
@require_POST
def delete_question(request, slug, version_id, lesson_id, question_id):
    course, version, error = _get_editable_version(request, slug, version_id)
    if error:
        return error
    lesson = get_object_or_404(LessonVersion, id=lesson_id, module__course_version=version)
    question = get_object_or_404(Question, id=question_id, lesson_version=lesson)
    if question.attempts.exists():
        messages.error(request, "This assessment has learner attempts and cannot be removed.")
        return _editor_redirect(course, version, f"lesson-{lesson.id}-assessments")
    record_audit_event(
        action="lesson_question_deleted",
        actor=request.user,
        obj=question,
        request=request,
        metadata={"course_id": str(course.id), "version_id": str(version.id), "lesson_id": str(lesson.id)},
    )
    question.delete()
    messages.success(request, "Assessment and its rubric removed from the draft version.")
    return _editor_redirect(course, version, f"lesson-{lesson.id}-assessments")


@login_required
@require_POST
def delete_questions(request, slug, version_id, lesson_id):
    course, version, error = _get_editable_version(request, slug, version_id)
    if error:
        return error
    lesson = get_object_or_404(LessonVersion, id=lesson_id, module__course_version=version)
    selected_ids = _selected_ids(request, "question_ids")
    if not selected_ids:
        messages.error(request, "Select at least one assessment to remove.")
        return _editor_redirect(course, version, f"lesson-{lesson.id}-assessments")
    questions = Question.objects.filter(lesson_version=lesson, id__in=selected_ids)
    question_count = questions.count()
    if not question_count:
        messages.error(request, "The selected assessments are no longer available.")
        return _editor_redirect(course, version, f"lesson-{lesson.id}-assessments")
    if Attempt.objects.filter(question__in=questions).exists():
        messages.error(request, "One or more selected assessments have learner attempts and cannot be removed.")
        return _editor_redirect(course, version, f"lesson-{lesson.id}-assessments")
    with transaction.atomic():
        record_audit_event(
            action="lesson_questions_deleted",
            actor=request.user,
            obj=lesson,
            request=request,
            metadata={"course_id": str(course.id), "version_id": str(version.id), "question_count": question_count},
        )
        questions.delete()
    messages.success(request, f"{question_count} assessment(s) and their rubrics removed from the draft version.")
    return _editor_redirect(course, version, f"lesson-{lesson.id}-assessments")


@login_required
@require_POST
@csrf_protect
def publish_version(request, slug, version_id):
    course, version, error = _get_editable_version(request, slug, version_id)
    if error:
        return error
    modules = list(version.modules.all())
    validation_errors = _version_validation_errors(version, modules)
    if validation_errors:
        for message in validation_errors:
            messages.error(request, message)
        return redirect("teacher_courses:version-editor", slug=course.slug, version_id=version.id)

    with transaction.atomic():
        now = timezone.now()
        LessonVersion.objects.filter(module__course_version=version).update(status=LessonVersion.Status.PUBLISHED)
        for question in Question.objects.filter(lesson_version__module__course_version=version, is_active=True):
            question.rubrics.order_by("-version_number").update(approved_by=request.user, approved_at=now)
        version.status = CourseVersion.Status.PUBLISHED
        version.approved_by = request.user
        version.approved_at = now
        version.save(update_fields=["status", "approved_by", "approved_at"])
        course.status = Course.Status.PUBLISHED
        course.save(update_fields=["status", "updated_at"])
        LessonArtifact.objects.filter(
            lesson_version__module__course_version=version,
            ai_generated=True,
        ).update(teacher_approved=True)
        FinalProject.objects.filter(course_version=version).update(teacher_approved=True)
        CourseGenerationRequest.objects.filter(generated_version=version).update(
            status=CourseGenerationRequest.Status.PUBLISHED,
            completed_at=now,
        )
        record_audit_event(
            action="course_version_published",
            actor=request.user,
            obj=version,
            request=request,
            metadata={"course_id": str(course.id), "version_number": version.version_number},
        )
    messages.success(request, f"Version {version.version_number} is now published and immutable.")
    return redirect("teacher_courses:studio", slug=course.slug)


def _version_validation_errors(version, modules=None):
    modules = modules if modules is not None else list(version.modules.all())
    validation_errors = []
    if not modules:
        validation_errors.append("Add at least one module.")
    for module in modules:
        lessons = list(module.lessons.all())
        if not lessons:
            validation_errors.append(f"Module '{module.title}' needs at least one lesson.")
        for lesson in lessons:
            if not lesson.content.strip():
                validation_errors.append(f"Lesson '{lesson.title}' needs lesson content.")
            questions = list(lesson.questions.filter(is_active=True))
            if not questions:
                validation_errors.append(f"Lesson '{lesson.title}' needs at least one active assessment.")
            for question in questions:
                rubric = question.rubrics.order_by("-version_number").first()
                if not rubric or not rubric.criteria:
                    validation_errors.append(f"Assessment '{question.prompt[:60]}' needs a rubric.")
    return validation_errors
