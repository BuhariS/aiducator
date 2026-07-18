from dataclasses import dataclass
from typing import Protocol

from ai_engine.schemas import CourseGenerationResult, GradingResult


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
    translation_languages: list[str]


@dataclass(frozen=True)
class ProviderCourseGeneration:
    result: CourseGenerationResult
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    response_id: str = ""


class GradingProvider(Protocol):
    def grade(self, *, question: str, answer: str, rubric: list[dict]) -> ProviderGrade:
        ...


class CourseGenerationProvider(Protocol):
    def generate(self, request: CourseGenerationInput) -> ProviderCourseGeneration:
        ...
