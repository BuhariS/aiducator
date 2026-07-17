from dataclasses import dataclass
from typing import Protocol

from ai_engine.schemas import GradingResult


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


class GradingProvider(Protocol):
    def grade(self, *, question: str, answer: str, rubric: list[dict]) -> ProviderGrade:
        ...
