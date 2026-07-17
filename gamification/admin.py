from django.contrib import admin

from .models import XPEvent


@admin.register(XPEvent)
class XPEventAdmin(admin.ModelAdmin):
    list_display = ("student", "enrollment", "event_type", "points", "source_id", "created_at")
    list_filter = ("event_type",)
    search_fields = ("student__email", "enrollment__course__title", "event_type")
    readonly_fields = ("id", "created_at")
