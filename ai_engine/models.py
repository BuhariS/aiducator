import uuid

from django.conf import settings
from django.db import models


class AIJob(models.Model):
    class JobType(models.TextChoices):
        COURSE_GENERATION = "course_generation", "Course generation"
        GRADING = "grading", "Grading"
        TRANSLATION = "translation", "Translation"

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job_type = models.CharField(max_length=30, choices=JobType.choices)
    entity_type = models.CharField(max_length=80)
    entity_id = models.UUIDField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.QUEUED)
    progress = models.PositiveSmallIntegerField(default=0)
    retry_count = models.PositiveSmallIntegerField(default=0)
    error_message = models.TextField(blank=True)
    provider = models.CharField(max_length=40, blank=True)
    model = models.CharField(max_length=100, blank=True)
    prompt_version = models.CharField(max_length=40, blank=True)
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    estimated_cost = models.DecimalField(max_digits=12, decimal_places=6, default=0)
    error_details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)


class CourseGenerationRequest(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        REVIEW = "review", "Ready for teacher review"
        FAILED = "failed", "Failed"
        PUBLISHED = "published", "Published"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="course_generation_requests",
    )
    course = models.ForeignKey(
        "courses.Course",
        on_delete=models.CASCADE,
        related_name="generation_requests",
    )
    generated_version = models.OneToOneField(
        "courses.CourseVersion",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="generation_request",
    )
    title = models.CharField(max_length=180)
    objective = models.TextField(blank=True)
    duration_weeks = models.PositiveSmallIntegerField(default=12)
    audience = models.CharField(max_length=180, blank=True)
    free_prompt = models.TextField(blank=True)
    translation_languages = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.QUEUED)
    error_details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]


class AIUsageEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(AIJob, on_delete=models.CASCADE, related_name="usage_events")
    provider = models.CharField(max_length=40)
    model = models.CharField(max_length=100)
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    estimated_cost = models.DecimalField(max_digits=12, decimal_places=6, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
