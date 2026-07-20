from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.conf import settings
from django.db import transaction
from django.db.models import Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect
from django.utils import timezone

from ai_engine.models import AIJob
from ai_engine.rate_limit import rate_limit
from ai_engine.tasks import grade_attempt
from analytics.security import record_audit_event
from accounts.access import user_has_teacher_access, user_is_teacher
from courses.models import LessonVersion, Module
from enrollments.models import Enrollment
from notifications.models import Notification
from organizations.models import Membership

from .access import has_copy_paste_accommodation
from .forms import AccommodationRequestForm, AppealForm, AttemptForm, GradeDecisionForm
from .models import (
    AccommodationRequest,
    Appeal,
    Attempt,
    GradeEvent,
    Question,
    ReviewQueueItem,
    RubricVersion,
    Submission,
)
from .services import confirm_attempt_grade, queue_manual_review, record_grade_event


@login_required
@require_http_methods(["GET", "POST"])
@csrf_protect
@rate_limit("assessment-submission", limit=settings.AI_RATE_LIMIT_ATTEMPT, period=3600)
def submit_attempt(request, question_id):
    question = get_object_or_404(Question.objects.select_related("lesson_version__module__course_version"), id=question_id, is_active=True)
    enrollment = get_object_or_404(
        Enrollment,
        student=request.user,
        course_version=question.lesson_version.module.course_version,
        status=Enrollment.Status.ACTIVE,
    )
    attempts_used = Attempt.objects.filter(enrollment=enrollment, question=question).count()
    if attempts_used >= 3:
        return render(request, "assessments/attempt_locked.html", {"question": question}, status=400)

    allow_copy_paste = has_copy_paste_accommodation(
        request.user,
        question.lesson_version.module.course_version.course,
    )
    form = AttemptForm(request.POST or None, allow_copy_paste=allow_copy_paste)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            locked_enrollment = Enrollment.objects.select_for_update().get(pk=enrollment.pk)
            attempts_used = Attempt.objects.filter(
                enrollment=locked_enrollment,
                question=question,
            ).count()
            if attempts_used >= 3:
                return render(request, "assessments/attempt_locked.html", {"question": question}, status=400)
            attempt = form.save(commit=False)
            attempt.enrollment = locked_enrollment
            attempt.question = question
            attempt.attempt_number = attempts_used + 1
            attempt.status = Attempt.Status.SUBMITTED
            attempt.save()
            Submission.objects.create(
                attempt=attempt,
                answer_text=attempt.answer_text,
                code_language="python" if question.question_type in {"code_writing", "debugging", "error_identification"} else "",
            )
            record_grade_event(attempt, GradeEvent.EventType.SUBMITTED, actor=request.user)
            job = AIJob.objects.create(
                job_type=AIJob.JobType.GRADING,
                entity_type="attempt",
                entity_id=attempt.id,
                status=AIJob.Status.QUEUED,
            )
            record_audit_event(
                action="assessment_attempt_submitted",
                actor=request.user,
                obj=attempt,
                request=request,
                metadata={"job_id": str(job.id), "attempt_number": attempt.attempt_number},
            )
            transaction.on_commit(lambda: _enqueue_grading(job.id))
        messages.success(request, "Assessment submitted. Your teacher will review the result when it is ready.")
        return _redirect_to_next_learning_step(question)

    return render(
        request,
        "assessments/submit.html",
        {
            "question": question,
            "form": form,
            "attempt_number": attempts_used + 1,
            "allow_copy_paste": allow_copy_paste,
        },
    )


