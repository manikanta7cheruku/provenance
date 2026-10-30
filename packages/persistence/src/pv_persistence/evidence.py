"""Evidence chunks: keep them in step with the profile, store embeddings, search.

Call everything here inside tenant_session (Row Level Security applies). Every statement also
filters by owner, so a missing policy could not leak rows.

Keeping chunks in step is cheap and happens in the SAME transaction as the profile change, so
keyword search is never stale. Embeddings need a model call, so they are produced later by the
worker. A chunk whose text changed loses its embedding at once, which means a stale vector can
never answer a search.
"""

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from pv_domain.evidence import (
    SOURCE_PROFILE_ENTRY,
    clean_chunk_text,
    content_hash,
    render_entry_text,
)
from pv_domain.tasks import TASK_EMBED_EVIDENCE
from pv_persistence.models import EvidenceChunk
from pv_persistence.queue import enqueue
from pv_persistence.resumes import list_entries


@dataclass(frozen=True)
class ReconcileResult:
    created: int
    updated: int
    removed: int

    @property
    def changed(self) -> bool:
        return bool(self.created or self.updated or self.removed)


@dataclass(frozen=True)
class ChunkRow:
    id: uuid.UUID
    source_type: str
    source_record_id: uuid.UUID
    entry_type: str | None
    text: str
    content_hash: str
    # Filled by the searches. Rank is 1 for the best match.
    score: float | None = None


@dataclass(frozen=True)
class EvidenceStatus:
    chunks: int
    embedded: int
    pending: int


def vector_literal(values: list[float]) -> str:
    """pgvector's text form. Passed as a bound parameter and cast in SQL, so no driver add-on."""
    return "[" + ",".join(repr(float(v)) for v in values) + "]"


def reconcile_profile_chunks(db: Session, owner_id: uuid.UUID) -> ReconcileResult:
    """Make the chunks match the profile entries exactly. Safe to run any number of times."""
    entries = list_entries(db, owner_id)
    existing = {
        chunk.source_record_id: chunk
        for chunk in db.execute(
            select(EvidenceChunk).where(
                EvidenceChunk.owner_user_id == owner_id,
                EvidenceChunk.source_type == SOURCE_PROFILE_ENTRY,
            )
        ).scalars()
    }
    created = updated = 0
    for entry in entries:
        body = clean_chunk_text(render_entry_text(entry.entry_type, entry.data))
        chunk = existing.pop(entry.id, None)
        if not body:
            if chunk is not None:
                db.delete(chunk)
            continue
        digest = content_hash(body)
        if chunk is None:
            db.add(
                EvidenceChunk(
                    owner_user_id=owner_id,
                    source_type=SOURCE_PROFILE_ENTRY,
                    source_record_id=entry.id,
                    entry_type=entry.entry_type,
                    text=body,
                    content_hash=digest,
                )
            )
            created += 1
        elif chunk.content_hash != digest or chunk.entry_type != entry.entry_type:
            chunk.text = body
            chunk.content_hash = digest
            chunk.entry_type = entry.entry_type
            db.flush()
            # The old vector described the old words. Drop it so it cannot answer a search.
            db.execute(
                text(
                    "UPDATE evidence_chunks SET embedding = NULL, embedding_model = NULL, "
                    "embedded_at = NULL, updated_at = now() WHERE id = :id"
                ),
                {"id": chunk.id},
            )
            updated += 1
    for orphan in existing.values():
        db.delete(orphan)
    db.flush()
    return ReconcileResult(created, updated, len(existing))


def enqueue_embedding(db: Session, owner_id: uuid.UUID) -> bool:
    """Queue one embedding task for the owner unless one is already waiting. Returns True if queued.

    A waiting task will read the current chunks when it runs, so a second one adds nothing.
    """
    waiting = db.execute(
        text(
            "SELECT 1 FROM tasks WHERE task_type = :t AND owner_user_id = :o "
            "AND state IN ('queued', 'retry_scheduled') LIMIT 1"
        ),
        {"t": TASK_EMBED_EVIDENCE, "o": owner_id},
    ).first()
    if waiting is not None:
        return False
    queued = enqueue(
        db,
        task_type=TASK_EMBED_EVIDENCE,
        idempotency_key=f"{TASK_EMBED_EVIDENCE}:{owner_id}:{uuid.uuid4().hex}",
        payload={},
        owner_user_id=owner_id,
        max_attempts=5,
    )
    return queued is not None


