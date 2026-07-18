from collections import Counter
from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Avg, Q, Sum
from django.utils import timezone

from accounts.models import User
from ai_engine.models import AIJob, AIUsageEvent, CourseGenerationRequest
from assessments.models import AIGrade, Attempt, GradeDecision, ManualReview, ReviewQueueItem
from courses.models import Course, LessonVersion
from enrollments.models import CourseCompletion, Enrollment, LessonProgress

from .models import LearningEvent, LessonTimeEvent


def _percentage(numerator, denominator):
    return round((numerator / denominator) * 100, 1) if denominator else 0


def record_lesson_time(*, student, enrollment, lesson, duration_seconds, metadata=None):
    if enrollment.student_id != student.id:
        raise PermissionDenied("You can only record your own lesson time.")
    if lesson.module.course_version_id != enrollment.course_version_id:
        raise PermissionDenied("This lesson is not part of the enrolled course version.")
    if not 1 <= duration_seconds <= 3_600:
        raise ValidationError("Lesson time must be between 1 second and 1 hour.")
    event = LessonTimeEvent.objects.create(
        student=student,
        enrollment=enrollment,
        lesson=lesson,
        duration_seconds=duration_seconds,
        metadata=metadata or {},
    )
    LearningEvent.objects.create(
        actor=student,
        event_type="lesson_time_recorded",
        entity_type="lesson",
        entity_id=lesson.id,
        metadata={"duration_seconds": duration_seconds},
    )
    return event


def teacher_course_metrics(course):
    enrollments = Enrollment.objects.filter(course=course)
    enrollment_count = enrollments.count()
    completed_count = CourseCompletion.objects.filter(enrollment__in=enrollments).count()
    decisions = GradeDecision.objects.filter(attempt__enrollment__in=enrollments)
    average_score = decisions.aggregate(value=Avg("final_score"))["value"] or 0
    passed_count = decisions.filter(final_score__gte=course.passing_score).count()
    needing_help = enrollments.filter(
        Q(lesson_progress__status=LessonProgress.Status.NEEDS_SUPPORT)
        | Q(attempts__status__in=["needs_support", "remediation"])
    ).distinct()
    overridden_count = decisions.filter(status=GradeDecision.Status.OVERRIDDEN).count()

    mistakes = Counter()
    for errors in AIGrade.objects.filter(attempt__enrollment__in=enrollments).values_list(
        "errors", flat=True
    ):
        for error in errors or []:
            label = str(error).strip()
            if label:
                mistakes[label] += 1

    disparities = []
    for ai_score, final_score in AIGrade.objects.filter(
        attempt__enrollment__in=enrollments,
        attempt__grade_decision__isnull=False,
    ).values_list("suggested_score", "attempt__grade_decision__final_score"):
        disparities.append(abs(ai_score - final_score))

    lessons = list(
        LessonVersion.objects.filter(module__course_version__course=course)
        .order_by("module__position", "position")
        .values("id", "title")
    )
    lesson_metrics = []
    for lesson in lessons:
        progress = LessonProgress.objects.filter(
            enrollment__in=enrollments, lesson_version_id=lesson["id"]
        )
        started = progress.exclude(status=LessonProgress.Status.NOT_STARTED).count()
        completed = progress.filter(status=LessonProgress.Status.COMPLETED).count()
        seconds = (
            LessonTimeEvent.objects.filter(
                enrollment__in=enrollments,
                lesson_id=lesson["id"],
            ).aggregate(value=Sum("duration_seconds"))["value"]
            or 0
        )
        lesson_metrics.append(
            {
                "title": lesson["title"],
                "started": started,
                "completed": completed,
                "dropoff_rate": round(100 - _percentage(completed, started), 1) if started else 0,
                "minutes": round(seconds / 60, 1),
            }
        )

    return {
        "course": course,
        "completion_rate": _percentage(completed_count, enrollment_count),
        "enrollment_count": enrollment_count,
        "assessment_average": round(float(average_score), 1),
        "assessment_pass_rate": _percentage(passed_count, decisions.count()),
        "common_mistakes": mistakes.most_common(5),
        "students_needing_help": list(needing_help.select_related("student")),
        "ai_overridden": overridden_count,
        "ai_human_gap": round(sum(disparities) / len(disparities), 1) if disparities else 0,
        "lesson_metrics": lesson_metrics,
    }


def teacher_analytics(user):
    courses = Course.objects.filter(created_by=user).order_by("title")
    return [teacher_course_metrics(course) for course in courses]


def administrator_analytics(organizations):
    organization_ids = organizations.values("id")
    courses = Course.objects.filter(organization_id__in=organization_ids)
    enrollments = Enrollment.objects.filter(course__organization_id__in=organization_ids)
    generation_ids = CourseGenerationRequest.objects.filter(
        course__organization_id__in=organization_ids,
    ).values("id")
    attempt_ids = Attempt.objects.filter(
        enrollment__course__organization_id__in=organization_ids,
    ).values("id")
    jobs = AIJob.objects.filter(
        Q(entity_type="course_generation_request", entity_id__in=generation_ids)
        | Q(entity_type="attempt", entity_id__in=attempt_ids)
    )
    total_jobs = jobs.count()
    failed_jobs = jobs.filter(status=AIJob.Status.FAILED).count()
    usage = AIUsageEvent.objects.filter(job__in=jobs).aggregate(
        input_tokens=Sum("input_tokens"),
        output_tokens=Sum("output_tokens"),
        estimated_cost=Sum("estimated_cost"),
    )
    review_volume = ManualReview.objects.filter(
        attempt__enrollment__course__organization_id__in=organization_ids
    ).count()
    open_reviews = ReviewQueueItem.objects.filter(
        attempt__enrollment__course__organization_id__in=organization_ids,
        status=ReviewQueueItem.Status.OPEN,
    ).count()
    active_since = timezone.now() - timedelta(days=30)
    active_users = (
        User.objects.filter(
            memberships__organization_id__in=organization_ids,
            last_login__gte=active_since,
        )
        .distinct()
        .count()
    )
    return {
        "active_users": active_users,
        "course_count": courses.count(),
        "enrollment_count": enrollments.count(),
        "completed_enrollments": CourseCompletion.objects.filter(
            enrollment__in=enrollments
        ).count(),
        "ai_request_volume": total_jobs,
        "ai_error_rate": _percentage(failed_jobs, total_jobs),
        "input_tokens": usage["input_tokens"] or 0,
        "output_tokens": usage["output_tokens"] or 0,
        "estimated_cost": usage["estimated_cost"] or Decimal("0"),
        "manual_review_volume": review_volume,
        "open_manual_reviews": open_reviews,
    }
