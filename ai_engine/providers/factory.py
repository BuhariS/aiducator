from django.conf import settings

from .base import CourseGenerationProvider, GradingProvider, ProviderError
from .fake import FakeCourseGenerationProvider, FakeGradingProvider
from .openai import OpenAICourseGenerationProvider, OpenAIGradingProvider


def get_grading_provider() -> GradingProvider:
    if settings.AI_LLM_PROVIDER == "fake":
        return FakeGradingProvider()
    if settings.AI_LLM_PROVIDER == "openai":
        return OpenAIGradingProvider()
    raise ProviderError(f"Unsupported AI_LLM_PROVIDER: {settings.AI_LLM_PROVIDER}")


def get_course_generation_provider() -> CourseGenerationProvider:
    if settings.AI_LLM_PROVIDER == "fake":
        return FakeCourseGenerationProvider()
    if settings.AI_LLM_PROVIDER == "openai":
        return OpenAICourseGenerationProvider()
    raise ProviderError(f"Unsupported AI_LLM_PROVIDER: {settings.AI_LLM_PROVIDER}")
