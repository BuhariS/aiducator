from ai_engine.schemas import GradingResult

from .base import ProviderGrade


class FakeGradingProvider:
    def grade(self, *, question: str, answer: str, rubric: list[dict]) -> ProviderGrade:
        score = 80 if len(answer.split()) >= 8 else 60
        result = GradingResult(
            suggested_score=score,
            confidence=0.9,
            strengths=["The answer attempts the requested concept."],
            mistakes=[] if score >= 70 else ["Add more explanation and a concrete Python example."],
            feedback="Your response has been reviewed against the lesson rubric.",
            remediation="Review the lesson example and explain the idea with a small program." if score < 70 else "",
            teacher_review_required=True,
        )
        return ProviderGrade(result=result, provider="fake", model="local", response_id="fake-response")
