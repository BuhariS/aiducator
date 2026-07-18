from typing import Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator


GENERATED_ARTIFACT_TYPES = Literal[
    "text",
    "video_embed",
    "image",
    "simulation_link",
    "code_example",
    "image_prompt",
    "youtube_search",
]

GENERATED_QUESTION_TYPES = Literal[
    "explanation",
    "code_writing",
    "debugging",
    "reflection",
    "scenario",
    "critical_thinking",
    "task_prompt",
    "misconception",
    "error_identification",
]


def _reject_unsafe_text(value: str) -> str:
    lowered = value.lower()
    if "<script" in lowered or "javascript:" in lowered or "data:text/html" in lowered:
        raise ValueError("Generated content contains a disallowed script or URL scheme")
    return value.strip()


def _reject_unsafe_payload(value):
    if isinstance(value, str):
        return _reject_unsafe_text(value)
    if isinstance(value, dict):
        return {key: _reject_unsafe_payload(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_reject_unsafe_payload(item) for item in value]
    return value


class GradingResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    score: int = Field(ge=0, le=100, validation_alias=AliasChoices("score", "suggested_score"))
    confidence: float = Field(ge=0, le=1)
    strengths: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    feedback: str
    remediation: str = ""
    recommended_action: Literal["advance", "remediate", "review"] = "review"
    requires_review: bool = True

    @property
    def suggested_score(self):
        return self.score

    @property
    def mistakes(self):
        return self.errors

    @property
    def teacher_review_required(self):
        return self.requires_review


class GeneratedArtifact(BaseModel):
    artifact_type: GENERATED_ARTIFACT_TYPES
    content: str = Field(min_length=1, max_length=12000)
    metadata: dict = Field(default_factory=dict)

    _safe_content = field_validator("content")(_reject_unsafe_text)
    _safe_metadata = field_validator("metadata")(_reject_unsafe_payload)


class GeneratedRubricCriterion(BaseModel):
    criterion: str = Field(min_length=3, max_length=500)
    weight: float = Field(gt=0, le=100)

    _safe_criterion = field_validator("criterion")(_reject_unsafe_text)


class GeneratedQuestion(BaseModel):
    question_type: GENERATED_QUESTION_TYPES
    prompt: str = Field(min_length=10, max_length=4000)
    rubric: list[GeneratedRubricCriterion] = Field(min_length=1, max_length=12)
    max_score: int = Field(default=100, ge=1, le=100)

    _safe_prompt = field_validator("prompt")(_reject_unsafe_text)


class GeneratedTranslation(BaseModel):
    language_code: str = Field(min_length=2, max_length=12)
    content: dict

    _safe_content = field_validator("content")(_reject_unsafe_payload)


class GeneratedLesson(BaseModel):
    title: str = Field(min_length=3, max_length=180)
    objectives: list[str] = Field(min_length=1, max_length=8)
    content: str = Field(min_length=30, max_length=20000)
    artifacts: list[GeneratedArtifact] = Field(default_factory=list, max_length=20)
    questions: list[GeneratedQuestion] = Field(min_length=1, max_length=12)
    translations: list[GeneratedTranslation] = Field(default_factory=list, max_length=12)

    _safe_title = field_validator("title")(_reject_unsafe_text)
    _safe_content = field_validator("content")(_reject_unsafe_text)


class GeneratedModule(BaseModel):
    title: str = Field(min_length=3, max_length=180)
    lessons: list[GeneratedLesson] = Field(min_length=1, max_length=20)

    _safe_title = field_validator("title")(_reject_unsafe_text)


class GeneratedFinalProject(BaseModel):
    title: str = Field(min_length=3, max_length=180)
    brief: str = Field(min_length=30, max_length=10000)
    objectives: list[str] = Field(min_length=1, max_length=8)
    requirements: list[str] = Field(min_length=1, max_length=12)
    deliverables: list[str] = Field(min_length=1, max_length=8)
    rubric: list[GeneratedRubricCriterion] = Field(min_length=1, max_length=12)
    estimated_hours: int = Field(default=8, ge=1, le=100)

    _safe_title = field_validator("title")(_reject_unsafe_text)
    _safe_brief = field_validator("brief")(_reject_unsafe_text)
    _safe_objectives = field_validator("objectives")(_reject_unsafe_payload)
    _safe_requirements = field_validator("requirements")(_reject_unsafe_payload)
    _safe_deliverables = field_validator("deliverables")(_reject_unsafe_payload)


class CourseGenerationResult(BaseModel):
    title: str = Field(min_length=3, max_length=180)
    description: str = Field(min_length=20, max_length=5000)
    modules: list[GeneratedModule] = Field(min_length=1, max_length=20)
    final_project: GeneratedFinalProject

    _safe_title = field_validator("title")(_reject_unsafe_text)
    _safe_description = field_validator("description")(_reject_unsafe_text)
