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
    created_at = models.DateTimeField(auto_now_add=True)
