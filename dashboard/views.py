from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.http import HttpResponseForbidden
from django.shortcuts import render

from accounts.access import user_has_admin_access
from courses.models import Course
from enrollments.models import Enrollment
from organizations.models import Cohort, Membership, Organization


def accessible_administrator_organizations(user):
    if user.is_superuser:
        return Organization.objects.all()
    return Organization.objects.filter(
        memberships__user=user,
        memberships__role__in=[Membership.Role.OWNER, Membership.Role.ADMIN],
    ).distinct()


@login_required
def administrator_dashboard(request):
    if not user_has_admin_access(request.user):
        return HttpResponseForbidden("You do not have access to the administrator dashboard.")
    organizations = accessible_administrator_organizations(request.user)

    organizations = organizations.annotate(
        course_count=Count("courses", distinct=True),
        cohort_count=Count("cohorts", distinct=True),
        member_count=Count("memberships", distinct=True),
    ).order_by("name")
    organization_ids = organizations.values("id")
    context = {
        "organizations": organizations,
        "course_count": Course.objects.filter(organization_id__in=organization_ids).count(),
        "cohort_count": Cohort.objects.filter(organization_id__in=organization_ids).count(),
        "member_count": Membership.objects.filter(organization_id__in=organization_ids).count(),
        "enrollment_count": Enrollment.objects.filter(course__organization_id__in=organization_ids).count(),
    }
    return render(request, "dashboard/administrator.html", context)
