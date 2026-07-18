import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from courses.models import LessonVersion
from courses.models import Course
from enrollments.models import Enrollment


class Question(models.Model):
    class QuestionType(models.TextChoices):
        EXPLANATION = "explanation", "Explanation"
        CODE_WRITING = "code_writing", "Code writing"
        DEBUGGING = "debugging", "Debugging"
        REFLECTION = "reflection", "Reflection"
        SCENARIO = "scenario", "Scenario-based"
        CRITICAL_THINKING = "critical_thinking", "Critical thinking"
        TASK_PROMPT = "task_prompt", "Task prompt generation"
        MISCONCEPTION = "misconception", "Common misconception"
        ERROR_IDENTIFICATION = "error_identification", "Identify the mistakes"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lesson_version = models.ForeignKey(LessonVersion, on_delete=models.CASCADE, related_name="questions")
    question_type = models.CharField(max_length=20, choices=QuestionType.choices)
    prompt = models.TextField()
    max_score = models.PositiveSmallIntegerField(default=100)
    position = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["position"]

    def save(self, *args, **kwargs):
        if self.lesson_version.module.course_version.status == "published":
            raise ValidationError("Questions in published course versions are immutable.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.lesson_version.module.course_version.status == "published":
            raise ValidationError("Questions in published course versions are immutable.")
        return super().delete(*args, **kwargs)


class RubricVersion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="rubrics")
    version_number = models.PositiveIntegerField(default=1)
    criteria = models.JSONField(default=list)
    total_score = models.PositiveSmallIntegerField(default=100)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="approved_rubrics")
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["question", "version_number"], name="unique_rubric_version")]

    def save(self, *args, **kwargs):
        if self.question.lesson_version.module.course_version.status == "published":
            raise ValidationError("Rubrics in published course versions are immutable.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.question.lesson_version.module.course_version.status == "published":
            raise ValidationError("Rubrics in published course versions are immutable.")
        return super().delete(*args, **kwargs)


class Attempt(models.Model):
    class Status(models.TextChoices):
        SUBMITTED = "submitted", "Submitted"
        EVALUATING = "evaluating", "Evaluating"
        AWAITING_REVIEW = "awaiting_review", "Awaiting review"
        GRADED = "graded", "Graded"
        REMEDIATION = "remediation", "Remediation"
        NEEDS_SUPPORT = "needs_support", "Needs teacher support"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    enrollment = models.ForeignKey(Enrollment, on_delete=models.PROTECT, related_name="attempts")
    question = models.ForeignKey(Question, on_delete=models.PROTECT, related_name="attempts")
    attempt_number = models.PositiveSmallIntegerField()
    answer_text = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SUBMITTED)
    submitted_at = models.DateTimeField(auto_now_add=True)
    evaluated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["enrollment", "question", "attempt_number"], name="unique_attempt_number"),
            models.CheckConstraint(check=models.Q(attempt_number__gte=1, attempt_number__lte=3), name="attempt_number_range"),
        ]
        ordering = ["attempt_number"]


class AIGrade(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    attempt = models.OneToOneField(Attempt, on_delete=models.CASCADE, related_name="ai_grade")
    suggested_score = models.PositiveSmallIntegerField()
    confidence = models.DecimalField(max_digits=4, decimal_places=3)
    strengths = models.JSONField(default=list)
    mistakes = models.JSONField(default=list)
    feedback = models.TextField()
    remediation = models.TextField(blank=True)
    teacher_review_required = models.BooleanField(default=True)
    provider = models.CharField(max_length=40, blank=True)
    model = models.CharField(max_length=100, blank=True)
    prompt_version = models.CharField(max_length=40, blank=True)
    raw_response = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(check=models.Q(suggested_score__lte=100), name="ai_score_range"),
            models.CheckConstraint(check=models.Q(confidence__gte=0, confidence__lte=1), name="ai_confidence_range"),
        ]


class GradeDecision(models.Model):
    class Status(models.TextChoices):
        PROVISIONAL = "provisional", "Provisional"
        CONFIRMED = "confirmed", "Confirmed"
        OVERRIDDEN = "overridden", "Overridden"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    attempt = models.OneToOneField(Attempt, on_delete=models.CASCADE, related_name="grade_decision")
    final_score = models.PositiveSmallIntegerField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PROVISIONAL)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="grade_decisions")
    reason = models.TextField(blank=True)
    decided_at = models.DateTimeField(auto_now_add=True)


class ReviewQueueItem(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        RESOLVED = "resolved", "Resolved"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    attempt = models.OneToOneField(Attempt, on_delete=models.CASCADE, related_name="review_item")
    reason = models.CharField(max_length=120)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_reviews")
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)


class AccommodationRequest(models.Model):
    class AccommodationType(models.TextChoices):
        COPY_PASTE = "copy_paste", "Copy and paste assistance"
        EXTENDED_TIME = "extended_time", "Extended assessment time"
        SCREEN_READER = "screen_reader", "Screen reader support"
        OTHER = "other", "Other accommodation"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        DECLINED = "declined", "Declined"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="accommodation_requests")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="accommodation_requests")
    accommodation_type = models.CharField(max_length=30, choices=AccommodationType.choices)
    details = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="reviewed_accommodations")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
