from copy import deepcopy

from django.core.exceptions import ValidationError
from django.db import transaction

from assessments.models import Question, RubricVersion
from courses.models import (
    CourseVersion,
    FinalProject,
    LessonArtifact,
    LessonVersion,
    Module,
)

from .models import CourseGenerationRequest
from .schemas import CourseGenerationResult
from .security import allowed_embed_url, moderate_payload, sanitize_html


def validate_generation_result(result) -> CourseGenerationResult:
    """Revalidate provider output before any generated content is persisted."""
    payload = result.model_dump() if hasattr(result, "model_dump") else result
    moderate_payload(payload, field_name="Generated course content")
    validated = CourseGenerationResult.model_validate(payload)
    for module in validated.modules:
        for lesson in module.lessons:
            lesson.content = sanitize_html(lesson.content)
            if len(lesson.content.split()) < 5:
                raise ValidationError(f"Generated lesson '{lesson.title}' is too short to be useful.")
            if sum(criterion.weight for question in lesson.questions for criterion in question.rubric) <= 0:
                raise ValidationError(f"Generated lesson '{lesson.title}' has invalid rubric weights.")
            for artifact in lesson.artifacts:
                if artifact.artifact_type != "code_example":
                    artifact.content = sanitize_html(artifact.content)
                if artifact.artifact_type in {"image", "simulation_link"}:
                    allowed_embed_url(artifact.content, field_name="Generated media URL")
    return validated


@transaction.atomic
def persist_generation_result(request: CourseGenerationRequest, result: CourseGenerationResult):
    result = validate_generation_result(result)
    course = request.course
    course.description = result.description
    course.status = course.Status.DRAFT
    course.save(update_fields=["description", "status", "updated_at"])

    if request.generated_version_id:
        existing_draft = request.generated_version
        if existing_draft and existing_draft.status == CourseVersion.Status.DRAFT and existing_draft.generated_by_ai:
            return existing_draft

    draft = CourseVersion.objects.create(
        course=course,
        version_number=(course.versions.order_by("-version_number").values_list("version_number", flat=True).first() or 0) + 1,
        status=CourseVersion.Status.DRAFT,
        generated_by_ai=True,
    )

    for module_position, generated_module in enumerate(result.modules, start=1):
        module = Module.objects.create(
            course_version=draft,
            title=generated_module.title,
            position=module_position,
        )
        for lesson_position, generated_lesson in enumerate(generated_module.lessons, start=1):
            lesson = LessonVersion.objects.create(
                module=module,
                title=generated_lesson.title,
                objectives=deepcopy(generated_lesson.objectives),
                content=generated_lesson.content,
                position=lesson_position,
                status=LessonVersion.Status.DRAFT,
            )
            for artifact_position, generated_artifact in enumerate(generated_lesson.artifacts, start=1):
                LessonArtifact.objects.create(
                    lesson_version=lesson,
                    artifact_type=generated_artifact.artifact_type,
                    content=generated_artifact.content,
                    metadata=generated_artifact.metadata.model_dump(),
                    ai_generated=True,
                    teacher_approved=False,
                    position=artifact_position,
                )
            for question_position, generated_question in enumerate(generated_lesson.questions, start=1):
                question = Question.objects.create(
                    lesson_version=lesson,
                    question_type=generated_question.question_type,
                    prompt=generated_question.prompt,
                    max_score=generated_question.max_score,
                    position=question_position,
                    is_active=True,
                    is_objective=False,
                )
                RubricVersion.objects.create(
                    question=question,
                    version_number=1,
                    criteria=[criterion.model_dump() for criterion in generated_question.rubric],
                    total_score=generated_question.max_score,
                )

    generated_project = result.final_project
    FinalProject.objects.create(
        course_version=draft,
        title=generated_project.title,
        brief=generated_project.brief,
        objectives=deepcopy(generated_project.objectives),
        requirements=deepcopy(generated_project.requirements),
        deliverables=deepcopy(generated_project.deliverables),
        rubric=[criterion.model_dump() for criterion in generated_project.rubric],
        estimated_hours=generated_project.estimated_hours,
        ai_generated=True,
        teacher_approved=False,
    )

    request.generated_version = draft
    request.status = CourseGenerationRequest.Status.REVIEW
    request.error_details = {}
    request.completed_at = None
    request.save(update_fields=["generated_version", "status", "error_details", "completed_at"])
    return draft
