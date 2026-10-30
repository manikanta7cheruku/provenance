"""The one place that turns settings into a provider. Switching provider changes this file only."""

from pv_config import Settings
from pv_llm.base import LLMError, LLMProvider
from pv_llm.gemini import GeminiProvider


def embeddings_configured(settings: Settings) -> bool:
    """True when a key and an embedding model are set, so meaning search can work."""
    return bool(settings.gemini_api_key.get_secret_value() and settings.llm_embedding_model)


def build_provider(settings: Settings, *, for_embeddings: bool = False) -> LLMProvider:
    """Raise a non-retryable LLMError when the AI provider is not configured.

    Generation needs LLM_MODEL. Embeddings need LLM_EMBEDDING_MODEL. Both need the key.
    """
    key = settings.gemini_api_key.get_secret_value()
    model = settings.llm_embedding_model if for_embeddings else settings.llm_model
    if not key or not model:
        raise LLMError("The AI provider is not configured.", retryable=False)
    return GeminiProvider(
        key,
        base_url=settings.gemini_base_url,
        min_interval_seconds=settings.llm_min_interval_seconds,
    )
