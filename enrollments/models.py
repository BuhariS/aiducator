import uuid

from django.conf import settings
from django.db import models

from courses.models import Course, CourseVersion, LessonVersion
from organizations.models import Cohort


class Enrollment(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        COMPLETED = "completed", "Completed"
        PAUSED = "paused", "Paused"
        WITHDRAWN = "withdrawn", "Withdrawn"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name="enrollments")
    course_version = models.ForeignKey(CourseVersion, on_delete=models.PROTECT, related_name="enrollments")
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="enrollments")
    cohort = models.ForeignKey(Cohort, on_delete=models.SET_NULL, null=True, blank=True, related_name="enrollments")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    enrolled_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["course", "student"], name="unique_course_enrollment")]


class LessonProgress(models.Model):
    class Status(models.TextChoices):
        NOT_STARTED = "not_started", "Not started"
        IN_PROGRESS = "in_progress", "In progress"
        NEEDS_SUPPORT = "needs_support", "Needs teacher support"
        COMPLETED = "completed", "Completed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    enrollment = models.ForeignKey(Enrollment, on_delete=models.CASCADE, related_name="lesson_progress")
    lesson_version = models.ForeignKey(LessonVersion, on_delete=models.PROTECT, related_name="progress_records")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NOT_STARTED)
    best_score = models.PositiveSmallIntegerField(null=True, blank=True)
    attempts_used = models.PositiveSmallIntegerField(default=0)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["enrollment", "lesson_version"], name="unique_lesson_progress")]


class StudentProgress(LessonProgress):
    class Meta:
        proxy = True
        verbose_name = "Student progress"
        verbose_name_plural = "Student progress"


class CourseCompletion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    enrollment = models.OneToOneField(Enrollment, on_delete=models.CASCADE, related_name="completion")
    completed_at = models.DateTimeField(auto_now_add=True)
    confirmed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="confirmed_completions")
