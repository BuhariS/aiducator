from django.contrib import admin

from .models import AuditEvent, LearningEvent


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
    readonly_fields = ("id", "actor", "action", "entity_type", "entity_id", "ip_hash", "metadata", "created_at")
