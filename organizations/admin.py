from django.contrib import admin

from .models import Cohort, Membership, Organization


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "created_at")
    search_fields = ("name", "slug")
    readonly_fields = ("id", "created_at")


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("organization", "user", "role", "created_at")
    list_filter = ("role", "organization")
    search_fields = ("organization__name", "user__email", "user__first_name", "user__last_name")
    readonly_fields = ("id", "created_at")


@admin.register(Cohort)
class CohortAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "teacher", "start_date", "end_date")
    list_filter = ("organization",)
    search_fields = ("name", "organization__name", "teacher__email")
    readonly_fields = ("id", "created_at")
