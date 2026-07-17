from django.conf import settings

from .base import GradingProvider, ProviderError
from .fake import FakeGradingProvider
from .openai import OpenAIGradingProvider


def get_grading_provider() -> GradingProvider:
    if settings.AI_LLM_PROVIDER == "fake":
        return FakeGradingProvider()
    if settings.AI_LLM_PROVIDER == "openai":
        return OpenAIGradingProvider()
    raise ProviderError(f"Unsupported AI_LLM_PROVIDER: {settings.AI_LLM_PROVIDER}")
