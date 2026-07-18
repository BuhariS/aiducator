import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify

from organizations.models import Organization


class Course(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        IN_REVIEW = "in_review", "In review"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="courses")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_courses")
    title = models.CharField(max_length=180)
    slug = models.SlugField(max_length=190, unique=True)
    description = models.TextField(blank=True)
    duration_weeks = models.PositiveSmallIntegerField(default=12)
    passing_score = models.PositiveSmallIntegerField(default=70)
    max_retries = models.PositiveSmallIntegerField(default=2)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class CourseVersion(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        IN_REVIEW = "in_review", "In review"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="versions")
    version_number = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    generated_by_ai = models.BooleanField(default=False)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="approved_course_versions")
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["course", "version_number"], name="unique_course_version")]
        ordering = ["course", "-version_number"]

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk, status=self.Status.PUBLISHED).exists():
            raise ValidationError("Published course versions are immutable.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.status == self.Status.PUBLISHED:
            raise ValidationError("Published course versions are immutable.")
        return super().delete(*args, **kwargs)


class FinalProject(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course_version = models.OneToOneField(
        CourseVersion,
        on_delete=models.CASCADE,
        related_name="final_project",
    )
    title = models.CharField(max_length=180)
    brief = models.TextField()
    objectives = models.JSONField(default=list)
    requirements = models.JSONField(default=list)
    deliverables = models.JSONField(default=list)
    rubric = models.JSONField(default=list)
    estimated_hours = models.PositiveSmallIntegerField(default=8)
    ai_generated = models.BooleanField(default=False)
    teacher_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if self.course_version.status == CourseVersion.Status.PUBLISHED:
            raise ValidationError("Final projects in published course versions are immutable.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.course_version.status == CourseVersion.Status.PUBLISHED:
            raise ValidationError("Final projects in published course versions are immutable.")
        return super().delete(*args, **kwargs)


class Module(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course_version = models.ForeignKey(CourseVersion, on_delete=models.CASCADE, related_name="modules")
    title = models.CharField(max_length=180)
    position = models.PositiveIntegerField()

    class Meta:
        ordering = ["position"]
        constraints = [models.UniqueConstraint(fields=["course_version", "position"], name="unique_module_position")]

    def save(self, *args, **kwargs):
        if self.course_version.status == CourseVersion.Status.PUBLISHED:
            raise ValidationError("Modules in published course versions are immutable.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.course_version.status == CourseVersion.Status.PUBLISHED:
            raise ValidationError("Modules in published course versions are immutable.")
        return super().delete(*args, **kwargs)


class LessonVersion(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name="lessons")
    title = models.CharField(max_length=180)
    objectives = models.JSONField(default=list)
    content = models.TextField()
    position = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["position"]
        constraints = [models.UniqueConstraint(fields=["module", "position"], name="unique_lesson_position")]

    def save(self, *args, **kwargs):
        if self.module.course_version.status == CourseVersion.Status.PUBLISHED:
            raise ValidationError("Lessons in published course versions are immutable.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.module.course_version.status == CourseVersion.Status.PUBLISHED:
            raise ValidationError("Lessons in published course versions are immutable.")
        return super().delete(*args, **kwargs)


class Lesson(LessonVersion):
    class Meta:
        proxy = True
        verbose_name = "Lesson"
        verbose_name_plural = "Lessons"


class LessonArtifact(models.Model):
    class ArtifactType(models.TextChoices):
        TEXT = "text", "Text"
        VIDEO = "video_embed", "Video embed"
        IMAGE = "image", "Image"
        SIMULATION = "simulation_link", "Simulation link"
        CODE = "code_example", "Code example"
        IMAGE_PROMPT = "image_prompt", "Image prompt"
        YOUTUBE_SEARCH = "youtube_search", "YouTube search suggestion"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lesson_version = models.ForeignKey(LessonVersion, on_delete=models.CASCADE, related_name="artifacts")
    artifact_type = models.CharField(max_length=30, choices=ArtifactType.choices)
    content = models.TextField()
    asset = models.FileField(upload_to="lesson-artifacts/", blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position"]

    def save(self, *args, **kwargs):
        if self.lesson_version.module.course_version.status == CourseVersion.Status.PUBLISHED:
            raise ValidationError("Artifacts in published course versions are immutable.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.lesson_version.module.course_version.status == CourseVersion.Status.PUBLISHED:
            raise ValidationError("Artifacts in published course versions are immutable.")
        return super().delete(*args, **kwargs)


class Translation(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        APPROVED = "approved", "Approved"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lesson_version = models.ForeignKey(LessonVersion, on_delete=models.CASCADE, related_name="translations")
    language_code = models.CharField(max_length=12)
    content = models.JSONField(default=dict)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["lesson_version", "language_code"], name="unique_lesson_translation")]

    def save(self, *args, **kwargs):
        if self.lesson_version.module.course_version.status == CourseVersion.Status.PUBLISHED:
            raise ValidationError("Translations in published course versions are immutable.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.lesson_version.module.course_version.status == CourseVersion.Status.PUBLISHED:
            raise ValidationError("Translations in published course versions are immutable.")
        return super().delete(*args, **kwargs)
