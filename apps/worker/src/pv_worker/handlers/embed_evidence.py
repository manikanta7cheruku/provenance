"""Embed the chunks that have no vector yet. Idempotent: the work list is "chunks still missing a
vector", so running it twice, or after a crash, simply finds less to do.

  - first it makes the chunks match the profile (cheap, and it also fills in users whose profile
    existed before evidence search did)
  - with no key or no embedding model it does nothing and succeeds: keyword search still works
  - a vector is stored only if the chunk still has the text it was computed from, so an edit made
    while the model was working is never overwritten by a stale vector
  - progress is kept when a call fails: the next attempt continues where this one stopped

Only chunk text goes to the provider, and every call is recorded in llm_calls without content.
"""

import logging
from collections.abc import Callable

from pv_domain.evidence import EMBEDDING_DIMENSIONS
from pv_llm import (
    LLMError,
    LLMProvider,
    build_provider,
    content_hash,
    embeddings_configured,
    record_result,
)
from pv_persistence.evidence import pending_embeddings, reconcile_profile_chunks, store_embedding
from pv_persistence.tenancy import tenant_session
from pv_worker.contract import TaskContext, TaskFailure

logger = logging.getLogger("pv_worker")

BATCH = 25
MAX_CHUNKS_PER_RUN = 200

ProviderFactory = Callable[[], LLMProvider]


def handle_embed_evidence(ctx: TaskContext) -> None:
    run_embed(
        ctx,
        provider_factory=lambda: build_provider(ctx.settings, for_embeddings=True),
        configured=embeddings_configured(ctx.settings),
    )


def run_embed(ctx: TaskContext, *, provider_factory: ProviderFactory, configured: bool) -> None:
    owner = ctx.owner_user_id
    if owner is None:
        raise TaskFailure("The embedding task has no owner.", retryable=False)

    with tenant_session(ctx.engine, owner) as db:
        reconcile_profile_chunks(db, owner)
    if not configured:
        logger.info("embedding_skipped", extra={"reason": "not_configured"})
        return

    model = ctx.settings.llm_embedding_model
    provider = provider_factory()
    done = 0
    while done < MAX_CHUNKS_PER_RUN:
        with tenant_session(ctx.engine, owner) as db:
            work = pending_embeddings(db, owner, model, BATCH)
        if not work:
            return
        for chunk_id, body, digest in work:
            ctx.extend_lease()
            try:
                result = provider.embed(model=model, text=body, dimensions=EMBEDDING_DIMENSIONS)
            except LLMError as exc:
                record_result(
                    ctx.engine,
                    ctx.settings,
                    provider=provider.name,
                    model=model,
                    purpose="evidence_embedding",
                    result=None,
                    input_hash=digest,
                    user_id=owner,
                    error_class="LLM_RETRYABLE" if exc.retryable else "LLM_REJECTED",
                )
                raise TaskFailure(exc.summary, retryable=exc.retryable) from exc
            record_result(
                ctx.engine,
                ctx.settings,
                provider=provider.name,
                model=model,
                purpose="evidence_embedding",
                result=result,
                input_hash=content_hash(body),
                user_id=owner,
            )
            if len(result.values) != EMBEDDING_DIMENSIONS:
                raise TaskFailure(
                    f"The embedding model returned {len(result.values)} numbers but the database "
                    f"stores {EMBEDDING_DIMENSIONS}. Check LLM_EMBEDDING_MODEL and "
                    "LLM_EMBEDDING_DIMENSIONS.",
                    retryable=False,
                )
            with tenant_session(ctx.engine, owner) as db:
                store_embedding(db, owner, chunk_id, digest, result.values, model)
            done += 1
