from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from accounts.access import user_has_teacher_access
from gamification.services import record_learning_reward

from .models import CourseCompletion, Enrollment, LessonProgress


def _can_change_progress(enrollment, actor):
    if actor.id == enrollment.student_id:
        return True
    return user_has_teacher_access(actor, enrollment.course.organization)


@transaction.atomic
def mark_lesson_complete(enrollment, lesson, *, actor):
    if not _can_change_progress(enrollment, actor):
        raise PermissionDenied("You do not have permission to update this learner's progress.")
    if lesson.module.course_version_id != enrollment.course_version_id:
        raise PermissionDenied("This lesson does not belong to the enrolled course version.")
    if lesson.questions.filter(is_active=True).exists():
        raise ValidationError("Complete the lesson assessment before marking this lesson complete.")
    progress, _ = LessonProgress.objects.get_or_create(
        enrollment=enrollment,
        lesson_version=lesson,
    )
    progress.status = LessonProgress.Status.COMPLETED
    progress.completed_at = progress.completed_at or timezone.now()
    progress.save(update_fields=["status", "completed_at"])
    record_learning_reward(
        enrollment=enrollment,
        event_type="lesson_completed",
        source=progress,
        points=5,
        reason="Completed lesson content",
        praise=f"You completed {lesson.title}.",
        badge_key="first_lesson",
        actor=actor,
    )
    completion = refresh_course_completion(enrollment, actor=actor)
    if completion:
        record_learning_reward(
            enrollment=enrollment,
            event_type="course_completed",
            source=completion,
            points=50,
            reason="Completed every lesson in the course",
            praise=f"You completed {enrollment.course.title}. Keep building your Python confidence!",
            badge_key="course_complete",
            actor=actor,
        )
    return progress


@transaction.atomic
def refresh_course_completion(enrollment, *, actor):
    if not _can_change_progress(enrollment, actor):
        raise PermissionDenied("You do not have permission to update this learner's completion.")
    lesson_ids = set(
        enrollment.course_version.modules.values_list("lessons__id", flat=True)
    )
    if not lesson_ids:
        return None
    completed_ids = set(
        enrollment.lesson_progress.filter(
            status=LessonProgress.Status.COMPLETED,
            lesson_version_id__in=lesson_ids,
        ).values_list("lesson_version_id", flat=True)
    )
    if completed_ids != lesson_ids:
        return None
    completion, _ = CourseCompletion.objects.get_or_create(
        enrollment=enrollment,
        defaults={"confirmed_by": actor},
    )
    return completion
