"""Provider-independent LLM access. Provider names and model names are configuration."""

from pv_llm.base import (
    EmbeddingResult,
    GenerationResult,
    LLMError,
    LLMProvider,
    ModelInfo,
)
from pv_llm.gemini import GeminiProvider
from pv_llm.recording import content_hash, record_result

__all__ = [
    "EmbeddingResult",
    "GeminiProvider",
    "GenerationResult",
    "LLMError",
    "LLMProvider",
    "ModelInfo",
    "content_hash",
    "record_result",
]
