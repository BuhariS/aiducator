from collections import Counter, defaultdict
from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Count, Q, Sum
from django.utils import timezone

from accounts.models import User
from ai_engine.models import AIJob, AIUsageEvent, CourseGenerationRequest
from assessments.models import AIGrade, Attempt, GradeDecision, ReviewQueueItem
from courses.models import Course, LessonVersion
from enrollments.models import Enrollment, LessonProgress

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
    return _teacher_metrics_for_courses(Course.objects.filter(id=course.id))[0]


def teacher_analytics(user):
    return _teacher_metrics_for_courses(Course.objects.filter(created_by=user).order_by("title"))


def _teacher_metrics_for_courses(courses):
    courses = list(
        courses.annotate(
            enrollment_count=Count("enrollments", distinct=True),
            completed_enrollment_count=Count("enrollments__completion", distinct=True),
        )
    )
    if not courses:
        return []

    course_ids = [course.id for course in courses]
    course_by_id = {course.id: course for course in courses}
    grade_stats = defaultdict(lambda: {"total": 0, "score_total": 0, "passed": 0, "overridden": 0})
    for decision in GradeDecision.objects.filter(
        attempt__enrollment__course_id__in=course_ids
    ).values("attempt__enrollment__course_id", "final_score", "status"):
        course_id = decision["attempt__enrollment__course_id"]
        stats = grade_stats[course_id]
        stats["total"] += 1
        stats["score_total"] += decision["final_score"]
        if decision["final_score"] >= course_by_id[course_id].passing_score:
            stats["passed"] += 1
        if decision["status"] == GradeDecision.Status.OVERRIDDEN:
            stats["overridden"] += 1

    mistakes_by_course = defaultdict(Counter)
    disparities_by_course = defaultdict(list)
    for grade in AIGrade.objects.filter(
        attempt__enrollment__course_id__in=course_ids
    ).values(
        "attempt__enrollment__course_id",
        "errors",
        "suggested_score",
        "attempt__grade_decision__final_score",
    ):
        course_id = grade["attempt__enrollment__course_id"]
        for error in grade["errors"] or []:
            label = str(error).strip()
            if label:
                mistakes_by_course[course_id][label] += 1
        final_score = grade["attempt__grade_decision__final_score"]
        if final_score is not None:
            disparities_by_course[course_id].append(abs(grade["suggested_score"] - final_score))

    learners_needing_help = defaultdict(list)
    for enrollment in (
        Enrollment.objects.filter(course_id__in=course_ids)
        .filter(
            Q(lesson_progress__status=LessonProgress.Status.NEEDS_SUPPORT)
            | Q(attempts__status__in=["needs_support", "remediation"])
        )
        .select_related("student")
        .distinct()
        .order_by("student__email")
    ):
        learners_needing_help[enrollment.course_id].append(enrollment)

    lessons_by_course = defaultdict(list)
    lessons = list(
        LessonVersion.objects.filter(module__course_version__course_id__in=course_ids)
        .order_by("module__course_version__course_id", "module__position", "position")
        .values("id", "title", "module__course_version__course_id")
    )
    lesson_ids = [lesson["id"] for lesson in lessons]
    for lesson in lessons:
        lessons_by_course[lesson["module__course_version__course_id"]].append(lesson)

    progress_by_lesson = {
        item["lesson_version_id"]: item
        for item in LessonProgress.objects.filter(
            enrollment__course_id__in=course_ids,
            lesson_version_id__in=lesson_ids,
        )
        .values("lesson_version_id")
        .annotate(
            started=Count("id", filter=~Q(status=LessonProgress.Status.NOT_STARTED)),
            completed=Count("id", filter=Q(status=LessonProgress.Status.COMPLETED)),
        )
    }
    seconds_by_lesson = {
        item["lesson_id"]: item["seconds"]
        for item in LessonTimeEvent.objects.filter(
            enrollment__course_id__in=course_ids,
            lesson_id__in=lesson_ids,
        )
        .values("lesson_id")
        .annotate(seconds=Sum("duration_seconds"))
    }

    metrics = []
    for course in courses:
        stats = grade_stats[course.id]
        lesson_metrics = []
        for lesson in lessons_by_course[course.id]:
            progress = progress_by_lesson.get(lesson["id"], {})
            started = progress.get("started", 0)
            completed = progress.get("completed", 0)
            lesson_metrics.append(
                {
                    "title": lesson["title"],
                    "started": started,
                    "completed": completed,
                    "dropoff_rate": round(100 - _percentage(completed, started), 1) if started else 0,
                    "minutes": round((seconds_by_lesson.get(lesson["id"]) or 0) / 60, 1),
                }
            )
        disparities = disparities_by_course[course.id]
        metrics.append(
            {
                "course": course,
                "completion_rate": _percentage(course.completed_enrollment_count, course.enrollment_count),
                "enrollment_count": course.enrollment_count,
                "assessment_average": round(stats["score_total"] / stats["total"], 1) if stats["total"] else 0,
                "assessment_pass_rate": _percentage(stats["passed"], stats["total"]),
                "common_mistakes": mistakes_by_course[course.id].most_common(5),
                "students_needing_help": learners_needing_help[course.id],
                "ai_overridden": stats["overridden"],
                "ai_human_gap": round(sum(disparities) / len(disparities), 1) if disparities else 0,
                "lesson_metrics": lesson_metrics,
            }
        )
    return metrics


