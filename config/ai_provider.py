from django.core.exceptions import ImproperlyConfigured


SUPPORTED_AI_LLM_PROVIDERS = {"fake", "openai"}


def validate_ai_provider_configuration(provider, api_key):
    normalized_provider = (provider or "").strip().lower()
    if normalized_provider not in SUPPORTED_AI_LLM_PROVIDERS:
        supported = ", ".join(sorted(SUPPORTED_AI_LLM_PROVIDERS))
        raise ImproperlyConfigured(f"Unsupported AI_LLM_PROVIDER '{provider}'. Supported values: {supported}.")
    if normalized_provider == "openai" and not (api_key or "").strip():
        raise ImproperlyConfigured("OPENAI_API_KEY must be set when AI_LLM_PROVIDER=openai.")
    return normalized_provider