def _redirect_to_next_learning_step(question):
    """Advance through remaining assessments in a lesson, then the next lesson."""
    lesson = question.lesson_version
    lesson_questions = list(
        Question.objects.filter(lesson_version=lesson, is_active=True).order_by("position", "id")
    )
    try:
        current_index = next(index for index, candidate in enumerate(lesson_questions) if candidate.id == question.id)
    except StopIteration:
        current_index = len(lesson_questions)
    if current_index + 1 < len(lesson_questions):
        return redirect("assessments:submit", question_id=lesson_questions[current_index + 1].id)

    next_lesson = (
        LessonVersion.objects.filter(module__course_version=lesson.module.course_version)
        .filter(
            Q(module__position__gt=lesson.module.position)
            | Q(module=lesson.module, position__gt=lesson.position)
        )
        .select_related("module")
        .order_by("module__position", "position", "id")
        .first()
    )
    if next_lesson:
        return redirect(
            "courses:learn-lesson",
            slug=lesson.module.course_version.course.slug,
            lesson_id=next_lesson.id,
        )
    return redirect(
        "courses:learn-lesson",
        slug=lesson.module.course_version.course.slug,
        lesson_id=lesson.id,
    )


@login_required
@require_http_methods(["GET", "POST"])
def request_accommodation(request):
    form = AccommodationRequestForm(request.POST or None, student=request.user)
    if request.method == "POST" and form.is_valid():
        accommodation = form.save(commit=False)
        accommodation.student = request.user
        accommodation.save()
        return redirect("assessments:accommodation-requested")
    return render(request, "assessments/accommodation_form.html", {"form": form})


@login_required
def accommodation_requested(request):
    return render(request, "assessments/accommodation_requested.html")


@login_required
def accommodation_queue(request):
    if not user_is_teacher(request.user):
        from django.http import HttpResponseForbidden

        return HttpResponseForbidden("You do not have access to accommodation requests.")
    items = AccommodationRequest.objects.filter(status=AccommodationRequest.Status.PENDING).filter(
        Q(course__created_by=request.user)
        | Q(
            course__organization__memberships__user=request.user,
            course__organization__memberships__role__in={
                Membership.Role.OWNER,
                Membership.Role.ADMIN,
                Membership.Role.TEACHER,
            },
        )
    ).select_related("student", "course").distinct()
    return render(request, "assessments/accommodation_queue.html", {"requests": items})


@login_required
@require_POST
def decide_accommodation(request, request_id):
    accommodation = get_object_or_404(
        AccommodationRequest.objects.select_related("course", "student"),
        id=request_id,
        status=AccommodationRequest.Status.PENDING,
    )
    if not user_has_teacher_access(request.user, accommodation.course.organization):
        from django.http import HttpResponseForbidden

        return HttpResponseForbidden("You do not have access to this accommodation request.")
    decision = request.POST.get("decision")
    if decision not in {AccommodationRequest.Status.APPROVED, AccommodationRequest.Status.DECLINED}:
        return redirect("assessments:accommodation-queue")
    accommodation.status = decision
    accommodation.reviewed_by = request.user
    accommodation.reviewed_at = timezone.now()
    accommodation.save(update_fields=["status", "reviewed_by", "reviewed_at"])
    return redirect("assessments:accommodation-queue")


@login_required
def attempt_status(request, attempt_id):
    attempt = get_object_or_404(
        Attempt.objects.select_related(
            "question__lesson_version__module",
            "enrollment__course",
            "enrollment__course_version",
        ),
        id=attempt_id,
        enrollment__student=request.user,
    )
    job = AIJob.objects.filter(entity_type="attempt", entity_id=attempt.id).order_by("-created_at").first()
    grade_decision = getattr(attempt, "grade_decision", None)
    attempts_used = Attempt.objects.filter(enrollment=attempt.enrollment, question=attempt.question).count()
    next_module = (
        Module.objects.filter(
            course_version=attempt.enrollment.course_version,
            position__gt=attempt.question.lesson_version.module.position,
        )
        .order_by("position")
        .prefetch_related("lessons")
        .first()
    )
    next_module_lesson = next_module.lessons.first() if next_module else None
    return render(
        request,
        "assessments/status.html",
        {
            "attempt": attempt,
            "job": job,
            "ai_grade": getattr(attempt, "ai_grade", None),
            "grade_decision": grade_decision,
            "can_retry": bool(
                grade_decision
                and grade_decision.final_score < attempt.enrollment.course.passing_score
                and attempts_used < attempt.enrollment.course.max_retries + 1
            ),
            "next_module_lesson": next_module_lesson,
        },
    )


