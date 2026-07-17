from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponseForbidden
from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from accounts.access import user_has_teacher_access
from assessments.forms import QuestionForm, RubricForm
from assessments.models import Question, ReviewQueueItem, RubricVersion
from enrollments.models import Enrollment, LessonProgress
from organizations.models import Membership

from .forms import CourseForm, LessonForm, ModuleForm
from .models import Course, CourseVersion, LessonVersion, Module
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
def learn(request, slug):
    course = get_object_or_404(Course, slug=slug, status=Course.Status.PUBLISHED)
    enrollment = get_object_or_404(
        Enrollment.objects.select_related("course_version"),
        course=course,
        student=request.user,
        status=Enrollment.Status.ACTIVE,
    )
    version = enrollment.course_version
    modules = version.modules.prefetch_related("lessons__questions").all()
    first_lesson = LessonVersion.objects.filter(module__course_version=version).select_related("module").first()
    progress = LessonProgress.objects.filter(enrollment=enrollment)
    return render(
        request,
        "courses/learn.html",
        {
            "course": course,
            "enrollment": enrollment,
            "modules": modules,
            "first_lesson": first_lesson,
            "progress_by_lesson": {item.lesson_version_id: item for item in progress},
        },
    )


@login_required
def student_dashboard(request):
    enrollments = Enrollment.objects.filter(student=request.user, status=Enrollment.Status.ACTIVE).select_related("course", "course_version")
    for enrollment in enrollments:
        enrollment.progress_count = enrollment.lesson_progress.filter(status=LessonProgress.Status.COMPLETED).count()
        enrollment.lesson_count = LessonVersion.objects.filter(module__course_version=enrollment.course_version).count()
    return render(request, "courses/student_dashboard.html", {"enrollments": enrollments})


@login_required
def teacher_dashboard(request):
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
            draft = create_draft_version(course)
        messages.success(request, "Course created. Start building the first draft version.")
        return redirect("teacher_courses:version-editor", slug=course.slug, version_id=draft.id)
    return render(request, "courses/course_form.html", {"form": form})


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
        draft = create_draft_version(course)
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
    messages.success(request, f"Version {version.version_number} is now published and immutable.")
    return redirect("teacher_courses:studio", slug=course.slug)
