from django.contrib import admin

from .models import AIJob, AIUsageEvent


@admin.register(AIJob)
class AIJobAdmin(admin.ModelAdmin):
    list_display = ("job_type", "entity_type", "entity_id", "status", "provider", "progress", "created_at")
    list_filter = ("job_type", "status", "provider")
    search_fields = ("entity_type", "entity_id", "provider", "model", "error_message")
    readonly_fields = ("id", "created_at")


@admin.register(AIUsageEvent)
class AIUsageEventAdmin(admin.ModelAdmin):
    list_display = ("job", "provider", "model", "input_tokens", "output_tokens", "estimated_cost", "created_at")
    list_filter = ("provider", "model")
    search_fields = ("job__entity_type", "provider", "model")
    readonly_fields = ("id", "created_at")
