from dataclasses import dataclass, field
from typing import Protocol

from ai_engine.schemas import AnalyticsAnalysisResult, CourseGenerationResult, GradingResult


class ProviderError(Exception):
    pass


@dataclass(frozen=True)
class ProviderGrade:
    result: GradingResult
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    response_id: str = ""


@dataclass(frozen=True)
class CourseGenerationInput:
    title: str
    objective: str
    duration_weeks: int
    audience: str
    free_prompt: str
    assessment_types: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ProviderCourseGeneration:
    result: CourseGenerationResult
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    response_id: str = ""


@dataclass(frozen=True)
class ProviderAnalyticsAnalysis:
    result: AnalyticsAnalysisResult
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    response_id: str = ""


class GradingProvider(Protocol):
    def grade(
        self,
        *,
        question: str,
        answer: str,
        rubric: list[dict],
        execution_context: dict | None = None,
    ) -> ProviderGrade:
        ...


class CourseGenerationProvider(Protocol):
    def generate(self, request: CourseGenerationInput) -> ProviderCourseGeneration:
        ...


class AnalyticsAnalyzer(Protocol):
    def analyze(self, metrics: dict) -> ProviderAnalyticsAnalysis:
        ...
