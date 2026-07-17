from django.contrib import admin

from .models import LearningEvent


@admin.register(LearningEvent)
class LearningEventAdmin(admin.ModelAdmin):
    list_display = ("actor", "event_type", "entity_type", "entity_id", "occurred_at")
    list_filter = ("event_type", "entity_type")
    search_fields = ("actor__email", "event_type", "entity_type", "entity_id")
    readonly_fields = ("id", "occurred_at")
