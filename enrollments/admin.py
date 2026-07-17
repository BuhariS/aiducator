from django.contrib import admin

from .models import CourseCompletion, Enrollment, LessonProgress, StudentProgress


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ("student", "course", "course_version", "status", "enrolled_at")
    list_filter = ("status", "course")
    search_fields = ("student__email", "student__first_name", "course__title")
    readonly_fields = ("id", "enrolled_at")


@admin.register(LessonProgress)
class LessonProgressAdmin(admin.ModelAdmin):
    list_display = ("enrollment", "lesson_version", "status", "best_score", "attempts_used")
    list_filter = ("status",)
    search_fields = ("enrollment__student__email", "lesson_version__title")
    readonly_fields = ("id",)


@admin.register(StudentProgress)
class StudentProgressAdmin(LessonProgressAdmin):
    pass


@admin.register(CourseCompletion)
class CourseCompletionAdmin(admin.ModelAdmin):
    list_display = ("enrollment", "confirmed_by", "completed_at")
    search_fields = ("enrollment__student__email", "enrollment__course__title", "confirmed_by__email")
    readonly_fields = ("id", "completed_at")
