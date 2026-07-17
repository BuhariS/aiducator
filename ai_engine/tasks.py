import logging

from celery import shared_task
from django.db import transaction
from django.conf import settings
from django.utils import timezone

from assessments.models import AIGrade, Attempt, ReviewQueueItem, RubricVersion

from .models import AIJob, AIUsageEvent
from .providers import ProviderError, get_grading_provider


logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    autoretry_for=(ProviderError,),
    retry_backoff=True,
    retry_backoff_max=120,
    retry_jitter=True,
    max_retries=3,
)
def grade_attempt(self, job_id):
    job = AIJob.objects.get(id=job_id)
    if job.status == AIJob.Status.SUCCEEDED:
        return {"job_id": str(job.id), "status": job.status}

    with transaction.atomic():
        job = AIJob.objects.select_for_update().get(id=job_id)
        job.status = AIJob.Status.RUNNING
        job.progress = 10
        job.started_at = job.started_at or timezone.now()
        job.retry_count = self.request.retries
        job.save(update_fields=["status", "progress", "started_at", "retry_count"])

    attempt = Attempt.objects.select_related(
        "question__lesson_version__module__course_version__course",
    ).get(id=job.entity_id)
    rubric = (
        RubricVersion.objects.filter(question=attempt.question, approved_by__isnull=False)
        .order_by("-version_number")
        .first()
    )
    if rubric is None:
        return _fail_job(job, attempt, "No approved rubric is available for this question.")

    try:
        provider = get_grading_provider()
        provider_grade = provider.grade(
            question=attempt.question.prompt,
            answer=attempt.answer_text,
            rubric=rubric.criteria,
        )
    except ProviderError as exc:
        _record_failure(job, attempt, str(exc))
        raise

    result = provider_grade.result
    with transaction.atomic():
        AIGrade.objects.update_or_create(
            attempt=attempt,
            defaults={
                "suggested_score": result.suggested_score,
                "confidence": result.confidence,
                "strengths": result.strengths,
                "mistakes": result.mistakes,
                "feedback": result.feedback,
                "remediation": result.remediation,
                "teacher_review_required": True,
                "provider": provider_grade.provider,
                "model": provider_grade.model,
                "prompt_version": settings.AI_PROMPT_VERSION,
                "raw_response": {"response_id": provider_grade.response_id},
            },
        )
        AIUsageEvent.objects.create(
            job=job,
            provider=provider_grade.provider,
            model=provider_grade.model,
            input_tokens=provider_grade.input_tokens,
            output_tokens=provider_grade.output_tokens,
        )
        attempt.status = Attempt.Status.AWAITING_REVIEW
        attempt.evaluated_at = timezone.now()
        attempt.save(update_fields=["status", "evaluated_at"])
        ReviewQueueItem.objects.update_or_create(
            attempt=attempt,
            defaults={
                "reason": "AI grading ready for teacher review",
                "status": ReviewQueueItem.Status.OPEN,
                "assigned_to": attempt.question.lesson_version.module.course_version.course.created_by,
                "resolved_at": None,
            },
        )
        job.status = AIJob.Status.SUCCEEDED
        job.progress = 100
        job.provider = provider_grade.provider
        job.model = provider_grade.model
        job.prompt_version = settings.AI_PROMPT_VERSION
        job.completed_at = timezone.now()
        job.save(update_fields=["status", "progress", "provider", "model", "prompt_version", "completed_at"])

    return {"job_id": str(job.id), "status": job.status}


def _fail_job(job, attempt, message):
    _record_failure(job, attempt, message)
    return {"job_id": str(job.id), "status": job.status, "error": message}


def _record_failure(job, attempt, message):
    logger.error("AI job %s failed: %s", job.id, message)
    with transaction.atomic():
        job.status = AIJob.Status.FAILED
        job.error_message = message
        job.completed_at = timezone.now()
        job.save(update_fields=["status", "error_message", "completed_at"])
        attempt.status = Attempt.Status.AWAITING_REVIEW
        attempt.save(update_fields=["status"])
        ReviewQueueItem.objects.update_or_create(
            attempt=attempt,
            defaults={
                "reason": "AI grading failed; manual review required",
                "status": ReviewQueueItem.Status.OPEN,
                "assigned_to": attempt.question.lesson_version.module.course_version.course.created_by,
            },
        )
