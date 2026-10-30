"""Hybrid retrieval over a person's evidence: keyword search and meaning search, fused by rank.

Two searches answer different questions. Keyword search (Postgres full text) finds the exact words,
including names and tools, and works with no AI at all. Meaning search (pgvector, cosine distance
over embeddings) finds entries that say the same thing in other words. Each returns a ranked list.
Reciprocal rank fusion combines the two lists using ranks only, so neither needs a score scale.

Meaning search is optional. With no key, no embedding model, no embedded chunks, or a provider that
is down, the result is the keyword list plus a plain note saying so. A search never fails because
the AI is unavailable.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy.engine import Engine

from pv_config import Settings
from pv_domain.evidence import EMBEDDING_DIMENSIONS, clean_query, reciprocal_rank_fusion
from pv_llm.base import LLMError, LLMProvider
from pv_llm.factory import build_provider, embeddings_configured
from pv_llm.recording import content_hash, record_result
from pv_persistence.evidence import (
    ChunkRow,
    evidence_status,
    search_keyword,
    search_meaning,
)
from pv_persistence.tenancy import tenant_session

CANDIDATES = 50
DEFAULT_LIMIT = 10


@dataclass(frozen=True)
class EvidenceHit:
    chunk_id: uuid.UUID
    source_type: str
    source_record_id: uuid.UUID
    entry_type: str | None
    text: str
    score: float
    matched_by: tuple[str, ...]
    keyword_rank: int | None
    meaning_rank: int | None
    similarity: float | None


@dataclass(frozen=True)
class SearchOutcome:
    hits: list[EvidenceHit]
    semantic_used: bool
    # A plain sentence when meaning search was not used, or None when it was.
    note: str | None


def _meaning(
    engine: Engine,
    settings: Settings,
    owner_id: uuid.UUID,
    query: str,
    provider: LLMProvider | None,
) -> tuple[list[ChunkRow], str | None]:
    """Rows from meaning search, or an empty list and the reason it was not used."""
    if provider is None and not embeddings_configured(settings):
        return [], "Meaning search needs an AI key. Showing keyword matches only."
    model = settings.llm_embedding_model
    with tenant_session(engine, owner_id) as db:
        status = evidence_status(db, owner_id, model)
    if status.embedded == 0:
        return (
            [],
            "Your entries are not indexed for meaning search yet. Showing keyword matches only.",
        )
    try:
        searcher = provider or build_provider(settings, for_embeddings=True)
        result = searcher.embed(model=model, text=query, dimensions=EMBEDDING_DIMENSIONS)
    except LLMError as exc:
        record_result(
            engine,
            settings,
            provider=getattr(provider, "name", "gemini"),
            model=model,
            purpose="evidence_query",
            result=None,
            input_hash=content_hash(query),
            user_id=owner_id,
            error_class="LLM_RETRYABLE" if exc.retryable else "LLM_REJECTED",
        )
        return [], "Meaning search is unavailable right now. Showing keyword matches only."
    record_result(
        engine,
        settings,
        provider=searcher.name,
        model=model,
        purpose="evidence_query",
        result=result,
        input_hash=content_hash(query),
        user_id=owner_id,
    )
    if len(result.values) != EMBEDDING_DIMENSIONS:
        return [], "Meaning search is misconfigured (embedding size). Showing keyword matches only."
    with tenant_session(engine, owner_id) as db:
        rows = search_meaning(db, owner_id, result.values, model, CANDIDATES)
    floor = settings.evidence_min_similarity
    return [r for r in rows if (r.score or 0.0) >= floor], None


def hybrid_search(
    engine: Engine,
    settings: Settings,
    owner_id: uuid.UUID,
    query: str,
    *,
    limit: int = DEFAULT_LIMIT,
    provider: LLMProvider | None = None,
) -> SearchOutcome:
    """Search one person's evidence. Always scoped to that person."""
    cleaned = clean_query(query)
    if not cleaned:
        return SearchOutcome([], False, None)
    with tenant_session(engine, owner_id) as db:
        keyword = search_keyword(db, owner_id, cleaned, CANDIDATES)
    meaning, note = _meaning(engine, settings, owner_id, cleaned, provider)

    keyword_rank = {row.id: position for position, row in enumerate(keyword, start=1)}
    meaning_rank = {row.id: position for position, row in enumerate(meaning, start=1)}
    similarity = {row.id: row.score for row in meaning}
    rows = {row.id: row for row in [*keyword, *meaning]}
    fused = reciprocal_rank_fusion([[r.id for r in keyword], [r.id for r in meaning]])
    hits = []
    for chunk_id, score in fused[:limit]:
        row = rows[chunk_id]
        matched = tuple(
            name
            for name, ranks in (("keyword", keyword_rank), ("meaning", meaning_rank))
            if chunk_id in ranks
        )
        hits.append(
            EvidenceHit(
                chunk_id=chunk_id,
                source_type=row.source_type,
                source_record_id=row.source_record_id,
                entry_type=row.entry_type,
                text=row.text,
                score=score,
                matched_by=matched,
                keyword_rank=keyword_rank.get(chunk_id),
                meaning_rank=meaning_rank.get(chunk_id),
                similarity=similarity.get(chunk_id),
            )
        )
    return SearchOutcome(hits, semantic_used=note is None, note=note)
