from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import Http404, HttpResponseForbidden
from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST
from django.conf import settings

from accounts.access import user_has_admin_access, user_has_teacher_access, user_is_student, user_is_teacher
from ai_engine.models import AIJob, CourseGenerationRequest
from assessments.forms import QuestionForm, RubricForm
from assessments.models import Attempt, Question, ReviewQueueItem, RubricVersion
from enrollments.models import Enrollment, LessonProgress
from enrollments.services import mark_lesson_complete
from organizations.models import Membership

from .forms import ArtifactForm, CourseForm, CourseGenerationForm, LessonForm, ModuleForm
from .models import Course, CourseVersion, LessonArtifact, LessonVersion, Module
from .services import create_draft_version


def catalog(request):
    courses = Course.objects.filter(status=Course.Status.PUBLISHED).select_related("organization", "created_by")
    return render(request, "courses/catalog.html", {"courses": courses})


@login_required
def course_detail(request, slug):
    course = get_object_or_404(Course, slug=slug, status=Course.Status.PUBLISHED)
    version = course.versions.filter(status=CourseVersion.Status.PUBLISHED).first()
    enrollment = Enrollment.objects.filter(course=course, student=request.user).first()
    return render(request, "courses/detail.html", {"course": course, "version": version, "enrollment": enrollment})


@login_required
@require_POST
def enroll(request, slug):
    course = get_object_or_404(Course, slug=slug, status=Course.Status.PUBLISHED)
    version = course.versions.filter(status=CourseVersion.Status.PUBLISHED).order_by("-version_number").first()
    if version is None:
        raise Http404("No published course version is available for enrollment.")
    Enrollment.objects.get_or_create(
        course=course,
        student=request.user,
        defaults={"course_version": version},
    )
    return redirect("courses:learn", slug=course.slug)


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
        selected_lesson = get_object_or_404(
            LessonVersion,
            id=lesson_id,
            module__course_version=version,
        )
    else:
        selected_lesson = lessons[0] if lessons else None
    progress = LessonProgress.objects.filter(enrollment=enrollment)
    attempts = Attempt.objects.filter(enrollment=enrollment, question__lesson_version__in=lessons).select_related(
        "grade_decision"
    )
    progress_by_lesson = {item.lesson_version_id: item for item in progress}
    attempts_by_question = {attempt.question_id: attempt for attempt in attempts}
    for lesson in lessons:
        lesson.student_progress = progress_by_lesson.get(lesson.id)
        for question in lesson.questions.all():
            question.student_attempt = attempts_by_question.get(question.id)
    return render(
        request,
        "courses/learn.html",
        {
            "course": course,
            "enrollment": enrollment,
            "modules": modules,
            "first_lesson": selected_lesson,
            "selected_lesson": selected_lesson,
            "progress_by_lesson": progress_by_lesson,
            "attempts_by_question": attempts_by_question,
        },
    )


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
    enrollments = Enrollment.objects.filter(student=request.user, status=Enrollment.Status.ACTIVE).select_related("course", "course_version")
    for enrollment in enrollments:
        enrollment.progress_count = enrollment.lesson_progress.filter(status=LessonProgress.Status.COMPLETED).count()
        enrollment.lesson_count = LessonVersion.objects.filter(module__course_version=enrollment.course_version).count()
    return render(request, "courses/student_dashboard.html", {"enrollments": enrollments})


@login_required
def teacher_dashboard(request):
    if not user_is_teacher(request.user):
        return HttpResponseForbidden("You do not have access to the teacher dashboard.")
    courses = Course.objects.filter(created_by=request.user).select_related("organization").order_by("-updated_at")
    review_count = ReviewQueueItem.objects.filter(status=ReviewQueueItem.Status.OPEN, assigned_to=request.user).count()
    return render(request, "courses/teacher_dashboard.html", {"courses": courses, "review_count": review_count})


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
                translation_languages=form.cleaned_data["translation_languages"],
            )
            job = AIJob.objects.create(
                job_type=AIJob.JobType.COURSE_GENERATION,
                entity_type="course_generation_request",
                entity_id=generation_request.id,
                status=AIJob.Status.QUEUED,
                prompt_version=settings.AI_COURSE_PROMPT_VERSION,
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


@login_required
def version_editor(request, slug, version_id):
    course, version, error = _get_editable_version(request, slug, version_id)
    if error:
        return error
    return render(request, "courses/version_editor.html", {"course": course, "version": version})


@login_required
@require_http_methods(["GET", "POST"])
def add_module(request, slug, version_id):
    course, version, error = _get_editable_version(request, slug, version_id)
    if error:
        return error
    form = ModuleForm(request.POST or None, initial={"position": version.modules.count() + 1})
    if request.method == "POST" and form.is_valid():
        module = form.save(commit=False)
        module.course_version = version
        module.save()
        messages.success(request, "Module added to the draft version.")
        return redirect("teacher_courses:version-editor", slug=course.slug, version_id=version.id)
    return render(request, "courses/module_form.html", {"course": course, "version": version, "form": form})


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
        saved_artifact.save()
        messages.success(request, "Learning material saved to the draft version.")
        return redirect("teacher_courses:version-editor", slug=course.slug, version_id=version.id)
    return render(
        request,
        "courses/artifact_form.html",
        {"course": course, "version": version, "lesson": lesson, "artifact": artifact, "form": form},
    )


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
        return redirect("teacher_courses:version-editor", slug=course.slug, version_id=version.id)
    return render(
        request,
        "courses/lesson_form.html",
        {"course": course, "version": version, "module": module, "lesson": lesson, "form": form},
    )


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
        return redirect("teacher_courses:version-editor", slug=course.slug, version_id=version.id)
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
def publish_version(request, slug, version_id):
    course, version, error = _get_editable_version(request, slug, version_id)
    if error:
        return error
    validation_errors = []
    modules = list(version.modules.all())
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
                validation_errors.append(f"Lesson '{lesson.title}' needs at least one active question.")
            for question in questions:
                rubric = question.rubrics.order_by("-version_number").first()
                if not rubric or not rubric.criteria:
                    validation_errors.append(f"Question '{question.prompt[:60]}' needs a rubric.")
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
        CourseGenerationRequest.objects.filter(generated_version=version).update(
            status=CourseGenerationRequest.Status.PUBLISHED,
            completed_at=now,
        )
    messages.success(request, f"Version {version.version_number} is now published and immutable.")
    return redirect("teacher_courses:studio", slug=course.slug)
