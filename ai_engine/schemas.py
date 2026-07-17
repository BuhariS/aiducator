from pydantic import BaseModel, Field


class GradingResult(BaseModel):
    suggested_score: int = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    strengths: list[str] = Field(default_factory=list)
    mistakes: list[str] = Field(default_factory=list)
    feedback: str
    remediation: str = ""
    teacher_review_required: bool = True
