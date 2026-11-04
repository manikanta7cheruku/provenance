"""Application drafts for a job: ask for one, read them, edit one, delete one.

Everything runs in one tenant session (Row Level Security) and filters by the signed-in owner. A job or
draft that belongs to someone else is "not found", never "forbidden". The text of a draft is the
person's: they can change every word, and every time they do, the claim check runs again against the
evidence that was kept with the draft. Nothing here sends a draft anywhere.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from pv_api.errors import ApiError
from pv_api.schemas import (
    DraftClaimOut,
    DraftEvidenceOut,
    DraftOut,
    DraftQuestionOut,
    DraftsOut,
    DraftStartIn,
)
from pv_api.services import job_service
from pv_domain.analysis import GATE_CATEGORIES, AnalysisStatus
from pv_domain.drafts import (
    COMMON_QUESTIONS,
    DRAFT_ERROR_MESSAGES,
    DRAFT_LABEL,
    KIND_ANSWER,
    MAX_BODY_CHARS,
    MAX_DRAFTS_PER_JOB,
    DraftErrorCode,
    DraftStatus,
    JobHeading,
    clean_body,
    clean_question,
    verify_draft,
    word_count,
)
from pv_domain.failures import FailureClass
from pv_domain.tailoring import job_vocabulary
from pv_persistence.analysis import get_analysis
from pv_persistence.audit import record_audit
from pv_persistence.drafts import (
    count_drafts,
    delete_draft,
    find_draft,
    get_draft,
    list_drafts,
    save_edit,
    start_draft,
)
from pv_persistence.jobs import get_posting
from pv_persistence.models import ApplicationDraft, JobPosting, JobRequirement
from pv_persistence.tenancy import tenant_session
from pv_persistence.workrows import fact_value

MIN_QUESTION_CHARS = 8


def _conflict(code: str, message: str) -> ApiError:
    return ApiError(409, code, message, failure_class=FailureClass.USER_ACTION_REQUIRED)


def _ui_state(status: str) -> str:
    if status == DraftStatus.READY:
        return "ready"
    if status == DraftStatus.FAILED:
        return "failed"
    return "working"


def _draft_out(row: ApplicationDraft) -> DraftOut:
    claims = [
        DraftClaimOut(
            text=str(c.get("text", "")),
            kind=str(c.get("kind", "")),
            supported=bool(c.get("supported")),
            source=c.get("source"),
        )
        for c in row.claims
    ]
    failed = row.status == DraftStatus.FAILED
    return DraftOut(
        id=row.id,
        kind=row.kind,  # type: ignore[arg-type]
        question=row.question,
        body=row.body,
        ui_state=_ui_state(row.status),  # type: ignore[arg-type]
        origin=row.origin,  # type: ignore[arg-type]
        error_message=DRAFT_ERROR_MESSAGES.get(row.error_code or "") if failed else None,
        claims=claims,
        unsupported_count=sum(1 for c in claims if not c.supported),
        word_count=word_count(row.body),
        evidence=[
            DraftEvidenceOut(
                text=str(e.get("text", "")),
                source=str(e.get("source", "")),
                cited=bool(e.get("cited")),
            )
            for e in row.evidence
        ],
        updated_at=row.updated_at,
    )


def _complete(db: Session, posting: JobPosting) -> bool:
    analysis = get_analysis(db, posting.owner_user_id, posting.id)
    return analysis is not None and analysis.status == AnalysisStatus.COMPLETE


def _view(db: Session, posting: JobPosting) -> DraftsOut:
    can = _complete(db, posting)
    return DraftsOut(
        drafts=[_draft_out(r) for r in list_drafts(db, posting.owner_user_id, posting.id)],
        can_write=can,
        blocker=None if can else DRAFT_ERROR_MESSAGES[DraftErrorCode.ANALYSIS_NEEDED],
        questions=[DraftQuestionOut(key=k, text=q) for k, q in COMMON_QUESTIONS],
        max_drafts=MAX_DRAFTS_PER_JOB,
        label=DRAFT_LABEL,
    )


def _posting(db: Session, user_id: uuid.UUID, job_id: uuid.UUID) -> JobPosting:
    posting = get_posting(db, user_id, job_id)
    if posting is None:
        raise job_service.not_found()
    return posting


def view(engine: Engine, user_id: uuid.UUID, job_id: uuid.UUID) -> DraftsOut:
    with tenant_session(engine, user_id) as db:
        return _view(db, _posting(db, user_id, job_id))


def start(
    engine: Engine,
    user_id: uuid.UUID,
    job_id: uuid.UUID,
    payload: DraftStartIn,
    ip_hash: str | None,
) -> DraftsOut:
    question = clean_question(payload.question) if payload.kind == KIND_ANSWER else ""
    if payload.kind == KIND_ANSWER and len(question) < MIN_QUESTION_CHARS:
        raise ApiError(
            422, "VALIDATION_FAILED", "Some details need fixing.",
            failure_class=FailureClass.VALIDATION_FAILED,
            fields={"question": "Write the question you want to answer, or choose one from the list."},
        )  # fmt: skip
    with tenant_session(engine, user_id) as db:
        posting = _posting(db, user_id, job_id)
        if not _complete(db, posting):
            raise _conflict("ANALYSIS_NEEDED", DRAFT_ERROR_MESSAGES[DraftErrorCode.ANALYSIS_NEEDED])
        existing = find_draft(db, user_id, job_id, payload.kind, question)
        if existing is None and count_drafts(db, user_id, job_id) >= MAX_DRAFTS_PER_JOB:
            raise _conflict(
                "TOO_MANY_DRAFTS",
                f"You can keep up to {MAX_DRAFTS_PER_JOB} drafts for one job. Delete one to make room.",
            )
        if existing is not None:
            if existing.status in (DraftStatus.QUEUED, DraftStatus.WORKING):
                raise _conflict("DRAFT_IN_PROGRESS", "This draft is already being written.")
            if existing.origin == "edited" and not payload.replace:
                raise _conflict(
                    "EDITED_DRAFT",
                    "You edited this draft. Writing it again replaces your edits. Confirm to go ahead.",
                )
        start_draft(db, owner_id=user_id, posting_id=job_id, kind=payload.kind, question=question)
        out = _view(db, posting)
    record_audit(
        engine, category="audit", action="application_draft.started", actor_user_id=user_id,
        target_type="job_posting", target_id=str(job_id), ip_hash=ip_hash,
        metadata={"kind": payload.kind},
    )  # fmt: skip
    return out


def _job_words(db: Session, posting: JobPosting) -> set[str]:
    texts = db.execute(
        select(JobRequirement.text).where(
            JobRequirement.owner_user_id == posting.owner_user_id,
            JobRequirement.posting_id == posting.id,
            JobRequirement.category.not_in(list(GATE_CATEGORIES)),
        )
    ).scalars()
    return job_vocabulary(texts)


def edit(
    engine: Engine,
    user_id: uuid.UUID,
    job_id: uuid.UUID,
    draft_id: uuid.UUID,
    body: str,
    ip_hash: str | None,
) -> DraftOut:
    cleaned = clean_body(body)
    if not cleaned or len(cleaned) > MAX_BODY_CHARS:
        raise ApiError(
            422, "VALIDATION_FAILED", "Some details need fixing.",
            failure_class=FailureClass.VALIDATION_FAILED,
            fields={"body": f"A draft can be up to {MAX_BODY_CHARS:,} characters and cannot be empty."},
        )  # fmt: skip
    with tenant_session(engine, user_id) as db:
        posting = _posting(db, user_id, job_id)
        row = get_draft(db, user_id, draft_id)
        if row is None or row.posting_id != job_id:
            raise job_service.not_found()
        if row.status in (DraftStatus.QUEUED, DraftStatus.WORKING):
            raise _conflict("DRAFT_IN_PROGRESS", "This draft is still being written.")
        verification = verify_draft(
            cleaned,
            evidence=[str(e.get("text", "")) for e in row.evidence],
            heading=JobHeading(
                title=posting.title or "",
                company=posting.company or "",
                location=fact_value(posting, "location") or "",
            ),
            job_words=_job_words(db, posting),
        )
        save_edit(
            row,
            body=cleaned,
            claims=[
                {"text": c.text, "kind": c.kind, "supported": c.supported, "source": c.source}
                for c in verification.claims
            ],
        )
        if row.status == DraftStatus.FAILED:
            row.status = DraftStatus.READY.value
            row.error_code = None
        out = _draft_out(row)
    record_audit(
        engine, category="audit", action="application_draft.edited", actor_user_id=user_id,
        target_type="job_posting", target_id=str(job_id), ip_hash=ip_hash,
        metadata={"unsupported": out.unsupported_count},
    )  # fmt: skip
    return out


def remove(
    engine: Engine, user_id: uuid.UUID, job_id: uuid.UUID, draft_id: uuid.UUID, ip_hash: str | None
) -> None:
    with tenant_session(engine, user_id) as db:
        _posting(db, user_id, job_id)
        row = get_draft(db, user_id, draft_id)
        if row is None or row.posting_id != job_id:
            raise job_service.not_found()
        delete_draft(db, row)
    record_audit(
        engine, category="audit", action="application_draft.deleted", actor_user_id=user_id,
        target_type="job_posting", target_id=str(job_id), ip_hash=ip_hash,
    )  # fmt: skip