def analytics_analysis_payload(course_metrics):
    return {
        "courses": [
            {
                "title": item["course"].title,
                "completion_rate": item["completion_rate"],
                "enrollment_count": item["enrollment_count"],
                "assessment_average": item["assessment_average"],
                "assessment_pass_rate": item["assessment_pass_rate"],
                "students_needing_help": len(item["students_needing_help"]),
                "ai_overrides": item["ai_overridden"],
                "ai_human_gap": item["ai_human_gap"],
                "common_mistakes": [
                    {"mistake": mistake, "count": count}
                    for mistake, count in item["common_mistakes"]
                ],
                "lesson_metrics": [
                    {
                        "title": lesson["title"],
                        "minutes": lesson["minutes"],
                        "dropoff_rate": lesson["dropoff_rate"],
                    }
                    for lesson in item["lesson_metrics"]
                ],
            }
            for item in course_metrics
        ]
    }


def administrator_analytics(organizations):
    organization_ids = organizations.values("id")
    course_totals = Course.objects.filter(organization_id__in=organization_ids).aggregate(
        course_count=Count("id", distinct=True),
        enrollment_count=Count("enrollments", distinct=True),
        completed_enrollments=Count("enrollments__completion", distinct=True),
    )
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
    job_totals = jobs.aggregate(
        total_jobs=Count("id"),
        failed_jobs=Count("id", filter=Q(status=AIJob.Status.FAILED)),
    )
    usage = AIUsageEvent.objects.filter(job__in=jobs).aggregate(
        input_tokens=Sum("input_tokens"),
        output_tokens=Sum("output_tokens"),
        estimated_cost=Sum("estimated_cost"),
    )
    review_totals = Attempt.objects.filter(
        enrollment__course__organization_id__in=organization_ids
    ).aggregate(
        manual_review_volume=Count("manual_review"),
        open_manual_reviews=Count(
            "review_item",
            filter=Q(review_item__status=ReviewQueueItem.Status.OPEN),
        ),
    )
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
        "course_count": course_totals["course_count"],
        "enrollment_count": course_totals["enrollment_count"],
        "completed_enrollments": course_totals["completed_enrollments"],
        "ai_request_volume": job_totals["total_jobs"],
        "ai_error_rate": _percentage(job_totals["failed_jobs"], job_totals["total_jobs"]),
        "input_tokens": usage["input_tokens"] or 0,
        "output_tokens": usage["output_tokens"] or 0,
        "estimated_cost": usage["estimated_cost"] or Decimal("0"),
        "manual_review_volume": review_totals["manual_review_volume"],
        "open_manual_reviews": review_totals["open_manual_reviews"],
    }
