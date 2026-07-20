from typing import Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator


GENERATED_QUESTION_TYPES = Literal[
    "reflection",
    "scenario",
    "critical_thinking",
    "task_prompt",
    "misconception",
]
GENERATED_QUESTION_TYPE_VALUES = (
    "reflection",
    "scenario",
    "critical_thinking",
    "task_prompt",
    "misconception",
)


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


class StructuredOutputModel(BaseModel):
    """Base schema compatible with OpenAI Structured Outputs."""

    model_config = ConfigDict(extra="forbid")


class GradingResult(StructuredOutputModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

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


class AnalyticsInsight(StructuredOutputModel):
    priority: Literal["high", "medium", "low"] = "medium"
    title: str = Field(min_length=3, max_length=180)
    evidence: str = Field(min_length=3, max_length=600)
    action: str = Field(min_length=3, max_length=800)

    _safe_title = field_validator("title")(_reject_unsafe_text)
    _safe_evidence = field_validator("evidence")(_reject_unsafe_text)
    _safe_action = field_validator("action")(_reject_unsafe_text)


class AnalyticsAnalysisResult(StructuredOutputModel):
    summary: str = Field(min_length=3, max_length=1200)
    insights: list[AnalyticsInsight] = Field(min_length=1, max_length=8)
    next_steps: list[str] = Field(min_length=1, max_length=6)

    _safe_summary = field_validator("summary")(_reject_unsafe_text)
    _safe_next_steps = field_validator("next_steps")(_reject_unsafe_payload)


class GeneratedRubricCriterion(StructuredOutputModel):
    criterion: str = Field(min_length=3, max_length=500)
    weight: float = Field(gt=0, le=100)

    _safe_criterion = field_validator("criterion")(_reject_unsafe_text)


class GeneratedQuestion(StructuredOutputModel):
    question_type: GENERATED_QUESTION_TYPES
    prompt: str = Field(min_length=10, max_length=4000)
    rubric: list[GeneratedRubricCriterion] = Field(min_length=1, max_length=12)
    max_score: int = Field(default=100, ge=1, le=100)

    _safe_prompt = field_validator("prompt")(_reject_unsafe_text)


class GeneratedLesson(StructuredOutputModel):
    title: str = Field(min_length=3, max_length=180)
    objectives: list[str] = Field(min_length=1, max_length=8)
    content: str = Field(min_length=30, max_length=20000)
    questions: list[GeneratedQuestion] = Field(min_length=1, max_length=12)

    _safe_title = field_validator("title")(_reject_unsafe_text)
    _safe_content = field_validator("content")(_reject_unsafe_text)


class GeneratedModule(StructuredOutputModel):
    title: str = Field(min_length=3, max_length=180)
    lessons: list[GeneratedLesson] = Field(min_length=1, max_length=20)

    _safe_title = field_validator("title")(_reject_unsafe_text)


class GeneratedFinalProject(StructuredOutputModel):
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


class CourseGenerationResult(StructuredOutputModel):
    title: str = Field(min_length=3, max_length=180)
    description: str = Field(min_length=20, max_length=5000)
    modules: list[GeneratedModule] = Field(min_length=1, max_length=20)
    final_project: GeneratedFinalProject

    _safe_title = field_validator("title")(_reject_unsafe_text)
    _safe_description = field_validator("description")(_reject_unsafe_text)
