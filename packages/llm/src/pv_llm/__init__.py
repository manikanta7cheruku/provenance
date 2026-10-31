"""Provider-independent LLM access. Provider names and model names are configuration."""

from pv_llm.base import (
    EmbeddingResult,
    GenerationResult,
    LLMError,
    LLMProvider,
    ModelInfo,
)
from pv_llm.evidence import EvidenceHit, SearchOutcome, hybrid_search
from pv_llm.factory import build_provider, embeddings_configured
from pv_llm.gemini import GeminiProvider
from pv_llm.job_extract import JobExtractionOutcome, extract_job_text
from pv_llm.recording import content_hash, record_result
from pv_llm.resume_parse import PROMPT_VERSION, ParseOutcome, parse_resume_text
from pv_llm.structured import StructuredOutputError, StructuredResult, generate_structured

__all__ = [
    "PROMPT_VERSION",
    "EmbeddingResult",
    "EvidenceHit",
    "GeminiProvider",
    "GenerationResult",
    "JobExtractionOutcome",
    "LLMError",
    "LLMProvider",
    "ModelInfo",
    "ParseOutcome",
    "SearchOutcome",
    "StructuredOutputError",
    "StructuredResult",
    "build_provider",
    "content_hash",
    "extract_job_text",
    "embeddings_configured",
    "generate_structured",
    "hybrid_search",
    "parse_resume_text",
    "record_result",
]
