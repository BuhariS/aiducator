from django.contrib import admin

from .models import AuditEvent, LearningEvent, LessonTimeEvent


@admin.register(LearningEvent)
class LearningEventAdmin(admin.ModelAdmin):
    list_display = ("actor", "event_type", "entity_type", "entity_id", "occurred_at")
    list_filter = ("event_type", "entity_type")
    search_fields = ("actor__email", "event_type", "entity_type", "entity_id")
    readonly_fields = ("id", "occurred_at")


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ("action", "actor", "entity_type", "entity_id", "created_at")
    list_filter = ("action", "entity_type")
    search_fields = ("action", "entity_type", "actor__email")
    readonly_fields = (
        "id",
        "actor",
        "action",
        "entity_type",
        "entity_id",
        "ip_hash",
        "metadata",
        "created_at",
    )


@admin.register(LessonTimeEvent)
class LessonTimeEventAdmin(admin.ModelAdmin):
    list_display = ("student", "lesson", "duration_seconds", "recorded_at")
    list_filter = ("recorded_at",)
    search_fields = ("student__email", "lesson__title")
    readonly_fields = (
        "id",
        "student",
        "enrollment",
        "lesson",
        "duration_seconds",
        "recorded_at",
        "metadata",
    )
