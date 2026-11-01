"""Tailoring a resume to a job: start it, show the suggestions, edit, accept or reject them.

Same rules as the rest of the studio: one tenant session per call (Row Level Security), every
query filtered by the signed-in owner, and "not found" for anything that belongs to someone else.

The one rule that matters here: a suggestion is applied to the resume only when it passes the
grounding check (pv_domain.tailoring). That is checked again at the moment of accepting, against
the evidence the suggestion cites as it is now, so nothing that was blocked can slip through, and a
person's own edit of a suggestion is held to the same standard.
"""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from pv_api.errors import ApiError
from pv_api.schemas import (
    ResumeDocumentSummaryOut,
    SuggestionAcceptedOut,
    TailorCitationOut,
    TailorClaimOut,
    TailorGapOut,
    TailoringOut,
    TailorJobOut,
    TailorRequirementOut,
    TailorSuggestionOut,
)
from pv_api.services.job_service import not_found
from pv_api.services.studio_service import _summary, _validation_error
from pv_domain.analysis import (
    GATE_CATEGORIES,
    REASON_MESSAGES,
    AnalysisStatus,
    Verdict,
)
from pv_domain.failures import FailureClass
from pv_domain.resume_doc import ResumeDocError, validate_document
from pv_domain.tailoring import (
    TAILORING_ERROR_MESSAGES,
    SuggestionStatus,
    TailoringStatus,
    apply_unit,
    clean_lines,
    find_unit,
    job_vocabulary,
    verify_text,
)
from pv_persistence.analysis import get_analysis, list_verdicts
from pv_persistence.audit import record_audit
from pv_persistence.jobs import get_posting, list_requirements
from pv_persistence.models import (
    EvidenceChunk,
    JobAnalysis,
    JobPosting,
    ResumeTailoring,
    TailoringSuggestion,
)
from pv_persistence.studio import RevisionConflict, get_document, save_document
from pv_persistence.tailoring import (
    decide,
    get_suggestion,
    get_tailoring,
    get_tailoring_by_id,
    list_suggestions,
    start_tailoring,
)
from pv_persistence.tenancy import tenant_session


def _conflict(code: str, message: str) -> ApiError:
    return ApiError(409, code, message, failure_class=FailureClass.USER_ACTION_REQUIRED)


def _ui_state(status: str) -> str:
    if status == TailoringStatus.READY:
        return "ready"
    if status == TailoringStatus.FAILED:
        return "failed"
    return "working"


def _suggestion_out(
    s: TailoringSuggestion, requirement_text: dict[str, str]
) -> TailorSuggestionOut:
    return TailorSuggestionOut(
        id=s.id,
        unit_id=s.unit_id,
        kind=s.kind,
        label=s.label,
        before_lines=list(s.before_lines),
        after_lines=list(s.after_lines),
        reason=s.reason,
        requirements=[
            TailorRequirementOut(id=uuid.UUID(r), text=requirement_text[r])
            for r in s.requirement_ids
            if r in requirement_text
        ],
        citations=[
            TailorCitationOut(
                chunk_id=uuid.UUID(c["chunk_id"]),
                quote=c["quote"],
                source=c.get("source", "profile"),
                entry_type=c.get("entry_type"),
            )
            for c in s.citations
        ],
        claims=[
            TailorClaimOut(
                text=c["text"],
                kind=c["kind"],
                supported=bool(c["supported"]),
                source=c.get("source"),
            )
            for c in s.claims
        ],
        blocked=s.blocked,
        edited=s.edited,
        status=s.status,
    )


def _view(db: Session, row: ResumeTailoring, posting: JobPosting) -> TailoringOut:
    owner = row.owner_user_id
    requirements = list_requirements(db, owner, posting.id)
    text_of = {str(r.id): r.text for r in requirements}
    analysis = get_analysis(db, owner, posting.id)
    verdicts = (
        {v.requirement_id: v for v in list_verdicts(db, owner, analysis.id)} if analysis else {}
    )
    unclaimed = [
        TailorGapOut(
            text=r.text,
            reason=REASON_MESSAGES.get(
                (verdicts[r.id].reason_code or "") if r.id in verdicts else "",
                "Nothing in your profile confirms this, so it was not added to your resume.",
            ),
        )
        for r in requirements
        if r.category not in GATE_CATEGORIES
        and (r.id not in verdicts or verdicts[r.id].verdict not in (Verdict.MET, Verdict.PARTIAL))
    ]
    suggestions = (
        [_suggestion_out(s, text_of) for s in list_suggestions(db, owner, row.id)]
        if row.status == TailoringStatus.READY
        else []
    )
    return TailoringOut(
        id=row.id,
        job_id=posting.id,
        job_title=posting.title,
        company=posting.company,
        ui_state=_ui_state(row.status),
        error_message=TAILORING_ERROR_MESSAGES.get(row.error_code or "")
        if row.error_code
        else None,
        suggestions=suggestions,
        unclaimed=unclaimed[:8],
    )


