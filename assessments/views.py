from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods
from django.views.decorators.http import require_POST
from django.utils import timezone

from ai_engine.models import AIJob
from ai_engine.tasks import grade_attempt
from accounts.access import user_has_teacher_access, user_is_teacher
from analytics.models import LearningEvent
from gamification.models import XPEvent
from enrollments.models import Enrollment, LessonProgress
from enrollments.services import refresh_course_completion
from notifications.models import Notification
from organizations.models import Membership

from .access import has_copy_paste_accommodation
from .forms import AccommodationRequestForm, AttemptForm, GradeDecisionForm
from .models import AccommodationRequest, Attempt, GradeDecision, Question, ReviewQueueItem


@login_required
@require_http_methods(["GET", "POST"])
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
            attempt = form.save(commit=False)
            attempt.enrollment = enrollment
            attempt.question = question
            attempt.attempt_number = attempts_used + 1
            attempt.status = Attempt.Status.SUBMITTED
            attempt.save()
            job = AIJob.objects.create(
                job_type=AIJob.JobType.GRADING,
                entity_type="attempt",
                entity_id=attempt.id,
                status=AIJob.Status.QUEUED,
            )
            transaction.on_commit(lambda: _enqueue_grading(job.id))
        return redirect("assessments:attempt-status", attempt_id=attempt.id)

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
    attempt = get_object_or_404(Attempt.objects.select_related("question", "enrollment__course"), id=attempt_id, enrollment__student=request.user)
    job = AIJob.objects.filter(entity_type="attempt", entity_id=attempt.id).order_by("-created_at").first()
    return render(
        request,
        "assessments/status.html",
        {
            "attempt": attempt,
            "job": job,
            "ai_grade": getattr(attempt, "ai_grade", None),
            "grade_decision": getattr(attempt, "grade_decision", None),
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
        .order_by("created_at")
    )
    return render(request, "assessments/review_queue.html", {"review_items": items})


@login_required
@require_http_methods(["GET", "POST"])
def review_detail(request, review_id):
    item, error = _review_item_for_teacher(request, review_id)
    if error:
        return error
    attempt = item.attempt
    ai_grade = getattr(attempt, "ai_grade", None)
    form = GradeDecisionForm(request.POST or None, initial={"final_score": getattr(ai_grade, "suggested_score", 0)})
    if request.method == "POST" and form.is_valid():
        finalize_review(item, request.user, form.cleaned_data["final_score"], form.cleaned_data["reason"])
        return redirect("assessments:review-queue")
    return render(request, "assessments/review_detail.html", {"item": item, "attempt": attempt, "form": form})


@transaction.atomic
def finalize_review(item, teacher, final_score, reason=""):
    attempt = item.attempt
    course = attempt.question.lesson_version.module.course_version.course
    if not user_has_teacher_access(teacher, course.organization):
        raise PermissionDenied("You do not have permission to finalize this review.")
    if item.status != ReviewQueueItem.Status.OPEN:
        raise PermissionDenied("This review has already been resolved.")
    if not 0 <= final_score <= 100:
        raise ValueError("Final score must be between 0 and 100.")
    passed = final_score >= course.passing_score
    attempts_used = Attempt.objects.filter(enrollment=attempt.enrollment, question=attempt.question).count()
    progress, _ = LessonProgress.objects.get_or_create(
        enrollment=attempt.enrollment,
        lesson_version=attempt.question.lesson_version,
    )
    previous_best = progress.best_score or 0
    progress.best_score = max(previous_best, final_score)
    progress.attempts_used = attempts_used
    if passed:
        progress.status = LessonProgress.Status.COMPLETED
        progress.completed_at = progress.completed_at or timezone.now()
    elif attempts_used >= course.max_retries + 1:
        progress.status = LessonProgress.Status.NEEDS_SUPPORT
    else:
        progress.status = LessonProgress.Status.IN_PROGRESS
    progress.save(update_fields=["best_score", "attempts_used", "status", "completed_at"])
    refresh_course_completion(attempt.enrollment, actor=teacher)

    GradeDecision.objects.update_or_create(
        attempt=attempt,
        defaults={
            "final_score": final_score,
            "status": GradeDecision.Status.CONFIRMED if getattr(attempt, "ai_grade", None) and final_score == attempt.ai_grade.suggested_score else GradeDecision.Status.OVERRIDDEN,
            "decided_by": teacher,
            "reason": reason,
        },
    )
    attempt.status = Attempt.Status.GRADED if passed else Attempt.Status.NEEDS_SUPPORT if attempts_used >= 3 else Attempt.Status.REMEDIATION
    attempt.save(update_fields=["status"])
    item.status = ReviewQueueItem.Status.RESOLVED
    item.assigned_to = teacher
    item.resolved_at = timezone.now()
    item.save(update_fields=["status", "assigned_to", "resolved_at"])
    if getattr(attempt, "ai_grade", None):
        attempt.ai_grade.teacher_review_required = False
        attempt.ai_grade.save(update_fields=["teacher_review_required"])

    Notification.objects.create(
        recipient=attempt.enrollment.student,
        notification_type="grade_confirmed",
        title="Your Python assessment was reviewed",
        body=f"Your teacher confirmed a score of {final_score}% for {attempt.question.lesson_version.title}.",
    )
    LearningEvent.objects.create(
        actor=attempt.enrollment.student,
        event_type="assessment_graded",
        entity_type="attempt",
        entity_id=attempt.id,
        metadata={"score": final_score, "passed": passed},
    )
    if passed and not XPEvent.objects.filter(student=attempt.enrollment.student, source_id=attempt.id).exists():
        XPEvent.objects.create(
            student=attempt.enrollment.student,
            enrollment=attempt.enrollment,
            event_type="assessment_passed",
            points=10,
            source_id=attempt.id,
        )
