"""Search a person's own evidence. Every route is scoped to the signed-in user.

Keyword search always works. Meaning search is added when an AI key and an embedding model are
configured and the entries have been embedded. If it cannot be used the answer says so in a plain
sentence and still returns keyword matches: the search itself never fails because the AI is down.
"""

from fastapi import APIRouter

from pv_api.deps import CsrfUser, CurrentUser, EngineDep, LimiterDep, SettingsDep
from pv_api.schemas import EvidenceHitOut, EvidenceSearchIn, EvidenceSearchOut, EvidenceStatusOut
from pv_llm import embeddings_configured, hybrid_search
from pv_persistence.evidence import evidence_status
from pv_persistence.tenancy import tenant_session

router = APIRouter(prefix="/evidence", tags=["evidence"])


@router.get("/status", response_model=EvidenceStatusOut)
def status(auth: CurrentUser, engine: EngineDep, settings: SettingsDep) -> EvidenceStatusOut:
    configured = embeddings_configured(settings)
    with tenant_session(engine, auth.user_id) as db:
        counts = evidence_status(db, auth.user_id, settings.llm_embedding_model or None)
    return EvidenceStatusOut(
        indexed=counts.chunks,
        embedded=counts.embedded,
        pending=counts.pending,
        meaning_search_configured=configured,
    )


@router.post("/search", response_model=EvidenceSearchOut)
def search(
    payload: EvidenceSearchIn,
    auth: CsrfUser,
    engine: EngineDep,
    settings: SettingsDep,
    limiter: LimiterDep,
) -> EvidenceSearchOut:
    # POST so the query is not stored in URLs or logs; it still only reads, so no audit event.
    limiter.check("evidence_search_user", str(auth.user_id))
    outcome = hybrid_search(engine, settings, auth.user_id, payload.query, limit=payload.limit)
    return EvidenceSearchOut(
        query=payload.query,
        meaning_search_used=outcome.semantic_used,
        note=outcome.note,
        hits=[
            EvidenceHitOut(
                chunk_id=hit.chunk_id,
                entry_id=hit.source_record_id if hit.source_type == "profile_entry" else None,
                source_type=hit.source_type,
                entry_type=hit.entry_type,
                text=hit.text,
                score=round(hit.score, 6),
                matched_by=list(hit.matched_by),
                keyword_rank=hit.keyword_rank,
                meaning_rank=hit.meaning_rank,
                similarity=None if hit.similarity is None else round(hit.similarity, 4),
            )
            for hit in outcome.hits
        ],
    )
