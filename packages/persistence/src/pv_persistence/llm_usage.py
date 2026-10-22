"""The model call ledger. One row per call: who, which model, how many tokens, what it cost.

There is deliberately no argument for prompt or response text. content_hash lets two
calls with the same input be recognised without storing the input.
"""

import uuid
from decimal import Decimal

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from pv_persistence.models import LlmCall


def record_llm_call(
    engine: Engine,
    *,
    purpose: str,
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    estimated_cost_usd: Decimal,
    latency_ms: int,
    status: str = "ok",
    error_class: str | None = None,
    prompt_version: str | None = None,
    content_hash: str | None = None,
    run_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
) -> None:
    with Session(engine) as db, db.begin():
        db.add(
            LlmCall(
                run_id=run_id,
                user_id=user_id,
                purpose=purpose,
                provider=provider,
                model=model,
                prompt_version=prompt_version,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                estimated_cost_usd=estimated_cost_usd,
                latency_ms=latency_ms,
                status=status,
                error_class=error_class,
                content_hash=content_hash,
            )
        )