def jobs(engine: Engine, user_id: uuid.UUID) -> list[TailorJobOut]:
    """The jobs whose evidence check is finished: the only ones a resume can be tailored to."""
    with tenant_session(engine, user_id) as db:
        rows = db.execute(
            select(JobPosting)
            .join(JobAnalysis, JobAnalysis.posting_id == JobPosting.id)
            .where(
                JobPosting.owner_user_id == user_id,
                JobAnalysis.owner_user_id == user_id,
                JobAnalysis.status == AnalysisStatus.COMPLETE.value,
            )
            .order_by(JobPosting.created_at.desc())
        ).scalars()
        return [TailorJobOut(job_id=p.id, title=p.title, company=p.company) for p in rows]


def start(
    engine: Engine, user_id: uuid.UUID, doc_id: uuid.UUID, job_id: uuid.UUID, ip_hash: str | None
) -> TailoringOut:
    with tenant_session(engine, user_id) as db:
        if get_document(db, user_id, doc_id) is None:
            raise not_found()
        posting = get_posting(db, user_id, job_id)
        if posting is None:
            raise not_found()
        analysis = get_analysis(db, user_id, job_id)
        if analysis is None or analysis.status != AnalysisStatus.COMPLETE:
            raise _conflict("ANALYSIS_NEEDED", TAILORING_ERROR_MESSAGES["ANALYSIS_NEEDED"])
        existing = get_tailoring(db, user_id, doc_id, job_id)
        if existing is not None and existing.status in (
            TailoringStatus.QUEUED,
            TailoringStatus.WORKING,
        ):
            raise _conflict("TAILORING_IN_PROGRESS", "Suggestions are already being made.")
        row = start_tailoring(db, user_id, doc_id, job_id)
        out = _view(db, row, posting)
    record_audit(
        engine, category="audit", action="resume.tailoring_started", actor_user_id=user_id,
        target_type="resume_document", target_id=str(doc_id), ip_hash=ip_hash,
    )  # fmt: skip
    return out


def get_for_job(
    engine: Engine, user_id: uuid.UUID, doc_id: uuid.UUID, job_id: uuid.UUID
) -> TailoringOut | None:
    with tenant_session(engine, user_id) as db:
        if get_document(db, user_id, doc_id) is None:
            raise not_found()
        posting = get_posting(db, user_id, job_id)
        if posting is None:
            raise not_found()
        row = get_tailoring(db, user_id, doc_id, job_id)
        return _view(db, row, posting) if row is not None else None


def _load(
    db: Session,
    user_id: uuid.UUID,
    doc_id: uuid.UUID,
    tailoring_id: uuid.UUID,
    suggestion_id: uuid.UUID,
) -> tuple[ResumeTailoring, JobPosting, TailoringSuggestion]:
    row = get_tailoring_by_id(db, user_id, tailoring_id)
    if row is None or row.document_id != doc_id:
        raise not_found()
    posting = get_posting(db, user_id, row.posting_id)
    suggestion = get_suggestion(db, user_id, tailoring_id, suggestion_id)
    if posting is None or suggestion is None:
        raise not_found()
    return row, posting, suggestion


def _pending(suggestion: TailoringSuggestion) -> None:
    if suggestion.status != SuggestionStatus.PENDING:
        raise _conflict("ALREADY_DECIDED", "This suggestion was already dealt with.")


def _evidence_texts(db: Session, user_id: uuid.UUID, suggestion: TailoringSuggestion) -> list[str]:
    ids = [uuid.UUID(c["chunk_id"]) for c in suggestion.citations]
    if not ids:
        return []
    return [
        text
        for (text,) in db.execute(
            select(EvidenceChunk.text).where(
                EvidenceChunk.owner_user_id == user_id, EvidenceChunk.id.in_(ids)
            )
        )
    ]


def _verify(
    db: Session,
    user_id: uuid.UUID,
    posting: JobPosting,
    suggestion: TailoringSuggestion,
    lines: list[str],
) -> tuple[list[dict[str, Any]], bool]:
    words = job_vocabulary(
        r.text
        for r in list_requirements(db, user_id, posting.id)
        if r.category not in GATE_CATEGORIES
    )
    result = verify_text(
        lines,
        before=suggestion.before_lines,
        evidence=_evidence_texts(db, user_id, suggestion),
        job_words=words,
    )
    claims = [
        {"text": c.text, "kind": c.kind, "supported": c.supported, "source": c.source}
        for c in result.claims
    ]
    return claims, result.blocked


