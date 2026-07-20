from django.contrib import admin

from .models import Course, CourseVersion, FinalProject, Lesson, LessonArtifact, LessonFeedback, LessonVersion, Module, ProjectSubmission, Translation


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("title", "organization", "created_by", "status", "duration_weeks", "updated_at")
    list_filter = ("status", "organization")
    search_fields = ("title", "slug", "organization__name", "created_by__email")
    readonly_fields = ("id", "created_at", "updated_at")
    prepopulated_fields = {"slug": ("title",)}


@admin.register(CourseVersion)
class CourseVersionAdmin(admin.ModelAdmin):
    list_display = ("course", "version_number", "status", "generated_by_ai", "approved_by", "created_at")
    list_filter = ("status", "generated_by_ai")
    search_fields = ("course__title", "approved_by__email")
    readonly_fields = ("id", "created_at")


@admin.register(FinalProject)
class FinalProjectAdmin(admin.ModelAdmin):
    list_display = ("title", "course_version", "ai_generated", "teacher_approved", "estimated_hours", "updated_at")
    list_filter = ("ai_generated", "teacher_approved")
    search_fields = ("title", "brief", "course_version__course__title")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(ProjectSubmission)
class ProjectSubmissionAdmin(admin.ModelAdmin):
    list_display = ("final_project", "enrollment", "status", "suggested_score", "submitted_at", "reviewed_at")
    list_filter = ("status",)
    search_fields = ("final_project__title", "enrollment__student__email")
    readonly_fields = ("id", "submitted_at", "reviewed_at")


@admin.register(LessonFeedback)
class LessonFeedbackAdmin(admin.ModelAdmin):
    list_display = ("lesson_version", "enrollment", "rating", "updated_at")
    list_filter = ("rating",)
    search_fields = ("lesson_version__title", "enrollment__student__email", "comment")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ("title", "course_version", "position")
    search_fields = ("title", "course_version__course__title")
    readonly_fields = ("id",)


@admin.register(LessonVersion)
class LessonVersionAdmin(admin.ModelAdmin):
    list_display = ("title", "module", "position", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("title", "module__title", "module__course_version__course__title")
    readonly_fields = ("id", "created_at")


@admin.register(Lesson)
class LessonAdmin(LessonVersionAdmin):
    pass


@admin.register(LessonArtifact)
class LessonArtifactAdmin(admin.ModelAdmin):
    list_display = ("lesson_version", "artifact_type", "position", "is_active", "ai_generated", "teacher_approved")
    list_filter = ("artifact_type", "is_active", "ai_generated", "teacher_approved")
    search_fields = ("lesson_version__title", "content")
    readonly_fields = ("id",)


@admin.register(Translation)
class TranslationAdmin(admin.ModelAdmin):
    list_display = ("lesson_version", "language_code", "status")
    list_filter = ("language_code", "status")
    search_fields = ("lesson_version__title", "language_code")
    readonly_fields = ("id",)
