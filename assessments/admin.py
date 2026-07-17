from django.contrib import admin

from .models import AIGrade, Attempt, GradeDecision, Question, ReviewQueueItem, RubricVersion


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("prompt", "lesson_version", "question_type", "max_score", "position", "is_active")
    list_filter = ("question_type", "is_active")
    search_fields = ("prompt", "lesson_version__title", "lesson_version__module__course_version__course__title")
    readonly_fields = ("id",)


@admin.register(RubricVersion)
class RubricVersionAdmin(admin.ModelAdmin):
    list_display = ("question", "version_number", "total_score", "approved_by", "approved_at")
    search_fields = ("question__prompt", "approved_by__email")
    readonly_fields = ("id", "created_at")


@admin.register(Attempt)
class AttemptAdmin(admin.ModelAdmin):
    list_display = ("enrollment", "question", "attempt_number", "status", "submitted_at", "evaluated_at")
    list_filter = ("status",)
    search_fields = ("enrollment__student__email", "question__prompt", "answer_text")
    readonly_fields = ("id", "submitted_at")


@admin.register(AIGrade)
class AIGradeAdmin(admin.ModelAdmin):
    list_display = ("attempt", "suggested_score", "confidence", "provider", "teacher_review_required", "created_at")
    list_filter = ("teacher_review_required", "provider")
    search_fields = ("attempt__enrollment__student__email", "attempt__question__prompt", "feedback")
    readonly_fields = ("id", "created_at")


@admin.register(GradeDecision)
class GradeDecisionAdmin(admin.ModelAdmin):
    list_display = ("attempt", "final_score", "status", "decided_by", "decided_at")
    list_filter = ("status",)
    search_fields = ("attempt__enrollment__student__email", "decided_by__email", "reason")
    readonly_fields = ("id", "decided_at")


@admin.register(ReviewQueueItem)
class ReviewQueueItemAdmin(admin.ModelAdmin):
    list_display = ("attempt", "status", "assigned_to", "reason", "created_at", "resolved_at")
    list_filter = ("status",)
    search_fields = ("attempt__enrollment__student__email", "assigned_to__email", "reason")
    readonly_fields = ("id", "created_at")