def _enqueue_grading(job_id):
    try:
        if settings.CELERY_TASK_ALWAYS_EAGER:
            grade_attempt.apply(args=[str(job_id)])
        else:
            grade_attempt.delay(str(job_id))
    except Exception:
        import logging

        logging.getLogger(__name__).exception("Unable to enqueue grading job %s", job_id)


def _review_item_for_teacher(request, review_id):
    item = get_object_or_404(
        ReviewQueueItem.objects.select_related(
            "attempt__question__lesson_version__module__course_version__course",
            "attempt__enrollment__student",
            "attempt__ai_grade",
        ),
        id=review_id,
        status=ReviewQueueItem.Status.OPEN,
    )
    course = item.attempt.question.lesson_version.module.course_version.course
    if not user_has_teacher_access(request.user, course.organization):
        from django.http import HttpResponseForbidden

        return None, HttpResponseForbidden("You do not have access to this review.")
    return item, None


@login_required
def review_queue(request):
    if not user_is_teacher(request.user):
        from django.http import HttpResponseForbidden

        return HttpResponseForbidden("You do not have access to teacher reviews.")
    items = (
        ReviewQueueItem.objects.filter(status=ReviewQueueItem.Status.OPEN)
        .filter(Q(assigned_to=request.user) | Q(assigned_to__isnull=True))
        .filter(
            Q(attempt__question__lesson_version__module__course_version__course__created_by=request.user)
            | Q(
                attempt__question__lesson_version__module__course_version__course__organization__memberships__user=request.user,
                attempt__question__lesson_version__module__course_version__course__organization__memberships__role__in={
                    Membership.Role.OWNER,
                    Membership.Role.ADMIN,
                    Membership.Role.TEACHER,
                },
            )
        )
        .select_related(
            "attempt__question__lesson_version__module__course_version__course",
            "attempt__enrollment__student",
            "attempt__ai_grade",
        )
        .prefetch_related(
            Prefetch(
                "attempt__question__rubrics",
                queryset=RubricVersion.objects.filter(approved_by__isnull=False).order_by("-version_number"),
                to_attr="ai_grading_rubrics",
            )
        )
        .order_by("created_at")
        .distinct()
    )
    items = list(items)
    for item in items:
        approved_rubrics = item.attempt.question.ai_grading_rubrics
        item.ai_grading_rubric = approved_rubrics[0] if approved_rubrics else None
    return render(request, "assessments/review_queue.html", {"review_items": items})


@login_required
@require_http_methods(["GET", "POST"])
def review_detail(request, review_id):
    item, error = _review_item_for_teacher(request, review_id)
    if error:
        return error
    attempt = item.attempt
    ai_grade = getattr(attempt, "ai_grade", None)
    form = GradeDecisionForm(
        request.POST or None,
        initial={"final_score": getattr(ai_grade, "suggested_score", 0)},
    )
    if request.method == "POST" and form.is_valid():
        finalize_review(item, request.user, form.cleaned_data["final_score"], form.cleaned_data["reason"])
        return redirect("assessments:review-queue")
    return render(request, "assessments/review_detail.html", {"item": item, "attempt": attempt, "form": form})


@transaction.atomic
def finalize_review(item, teacher, final_score, reason=""):
    if item.status != ReviewQueueItem.Status.OPEN:
        raise PermissionDenied("This review has already been resolved.")
    return confirm_attempt_grade(item.attempt, final_score, actor=teacher, reason=reason)


