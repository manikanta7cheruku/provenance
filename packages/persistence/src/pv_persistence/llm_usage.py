"""The model call ledger. One row per call: who, which model, how many tokens, what it cost.

There is deliberately no argument for prompt or response text. content_hash lets two
calls with the same input be recognised without storing the input.
"""

import uuid
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from pv_persistence.models import LlmCall
from pv_persistence.tenancy import tenant_session


def _plan_of(engine: Engine, user_id: uuid.UUID) -> str | None:
    """The plan the person has been given, or None for the default plan. Never raises: recording a
    call must not fail because a plan could not be read."""
    try:
        with tenant_session(engine, user_id) as db:
            value = db.execute(text("SELECT plan_id FROM user_plans LIMIT 1")).scalar_one_or_none()
        return str(value) if value else None
    except SQLAlchemyError:
        return None


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
    plan_id: str | None = None,
) -> None:
    if plan_id is None and user_id is not None:
        plan_id = _plan_of(engine, user_id)
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
                plan_id=plan_id,
            )
        )
