"""Provider-independent LLM access. Provider names and model names are configuration."""

from pv_llm.base import (
    EmbeddingResult,
    GenerationResult,
    LLMError,
    LLMProvider,
    ModelInfo,
)
from pv_llm.factory import build_provider
from pv_llm.gemini import GeminiProvider
from pv_llm.recording import content_hash, record_result
from pv_llm.resume_parse import PROMPT_VERSION, ParseOutcome, parse_resume_text
from pv_llm.structured import StructuredOutputError, StructuredResult, generate_structured

__all__ = [
    "PROMPT_VERSION",
    "EmbeddingResult",
    "GeminiProvider",
    "GenerationResult",
    "LLMError",
    "LLMProvider",
    "ModelInfo",
    "ParseOutcome",
    "StructuredOutputError",
    "StructuredResult",
    "build_provider",
    "content_hash",
    "generate_structured",
    "parse_resume_text",
    "record_result",
]