@login_required
@require_http_methods(["GET", "POST"])
def submit_appeal(request, attempt_id):
    attempt = get_object_or_404(
        Attempt.objects.select_related(
            "enrollment__student",
            "enrollment__course",
            "question__lesson_version__module__course_version__course",
            "grade_decision",
        ),
        id=attempt_id,
        enrollment__student=request.user,
    )
    if not hasattr(attempt, "grade_decision"):
        raise PermissionDenied("You can appeal only a confirmed grade.")
    if Appeal.objects.filter(attempt=attempt, status=Appeal.Status.PENDING).exists():
        return redirect("assessments:attempt-status", attempt_id=attempt.id)
    form = AppealForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        appeal = form.save(commit=False)
        appeal.attempt = attempt
        appeal.student = request.user
        appeal.save()
        record_grade_event(attempt, GradeEvent.EventType.APPEALED, actor=request.user, metadata={"appeal_id": str(appeal.id)})
        Notification.objects.create(
            recipient=attempt.question.lesson_version.module.course_version.course.created_by,
            notification_type="assessment_appeal",
            title="A student appealed a confirmed grade",
            body=f"Review the appeal for {attempt.question.lesson_version.title}.",
        )
        return redirect("assessments:attempt-status", attempt_id=attempt.id)
    return render(request, "assessments/appeal_form.html", {"attempt": attempt, "form": form})


@login_required
def appeal_queue(request):
    if not user_is_teacher(request.user):
        from django.http import HttpResponseForbidden

        return HttpResponseForbidden("You do not have access to assessment appeals.")
    appeals = (
        Appeal.objects.filter(status=Appeal.Status.PENDING)
        .filter(
            Q(attempt__question__lesson_version__module__course_version__course__created_by=request.user)
            | Q(
                attempt__question__lesson_version__module__course_version__course__organization__memberships__user=request.user,
                attempt__question__lesson_version__module__course_version__course__organization__memberships__role__in={
                    Membership.Role.OWNER,
                    Membership.Role.ADMIN,
                    Membership.Role.TEACHER,
                },
            )
        )
        .select_related("attempt__question__lesson_version", "student", "attempt__grade_decision")
        .distinct()
    )
    return render(request, "assessments/appeal_queue.html", {"appeals": appeals})


@login_required
@require_POST
def decide_appeal(request, appeal_id):
    appeal = get_object_or_404(
        Appeal.objects.select_related(
            "attempt__question__lesson_version__module__course_version__course",
            "student",
        ),
        id=appeal_id,
        status=Appeal.Status.PENDING,
    )
    course = appeal.attempt.question.lesson_version.module.course_version.course
    if not user_has_teacher_access(request.user, course.organization):
        from django.http import HttpResponseForbidden

        return HttpResponseForbidden("You do not have access to this appeal.")
    decision = request.POST.get("decision")
    if decision not in {Appeal.Status.APPROVED, Appeal.Status.REJECTED}:
        return redirect("assessments:appeal-queue")
    appeal.status = decision
    appeal.reviewed_by = request.user
    appeal.decision_note = request.POST.get("decision_note", "").strip()
    appeal.resolved_at = timezone.now()
    appeal.save(update_fields=["status", "reviewed_by", "decision_note", "resolved_at"])
    record_grade_event(
        appeal.attempt,
        GradeEvent.EventType.APPEAL_RESOLVED,
        actor=request.user,
        metadata={"appeal_id": str(appeal.id), "decision": decision},
    )
    if decision == Appeal.Status.APPROVED:
        appeal.attempt.status = Attempt.Status.AWAITING_REVIEW
        appeal.attempt.save(update_fields=["status"])
        grade = getattr(appeal.attempt, "ai_grade", None)
        if grade:
            grade.requires_review = True
            grade.teacher_review_required = True
            grade.save(update_fields=["requires_review", "teacher_review_required"])
        queue_manual_review(appeal.attempt, "Student appeal approved; reassessment required", assigned_to=request.user)
    Notification.objects.create(
        recipient=appeal.student,
        notification_type="assessment_appeal",
        title="Your assessment appeal was reviewed",
        body="Your teacher approved the appeal and reopened the assessment for review."
        if decision == Appeal.Status.APPROVED
        else "Your teacher reviewed your appeal and kept the confirmed grade.",
    )
    return redirect("assessments:appeal-queue")