def edit(
    engine: Engine,
    user_id: uuid.UUID,
    doc_id: uuid.UUID,
    tailoring_id: uuid.UUID,
    suggestion_id: uuid.UUID,
    after_lines: list[str],
) -> TailorSuggestionOut:
    lines = clean_lines(after_lines)
    if lines is None:
        raise ApiError(
            422, "VALIDATION_FAILED", "Some details need fixing.",
            failure_class=FailureClass.VALIDATION_FAILED,
            fields={"after_lines": "Write between 1 and 8 lines, each up to 300 characters."},
        )  # fmt: skip
    with tenant_session(engine, user_id) as db:
        row, posting, suggestion = _load(db, user_id, doc_id, tailoring_id, suggestion_id)
        _pending(suggestion)
        if suggestion.kind == "paragraph" and len(lines) != 1:
            raise ApiError(
                422, "VALIDATION_FAILED", "Some details need fixing.",
                failure_class=FailureClass.VALIDATION_FAILED,
                fields={"after_lines": "A paragraph is one piece of text."},
            )  # fmt: skip
        claims, blocked = _verify(db, user_id, posting, suggestion, lines)
        suggestion.after_lines = lines
        suggestion.claims = claims
        suggestion.blocked = blocked
        suggestion.edited = True
        text_of = {str(r.id): r.text for r in list_requirements(db, user_id, posting.id)}
        return _suggestion_out(suggestion, text_of)


def reject(
    engine: Engine,
    user_id: uuid.UUID,
    doc_id: uuid.UUID,
    tailoring_id: uuid.UUID,
    suggestion_id: uuid.UUID,
) -> TailorSuggestionOut:
    with tenant_session(engine, user_id) as db:
        row, posting, suggestion = _load(db, user_id, doc_id, tailoring_id, suggestion_id)
        _pending(suggestion)
        decide(db, suggestion, SuggestionStatus.REJECTED)
        text_of = {str(r.id): r.text for r in list_requirements(db, user_id, posting.id)}
        return _suggestion_out(suggestion, text_of)


def accept(
    engine: Engine,
    user_id: uuid.UUID,
    doc_id: uuid.UUID,
    tailoring_id: uuid.UUID,
    suggestion_id: uuid.UUID,
    revision: int,
    ip_hash: str | None,
) -> SuggestionAcceptedOut:
    with tenant_session(engine, user_id) as db:
        row, posting, suggestion = _load(db, user_id, doc_id, tailoring_id, suggestion_id)
        _pending(suggestion)
        document = get_document(db, user_id, doc_id)
        if document is None:
            raise not_found()
        # Checked again now, against the evidence as it is now. A stored result is not trusted.
        claims, blocked = _verify(db, user_id, posting, suggestion, list(suggestion.after_lines))
        suggestion.claims, suggestion.blocked = claims, blocked
        if blocked:
            raise _conflict(
                "UNSUPPORTED_CLAIMS",
                "This change adds something your evidence does not support. Edit it or reject it.",
            )
        content = dict(document.content)
        unit = find_unit(content, suggestion.unit_id)
        changed = (
            apply_unit(content, unit, suggestion.after_lines, suggestion.before_lines)
            if unit is not None and unit.kind == suggestion.kind
            else None
        )
        if changed is None:
            raise _conflict(
                "RESUME_CHANGED",
                "That part of your resume changed after this was suggested. Ask again.",
            )
        try:
            clean = validate_document(changed)
        except ResumeDocError as exc:
            raise _validation_error(exc) from exc
        try:
            saved = save_document(db, document, clean, expected_revision=revision, checkpoint=True)
        except RevisionConflict as conflict:
            raise _conflict(
                "REVISION_CONFLICT",
                "This resume was changed somewhere else. Reload to see the latest version.",
            ) from conflict
        decide(db, suggestion, SuggestionStatus.ACCEPTED)
        text_of = {str(r.id): r.text for r in list_requirements(db, user_id, posting.id)}
        out = SuggestionAcceptedOut(
            suggestion=_suggestion_out(suggestion, text_of),
            document=ResumeDocumentSummaryOut.model_validate(_summary(saved)),
        )
    record_audit(
        engine, category="audit", action="resume.suggestion_accepted", actor_user_id=user_id,
        target_type="resume_document", target_id=str(doc_id), ip_hash=ip_hash,
        metadata={"edited": suggestion.edited},
    )  # fmt: skip
    return out
