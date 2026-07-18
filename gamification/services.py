from datetime import timedelta

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from accounts.access import user_has_teacher_access
from analytics.models import LearningEvent
from notifications.models import Notification

from .models import BadgeAward, PraiseNotification, StreakEvent, XPEvent


BADGES = {
    "first_lesson": ("First Lesson", "Completed your first lesson."),
    "first_assessment": ("First Assessment", "Passed your first assessment."),
    "course_complete": ("Course Finisher", "Completed every lesson in a course."),
}


@transaction.atomic
def award_xp(*, student, enrollment, event_type, points, reason, source=None, actor=None, metadata=None):
    source_id = getattr(source, "pk", source)
    if source_id:
        existing = XPEvent.objects.filter(
            student=student,
            event_type=event_type,
            source_id=source_id,
        ).first()
        if existing:
            return existing
    event = XPEvent.objects.create(
        student=student,
        enrollment=enrollment,
        event_type=event_type,
        points=points,
        source_id=source_id,
        reason=reason,
        metadata=metadata or {},
        created_by=actor,
    )
    LearningEvent.objects.create(
        actor=student,
        event_type="xp_awarded",
        entity_type="xp_event",
        entity_id=event.id,
        metadata={"event_type": event_type, "points": points, "reason": reason},
    )
    return event


@transaction.atomic
def correct_xp(original_event, *, points, reason, actor):
    if not reason.strip():
        raise ValueError("An XP correction requires a reason.")
    if not user_has_teacher_access(actor, original_event.enrollment.course.organization):
        raise PermissionDenied("You do not have permission to correct this XP event.")
    correction = XPEvent.objects.create(
        student=original_event.student,
        enrollment=original_event.enrollment,
        event_type="correction",
        points=points,
        source_id=original_event.source_id,
        reason=reason,
        correction_for=original_event,
        created_by=actor,
    )
    LearningEvent.objects.create(
        actor=actor,
        event_type="xp_corrected",
        entity_type="xp_event",
        entity_id=correction.id,
        metadata={"original_event_id": str(original_event.id), "points": points, "reason": reason},
    )
    return correction


@transaction.atomic
def record_streak(*, student, enrollment, source=None, metadata=None):
    today = timezone.localdate()
    existing = StreakEvent.objects.filter(student=student, event_date=today).first()
    if existing:
        return existing
    previous = StreakEvent.objects.filter(student=student).order_by("-event_date").first()
    if previous and previous.event_date == today - timedelta(days=1):
        event_type = StreakEvent.EventType.CONTINUED
        streak_days = previous.streak_days + 1
    elif previous:
        event_type = StreakEvent.EventType.BROKEN
        streak_days = 1
    else:
        event_type = StreakEvent.EventType.STARTED
        streak_days = 1
    return StreakEvent.objects.create(
        student=student,
        enrollment=enrollment,
        event_type=event_type,
        event_date=today,
        streak_days=streak_days,
        source_id=getattr(source, "pk", source),
        metadata=metadata or {},
    )


@transaction.atomic
def award_badge(*, student, badge_key, source=None, metadata=None):
    if badge_key not in BADGES:
        raise ValueError(f"Unknown badge key: {badge_key}")
    name, description = BADGES[badge_key]
    badge, _ = BadgeAward.objects.get_or_create(
        student=student,
        badge_key=badge_key,
        defaults={
            "name": name,
            "description": description,
            "source_id": getattr(source, "pk", source),
            "metadata": metadata or {},
        },
    )
    return badge


@transaction.atomic
def praise_student(*, student, enrollment, event_type, message, source=None):
    source_id = getattr(source, "pk", source)
    if source_id:
        existing = PraiseNotification.objects.filter(
            student=student,
            event_type=event_type,
            source_id=source_id,
        ).first()
        if existing:
            return existing
    notification = Notification.objects.create(
        recipient=student,
        notification_type="praise",
        title="Great work!",
        body=message,
    )
    return PraiseNotification.objects.create(
        student=student,
        enrollment=enrollment,
        notification=notification,
        event_type=event_type,
        source_id=source_id,
    )


@transaction.atomic
def record_learning_reward(*, enrollment, event_type, source, points, reason, praise, badge_key=None, actor=None):
    student = enrollment.student
    xp_event = award_xp(
        student=student,
        enrollment=enrollment,
        event_type=event_type,
        points=points,
        reason=reason,
        source=source,
        actor=actor,
    )
    streak = record_streak(student=student, enrollment=enrollment, source=source)
    praise_event = praise_student(
        student=student,
        enrollment=enrollment,
        event_type=event_type,
        message=praise,
        source=source,
    )
    badge = award_badge(student=student, badge_key=badge_key, source=source) if badge_key else None
    return {"xp": xp_event, "streak": streak, "praise": praise_event, "badge": badge}
