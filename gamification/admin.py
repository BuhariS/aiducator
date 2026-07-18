from django.contrib import admin

from .models import BadgeAward, PraiseNotification, StreakEvent, XPEvent


@admin.register(XPEvent)
class XPEventAdmin(admin.ModelAdmin):
    list_display = ("student", "enrollment", "event_type", "points", "source_id", "created_at")
    list_filter = ("event_type",)
    search_fields = ("student__email", "enrollment__course__title", "event_type")
    readonly_fields = ("id", "created_at")


@admin.register(BadgeAward)
class BadgeAwardAdmin(admin.ModelAdmin):
    list_display = ("student", "badge_key", "name", "awarded_at", "revoked_at")
    list_filter = ("badge_key", "revoked_at")
    search_fields = ("student__email", "badge_key", "name")
    readonly_fields = ("id", "awarded_at")


@admin.register(StreakEvent)
class StreakEventAdmin(admin.ModelAdmin):
    list_display = ("student", "event_date", "event_type", "streak_days", "created_at")
    list_filter = ("event_type", "event_date")
    search_fields = ("student__email",)
    readonly_fields = ("id", "created_at")


@admin.register(PraiseNotification)
class PraiseNotificationAdmin(admin.ModelAdmin):
    list_display = ("student", "event_type", "notification", "created_at")
    list_filter = ("event_type",)
    search_fields = ("student__email", "notification__body")
    readonly_fields = ("id", "created_at")
