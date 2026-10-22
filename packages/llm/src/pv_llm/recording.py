"""Record every model call in the llm_calls ledger (metadata and cost, never content)."""

import hashlib
import uuid

from sqlalchemy.engine import Engine

from pv_config import Settings
from pv_domain.cost import estimate_cost_usd
from pv_llm.base import EmbeddingResult, GenerationResult
from pv_persistence.llm_usage import record_llm_call


def content_hash(*parts: str) -> str:
    """Fingerprint of the input, so repeated calls can be recognised without storing text."""
    digest = hashlib.sha256()
    for part in parts:
        digest.update(part.encode())
        digest.update(b"\x00")
    return digest.hexdigest()


def record_result(
    engine: Engine,
    settings: Settings,
    *,
    provider: str,
    model: str,
    purpose: str,
    result: GenerationResult | EmbeddingResult | None,
    input_hash: str | None = None,
    prompt_version: str | None = None,
    run_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    error_class: str | None = None,
    latency_ms: int = 0,
) -> None:
    """Pass result=None with an error_class to record a failed call."""
    if result is None:
        record_llm_call(
            engine,
            purpose=purpose,
            provider=provider,
            model=model,
            input_tokens=0,
            output_tokens=0,
            estimated_cost_usd=estimate_cost_usd(
                0, 0, input_price_per_million=0, output_price_per_million=0
            ),
            latency_ms=latency_ms,
            status="error",
            error_class=error_class or "UNKNOWN",
            prompt_version=prompt_version,
            content_hash=input_hash,
            run_id=run_id,
            user_id=user_id,
        )
        return
    output_tokens = result.output_tokens if isinstance(result, GenerationResult) else 0
    input_price = (
        settings.llm_embedding_price_per_million
        if isinstance(result, EmbeddingResult)
        else settings.llm_input_price_per_million
    )
    record_llm_call(
        engine,
        purpose=purpose,
        provider=provider,
        model=model,
        input_tokens=result.input_tokens,
        output_tokens=output_tokens,
        estimated_cost_usd=estimate_cost_usd(
            result.input_tokens,
            output_tokens,
            input_price_per_million=input_price,
            output_price_per_million=settings.llm_output_price_per_million,
        ),
        latency_ms=result.latency_ms,
        prompt_version=prompt_version,
        content_hash=input_hash,
        run_id=run_id,
        user_id=user_id,
    )
