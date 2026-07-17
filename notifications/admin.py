from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("recipient", "notification_type", "title", "read_at", "created_at")
    list_filter = ("notification_type", "read_at")
    search_fields = ("recipient__email", "title", "body")
    readonly_fields = ("id", "created_at")
