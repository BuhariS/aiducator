from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from accounts.access import user_has_teacher_access
from analytics.models import LearningEvent
from enrollments.models import LessonProgress
from enrollments.services import refresh_course_completion
from gamification.services import record_learning_reward
from notifications.models import Notification

from .models import (
    Attempt,
    GradeDecision,
    GradeEvent,
    ManualReview,
    ReviewQueueItem,
)


def record_grade_event(attempt, event_type, *, actor=None, score=None, metadata=None):
    return GradeEvent.objects.create(
        attempt=attempt,
        event_type=event_type,
        actor=actor,
        score=score,
        metadata=metadata or {},
    )


@transaction.atomic
def queue_manual_review(attempt, reason, *, assigned_to=None):
    manual_review, _ = ManualReview.objects.update_or_create(
        attempt=attempt,
        defaults={
            "reason": reason,
            "status": ManualReview.Status.OPEN,
            "assigned_to": assigned_to,
            "resolution_note": "",
            "resolved_at": None,
        },
    )
    ReviewQueueItem.objects.update_or_create(
        attempt=attempt,
        defaults={
            "reason": reason[:120],
            "status": ReviewQueueItem.Status.OPEN,
            "assigned_to": assigned_to,
            "resolved_at": None,
        },
    )
    record_grade_event(attempt, GradeEvent.EventType.REVIEW_REQUESTED, metadata={"reason": reason})
    return manual_review


@transaction.atomic
def confirm_attempt_grade(attempt, final_score, *, actor=None, reason="", automatic=False):
    attempt = Attempt.objects.select_for_update().select_related(
        "question__lesson_version__module__course_version__course",
        "enrollment__student",
    ).get(pk=attempt.pk)
    course = attempt.question.lesson_version.module.course_version.course
    if actor is not None and not user_has_teacher_access(actor, course.organization):
        raise PermissionDenied("You do not have permission to confirm this grade.")
    if not 0 <= final_score <= 100:
        raise ValueError("Final score must be between 0 and 100.")

    previous_decision = GradeDecision.objects.filter(attempt=attempt).first()
    passed = final_score >= course.passing_score
    attempts_used = Attempt.objects.filter(
        enrollment=attempt.enrollment,
        question=attempt.question,
    ).count()
    progress, _ = LessonProgress.objects.get_or_create(
        enrollment=attempt.enrollment,
        lesson_version=attempt.question.lesson_version,
    )
    progress.best_score = max(progress.best_score or 0, final_score)
    progress.attempts_used = attempts_used
    if passed:
        progress.status = LessonProgress.Status.COMPLETED
        progress.completed_at = progress.completed_at or timezone.now()
    elif attempts_used >= course.max_retries + 1:
        progress.status = LessonProgress.Status.NEEDS_SUPPORT
    else:
        progress.status = LessonProgress.Status.IN_PROGRESS
    progress.save(update_fields=["best_score", "attempts_used", "status", "completed_at"])

    ai_grade = getattr(attempt, "ai_grade", None)
    ai_score = ai_grade.score if ai_grade and ai_grade.score else ai_grade.suggested_score if ai_grade else None
    status = (
        GradeDecision.Status.CONFIRMED
        if ai_grade and final_score == ai_score
        else GradeDecision.Status.OVERRIDDEN
    )
    GradeDecision.objects.update_or_create(
        attempt=attempt,
        defaults={
            "final_score": final_score,
            "status": status,
            "decided_by": actor,
            "reason": reason,
        },
    )
    attempt.status = (
        Attempt.Status.GRADED
        if passed
        else Attempt.Status.NEEDS_SUPPORT
        if attempts_used >= course.max_retries + 1
        else Attempt.Status.REMEDIATION
    )
    attempt.save(update_fields=["status"])

    manual_review = ManualReview.objects.filter(attempt=attempt).first()
    if manual_review:
        manual_review.status = ManualReview.Status.RESOLVED
        manual_review.assigned_to = actor or manual_review.assigned_to
        manual_review.resolution_note = reason
        manual_review.resolved_at = timezone.now()
        manual_review.save(update_fields=["status", "assigned_to", "resolution_note", "resolved_at"])
    legacy_review = ReviewQueueItem.objects.filter(attempt=attempt).first()
    if legacy_review:
        legacy_review.status = ReviewQueueItem.Status.RESOLVED
        legacy_review.assigned_to = actor or legacy_review.assigned_to
        legacy_review.resolved_at = timezone.now()
        legacy_review.save(update_fields=["status", "assigned_to", "resolved_at"])
    if ai_grade:
        ai_grade.requires_review = False
        ai_grade.teacher_review_required = False
        ai_grade.save(update_fields=["requires_review", "teacher_review_required"])

    progression_actor = actor or attempt.enrollment.student
    completion = refresh_course_completion(attempt.enrollment, actor=progression_actor)
    if passed:
        record_learning_reward(
            enrollment=attempt.enrollment,
            event_type="assessment_passed",
            source=attempt,
            points=10,
            reason="Confirmed assessment pass",
            praise=f"You passed {attempt.question.lesson_version.title} with {final_score}%.",
            badge_key="first_assessment",
            actor=actor,
        )
    if completion:
        record_learning_reward(
            enrollment=attempt.enrollment,
            event_type="course_completed",
            source=completion,
            points=50,
            reason="Completed every lesson in the course",
            praise=f"You completed {course.title}. Keep building your Python confidence!",
            badge_key="course_complete",
            actor=actor,
        )
    event_type = (
        GradeEvent.EventType.AUTO_CONFIRMED
        if automatic
        else GradeEvent.EventType.MANUALLY_CONFIRMED
        if status == GradeDecision.Status.CONFIRMED
        else GradeEvent.EventType.OVERRIDDEN
    )
    record_grade_event(
        attempt,
        event_type,
        actor=actor,
        score=final_score,
        metadata={"reason": reason, "passed": passed},
    )
    record_grade_event(
        attempt,
        GradeEvent.EventType.PROGRESSION_UPDATED,
        actor=actor,
        score=final_score,
        metadata={"passed": passed},
    )
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
        metadata={"score": final_score, "passed": passed, "automatic": automatic},
    )
    return GradeDecision.objects.get(attempt=attempt), previous_decision


def should_auto_confirm(attempt, grade):
    return (
        attempt.question.is_objective
        and grade.confidence >= settings.AI_AUTO_CONFIRM_MIN_CONFIDENCE
        and not grade.requires_review
        and grade.recommended_action in {"advance", "remediate"}
    )
