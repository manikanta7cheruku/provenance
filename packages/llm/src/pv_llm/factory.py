"""The one place that turns settings into a provider. Switching provider changes this file only."""

from pv_config import Settings
from pv_llm.base import LLMError, LLMProvider
from pv_llm.gemini import GeminiProvider


def build_provider(settings: Settings) -> LLMProvider:
    """Raise a non-retryable LLMError when the AI provider is not configured."""
    key = settings.gemini_api_key.get_secret_value()
    if not key or not settings.llm_model:
        raise LLMError("The AI provider is not configured.", retryable=False)
    return GeminiProvider(key, min_interval_seconds=settings.llm_min_interval_seconds)
