import uuid

from django.conf import settings
from django.db import models

from enrollments.models import Enrollment


class XPEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="xp_events")
    enrollment = models.ForeignKey(Enrollment, on_delete=models.PROTECT, related_name="xp_events")
    event_type = models.CharField(max_length=60)
    points = models.IntegerField()
    source_id = models.UUIDField(null=True, blank=True)
    reason = models.CharField(max_length=255, default="Legacy XP award")
    metadata = models.JSONField(default=dict, blank=True)
    correction_for = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="corrections",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_xp_events",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError("XP events are immutable records.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("XP events are immutable records.")


class BadgeAward(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="badge_awards")
    badge_key = models.CharField(max_length=80)
    name = models.CharField(max_length=120)
    description = models.TextField()
    source_id = models.UUIDField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    awarded_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["student", "badge_key"], name="unique_student_badge")]


class StreakEvent(models.Model):
    class EventType(models.TextChoices):
        STARTED = "started", "Streak started"
        CONTINUED = "continued", "Streak continued"
        BROKEN = "broken", "Streak broken"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="streak_events")
    enrollment = models.ForeignKey(Enrollment, on_delete=models.PROTECT, related_name="streak_events")
    event_type = models.CharField(max_length=20, choices=EventType.choices)
    event_date = models.DateField()
    streak_days = models.PositiveIntegerField(default=1)
    source_id = models.UUIDField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["student", "event_date"], name="unique_student_streak_day")]


class PraiseNotification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="praise_notifications")
    enrollment = models.ForeignKey(Enrollment, on_delete=models.PROTECT, related_name="praise_notifications")
    notification = models.OneToOneField(
        "notifications.Notification",
        on_delete=models.PROTECT,
        related_name="praise_event",
    )
    event_type = models.CharField(max_length=60)
    source_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