def sync_evidence(db: Session, owner_id: uuid.UUID) -> ReconcileResult:
    """Call after any profile entry change, in the same transaction."""
    result = reconcile_profile_chunks(db, owner_id)
    if result.changed:
        enqueue_embedding(db, owner_id)
    return result


def pending_embeddings(
    db: Session, owner_id: uuid.UUID, model: str, limit: int
) -> list[tuple[uuid.UUID, str, str]]:
    """Chunks with no vector, or a vector from another model. Returns (id, text, content_hash)."""
    rows = db.execute(
        text(
            "SELECT id, text, content_hash FROM evidence_chunks "
            "WHERE owner_user_id = :o "
            "AND (embedding IS NULL OR embedding_model IS DISTINCT FROM :m) "
            "ORDER BY updated_at, id LIMIT :n"
        ),
        {"o": owner_id, "m": model, "n": limit},
    ).all()
    return [(row.id, row.text, row.content_hash) for row in rows]


def store_embedding(
    db: Session,
    owner_id: uuid.UUID,
    chunk_id: uuid.UUID,
    digest: str,
    values: list[float],
    model: str,
) -> bool:
    """Save a vector only if the chunk still has the text it was computed from."""
    result = db.execute(
        text(
            "UPDATE evidence_chunks SET embedding = CAST(:v AS vector), embedding_model = :m, "
            "embedded_at = now() WHERE id = :id AND owner_user_id = :o AND content_hash = :h"
        ),
        {"v": vector_literal(values), "m": model, "id": chunk_id, "o": owner_id, "h": digest},
    )
    return int(getattr(result, "rowcount", 0) or 0) == 1


def evidence_status(db: Session, owner_id: uuid.UUID, model: str | None) -> EvidenceStatus:
    row = db.execute(
        text(
            "SELECT count(*) AS chunks, "
            "count(*) FILTER (WHERE embedding IS NOT NULL AND embedding_model = :m) AS embedded "
            "FROM evidence_chunks WHERE owner_user_id = :o"
        ),
        {"o": owner_id, "m": model or ""},
    ).one()
    return EvidenceStatus(int(row.chunks), int(row.embedded), int(row.chunks) - int(row.embedded))


def _rows(result: Any) -> list[ChunkRow]:
    return [
        ChunkRow(
            id=r.id,
            source_type=r.source_type,
            source_record_id=r.source_record_id,
            entry_type=r.entry_type,
            text=r.text,
            content_hash=r.content_hash,
            score=float(r.score) if r.score is not None else None,
        )
        for r in result
    ]


def search_keyword(db: Session, owner_id: uuid.UUID, query: str, limit: int) -> list[ChunkRow]:
    """Full-text search. websearch_to_tsquery accepts plain words, quotes, OR and minus safely."""
    return _rows(
        db.execute(
            text(
                "SELECT c.id, c.source_type, c.source_record_id, c.entry_type, c.text, "
                "c.content_hash, ts_rank_cd(c.tsv, q.query) AS score "
                "FROM evidence_chunks c, websearch_to_tsquery('english', :q) AS q(query) "
                "WHERE c.owner_user_id = :o AND c.tsv @@ q.query "
                "ORDER BY score DESC, c.id LIMIT :n"
            ),
            {"q": query, "o": owner_id, "n": limit},
        )
    )


def search_meaning(
    db: Session, owner_id: uuid.UUID, vector: list[float], model: str, limit: int
) -> list[ChunkRow]:
    """Nearest chunks by cosine similarity (1 is identical). Only vectors from the same model."""
    return _rows(
        db.execute(
            text(
                "SELECT id, source_type, source_record_id, entry_type, text, content_hash, "
                "1 - (embedding <=> CAST(:v AS vector)) AS score "
                "FROM evidence_chunks "
                "WHERE owner_user_id = :o AND embedding IS NOT NULL AND embedding_model = :m "
                "ORDER BY embedding <=> CAST(:v AS vector), id LIMIT :n"
            ),
            {"v": vector_literal(vector), "o": owner_id, "m": model, "n": limit},
        )
    )
