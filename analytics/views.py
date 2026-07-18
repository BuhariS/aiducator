from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST

from accounts.access import user_has_admin_access, user_is_teacher
from courses.models import LessonVersion
from dashboard.views import accessible_administrator_organizations
from enrollments.models import Enrollment

from .services import administrator_analytics, record_lesson_time, teacher_analytics


@login_required
def teacher_analytics_view(request):
    if not user_is_teacher(request.user):
        return HttpResponseForbidden("You do not have access to teacher analytics.")
    return render(
        request, "analytics/teacher.html", {"course_metrics": teacher_analytics(request.user)}
    )


@login_required
def administrator_analytics_view(request):
    if not user_has_admin_access(request.user):
        return HttpResponseForbidden("You do not have access to administrator analytics.")
    organizations = accessible_administrator_organizations(request.user)
    return render(
        request,
        "analytics/administrator.html",
        {"metrics": administrator_analytics(organizations)},
    )


@login_required
@require_POST
@csrf_protect
def record_lesson_time_view(request, lesson_id):
    lesson = get_object_or_404(LessonVersion, id=lesson_id)
    enrollment = get_object_or_404(
        Enrollment,
        student=request.user,
        course_version=lesson.module.course_version,
        status=Enrollment.Status.ACTIVE,
    )
    try:
        duration_seconds = int(request.POST.get("duration_seconds", "0"))
        record_lesson_time(
            student=request.user,
            enrollment=enrollment,
            lesson=lesson,
            duration_seconds=duration_seconds,
        )
    except (TypeError, ValueError, ValidationError):
        return JsonResponse({"error": "Invalid duration."}, status=400)
    return JsonResponse({"status": "recorded"})
