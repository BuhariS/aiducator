from copy import deepcopy

from django.db import transaction
from django.db.models import Max

from assessments.models import Question, RubricVersion

from .models import Course, CourseVersion, LessonArtifact, LessonVersion, Module, Translation


@transaction.atomic
def create_draft_version(course: Course, source: CourseVersion | None = None) -> CourseVersion:
    if source is None:
        source = course.versions.order_by("-version_number").first()
    next_number = (course.versions.aggregate(max_number=Max("version_number"))["max_number"] or 0) + 1
    draft = CourseVersion.objects.create(
        course=course,
        version_number=next_number,
        status=CourseVersion.Status.DRAFT,
        generated_by_ai=False,
    )
    if source is None:
        return draft

    for source_module in source.modules.all():
        module = Module.objects.create(
            course_version=draft,
            title=source_module.title,
            position=source_module.position,
        )
        for source_lesson in source_module.lessons.all():
            lesson = LessonVersion.objects.create(
                module=module,
                title=source_lesson.title,
                objectives=deepcopy(source_lesson.objectives),
                content=source_lesson.content,
                position=source_lesson.position,
                status=LessonVersion.Status.DRAFT,
            )
            for source_artifact in source_lesson.artifacts.all():
                LessonArtifact.objects.create(
                    lesson_version=lesson,
                    artifact_type=source_artifact.artifact_type,
                    content=source_artifact.content,
                    metadata=deepcopy(source_artifact.metadata),
                    is_active=source_artifact.is_active,
                    position=source_artifact.position,
                )
            for source_translation in source_lesson.translations.all():
                Translation.objects.create(
                    lesson_version=lesson,
                    language_code=source_translation.language_code,
                    content=deepcopy(source_translation.content),
                    status=Translation.Status.DRAFT,
                )
            for source_question in source_lesson.questions.all():
                question = Question.objects.create(
                    lesson_version=lesson,
                    question_type=source_question.question_type,
                    prompt=source_question.prompt,
                    max_score=source_question.max_score,
                    position=source_question.position,
                    is_active=source_question.is_active,
                )
                source_rubric = source_question.rubrics.order_by("-version_number").first()
                if source_rubric:
                    RubricVersion.objects.create(
                        question=question,
                        version_number=1,
                        criteria=deepcopy(source_rubric.criteria),
                        total_score=source_rubric.total_score,
                    )
    return draft
