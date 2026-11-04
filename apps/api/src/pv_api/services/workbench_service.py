"""The workbench: the list of a person's jobs, their decisions, notes, saved views, bulk moves, and
adding a job found on a permitted source.

Everything runs in one tenant session (Row Level Security) and filters by the signed-in owner. A job
or view that belongs to someone else is "not found", never "forbidden". Which move is allowed is
decided by pv_domain.pipeline. The list, its filters and its sort are applied here, not in the
browser, so the rules are in one place and tested.
"""

import uuid
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from pv_api.errors import ApiError
from pv_api.schemas import (
    BulkItemOut,
    BulkOut,
    DecisionOut,
    DecisionResultOut,
    FacetsOut,
    JobCreatedOut,
    ViewIn,
    ViewOut,
    WorkbenchOut,
    WorkRowOut,
)
from pv_api.services import job_service
from pv_api.services.decision_view import decision_out, eligibility_state
from pv_config import Settings
from pv_domain.eligibility import evaluate_eligibility
from pv_domain.failures import FailureClass
from pv_domain.job import JobParseStatus, job_ui_state
from pv_domain.job_facts import posting_facts_from_record
from pv_domain.job_import import ACQUISITION_SOURCE, build_draft
from pv_domain.pipeline import (
    ACTION_LABELS,
    MAX_BULK,
    MAX_NOTE_CHARS,
    REVERSE,
    Action,
    TransitionError,
    WorkQuery,
    WorkRow,
    clean_query,
    facets,
    query_to_dict,
    transition,
)
from pv_domain.pipeline import (
    select as select_rows,
)
from pv_persistence.audit import record_audit
from pv_persistence.jobs import get_posting, list_postings, load_seeker
from pv_persistence.models import JobDecision, JobPosting, JobSource, SourceJob
from pv_persistence.source_jobs import usable_where
from pv_persistence.tenancy import tenant_session
from pv_persistence.workbench import (
    ViewError,
    create_view,
    decisions_for,
    fit_bands,
    get_decision,
    get_view,
    list_views,
    previous_before_applied,
    record_move,
    set_note,
    state_of,
)

MAX_ROWS = 500


def _row(
    posting: JobPosting, decision: JobDecision | None, eligibility: str | None, band: str | None
) -> WorkRow:
    return WorkRow(
        id=str(posting.id),
        title=posting.title or "",
        company=posting.company or "",
        source_name=posting.source_name,
        acquisition_method=posting.acquisition_method,
        work_mode=job_service._fact_value(posting, "work_mode"),
        location=job_service._fact_value(posting, "location") or "",
        employment_type=job_service._fact_value(posting, "employment_type"),
        seniority=job_service._fact_value(posting, "seniority"),
        eligibility=eligibility,
        band=band,
        reading=job_ui_state(posting.parse_status).value,
        state=state_of(decision).value,
        created_at=posting.created_at,
        applied_at=decision.applied_at if decision else None,
        note=decision.note if decision else "",
    )


def _load(db: Session, owner: uuid.UUID) -> tuple[list[JobPosting], list[WorkRow]]:
    postings = list_postings(db, owner, limit=MAX_ROWS + 1)[: MAX_ROWS + 1]
    decisions = decisions_for(db, owner)
    prefs, years = load_seeker(db, owner)
    eligibility: dict[uuid.UUID, str] = {}
    for posting in postings:
        if posting.parse_status == JobParseStatus.EXTRACTED:
            facts = posting_facts_from_record(
                posting.raw_text, posting.title, posting.company, posting.facts
            )
            eligibility[posting.id] = evaluate_eligibility(facts, prefs, years).state.value
    bands = fit_bands(db, owner, {p: s != "not_eligible" for p, s in eligibility.items()})
    rows = [_row(p, decisions.get(p.id), eligibility.get(p.id), bands.get(p.id)) for p in postings]
    return postings, rows


def _row_out(row: WorkRow, decision: JobDecision | None) -> WorkRowOut:
    return WorkRowOut(
        id=uuid.UUID(row.id),
        title=row.title or None,
        company=row.company or None,
        source_name=row.source_name,
        acquisition_method=row.acquisition_method,
        work_mode=row.work_mode,
        location=row.location or None,
        employment_type=row.employment_type,
        seniority=row.seniority,
        eligibility=row.eligibility,
        band=row.band,
        reading=row.reading,  # type: ignore[arg-type]
        decision=decision_out(decision, row.eligibility),
        has_note=bool(row.note),
        created_at=row.created_at,
    )


def _facets_out(rows: list[WorkRow], query: WorkQuery) -> FacetsOut:
    f = facets(rows, query)
    return FacetsOut(
        views=f.views,
        work_modes=f.work_modes,
        eligibility=f.eligibility,
        bands=f.bands,
        employment_types=f.employment_types,
        seniorities=f.seniorities,
        sources=f.sources,
    )


def workbench(engine: Engine, user_id: uuid.UUID, raw: dict[str, Any]) -> WorkbenchOut:
    query = clean_query(raw)
    with tenant_session(engine, user_id) as db:
        postings, rows = _load(db, user_id)
        truncated = len(postings) > MAX_ROWS
        rows = rows[:MAX_ROWS]
        decisions = decisions_for(db, user_id)
        chosen = select_rows(rows, query)
        return WorkbenchOut(
            rows=[_row_out(r, decisions.get(uuid.UUID(r.id))) for r in chosen],
            total=len(chosen),
            query=query_to_dict(query),
            facets=_facets_out(rows, query),
            truncated=truncated,
        )


# ---- decisions


def _error(error: TransitionError) -> ApiError:
    return ApiError(
        409,
        "DECISION_NOT_ALLOWED" if error.code == "not_allowed" else "NOT_ELIGIBLE",
        error.message,
        failure_class=FailureClass.USER_ACTION_REQUIRED,
    )


def _apply(
    db: Session,
    posting: JobPosting,
    action: Action,
    applied_on: date | None,
) -> JobDecision:
    owner = posting.owner_user_id
    decision = get_decision(db, owner, posting.id)
    state = state_of(decision)
    previous = (
        previous_before_applied(db, owner, posting.id) if action is Action.UNDO_APPLIED else None
    )
    target = transition(
        state, action, eligibility=eligibility_state(db, posting), previous=previous
    )
    applied_at: datetime | None = None
    if action is Action.MARK_APPLIED:
        today = datetime.now(UTC).date()
        if applied_on is not None and applied_on > today:
            raise ApiError(
                422,
                "VALIDATION_FAILED",
                "Some details need fixing.",
                failure_class=FailureClass.VALIDATION_FAILED,
                fields={"applied_on": "The day you applied cannot be in the future."},
            )
        day = applied_on or today
        applied_at = datetime(day.year, day.month, day.day, 12, 0, tzinfo=UTC)
    return record_move(
        db,
        owner_id=owner,
        posting_id=posting.id,
        action=action,
        to_state=target,
        applied_at=applied_at,
    )


def decide(
    engine: Engine,
    user_id: uuid.UUID,
    job_id: uuid.UUID,
    action: Action,
    applied_on: date | None,
    ip_hash: str | None,
) -> DecisionResultOut:
    with tenant_session(engine, user_id) as db:
        posting = get_posting(db, user_id, job_id)
        if posting is None:
            raise job_service.not_found()
        try:
            decision = _apply(db, posting, action, applied_on)
        except TransitionError as error:
            raise _error(error) from error
        out = decision_out(decision, eligibility_state(db, posting))
    record_audit(
        engine, category="audit", action="job.decision", actor_user_id=user_id,
        target_type="job_posting", target_id=str(job_id), ip_hash=ip_hash,
        metadata={"decision": action.value},
    )  # fmt: skip
    reverse = REVERSE.get(action)
    return DecisionResultOut(
        decision=out,
        undo=reverse.value if reverse else None,
        undo_label=ACTION_LABELS[reverse] if reverse else None,
    )


def bulk(
    engine: Engine,
    user_id: uuid.UUID,
    ids: list[uuid.UUID],
    action: Action,
    ip_hash: str | None,
) -> BulkOut:
    if len(ids) > MAX_BULK:
        raise ApiError(
            422, "VALIDATION_FAILED", f"Choose up to {MAX_BULK} jobs at a time.",
            failure_class=FailureClass.VALIDATION_FAILED,
        )  # fmt: skip
    results: list[BulkItemOut] = []
    with tenant_session(engine, user_id) as db:
        for job_id in ids:
            posting = get_posting(db, user_id, job_id)
            if posting is None:
                results.append(BulkItemOut(id=job_id, ok=False, state=None, message="Not found."))
                continue
            try:
                with db.begin_nested():
                    decision = _apply(db, posting, action, None)
            except TransitionError as error:
                current = state_of(get_decision(db, user_id, job_id))
                results.append(
                    BulkItemOut(id=job_id, ok=False, state=current.value, message=error.message)
                )
                continue
            results.append(BulkItemOut(id=job_id, ok=True, state=decision.state, message=None))
    done = sum(1 for r in results if r.ok)
    if done:
        record_audit(
            engine, category="audit", action="job.decision_bulk", actor_user_id=user_id,
            ip_hash=ip_hash, metadata={"decision": action.value, "count": done},
        )  # fmt: skip
    reverse = REVERSE.get(action)
    return BulkOut(
        results=results,
        done=done,
        skipped=len(results) - done,
        undo=reverse.value if reverse and done else None,
        undo_label=ACTION_LABELS[reverse] if reverse and done else None,
    )


def save_note(engine: Engine, user_id: uuid.UUID, job_id: uuid.UUID, note: str) -> DecisionOut:
    cleaned = "".join(ch for ch in note if ch == "\n" or ch >= " " and ch != "\x7f").strip()
    if len(cleaned) > MAX_NOTE_CHARS:
        raise ApiError(
            422, "VALIDATION_FAILED", "Some details need fixing.",
            failure_class=FailureClass.VALIDATION_FAILED,
            fields={"note": f"A note can be up to {MAX_NOTE_CHARS:,} characters."},
        )  # fmt: skip
    with tenant_session(engine, user_id) as db:
        posting = get_posting(db, user_id, job_id)
        if posting is None:
            raise job_service.not_found()
        decision = set_note(db, user_id, job_id, cleaned)
        return decision_out(decision, eligibility_state(db, posting))


# ---- saved views


def _view_out(view: Any) -> ViewOut:
    return ViewOut(id=view.id, name=view.name, query=view.query, created_at=view.created_at)


def views(engine: Engine, user_id: uuid.UUID) -> list[ViewOut]:
    with tenant_session(engine, user_id) as db:
        return [_view_out(v) for v in list_views(db, user_id)]


def save_view(engine: Engine, user_id: uuid.UUID, payload: ViewIn) -> ViewOut:
    stored = query_to_dict(clean_query(payload.query))
    with tenant_session(engine, user_id) as db:
        try:
            view = create_view(db, user_id, payload.name, stored)
        except ViewError as error:
            raise ApiError(
                409 if error.code == "name_taken" else 422,
                "VIEW_NAME_TAKEN" if error.code == "name_taken" else "VALIDATION_FAILED",
                error.message,
                failure_class=FailureClass.USER_ACTION_REQUIRED,
                fields={"name": error.message},
            ) from error
        return _view_out(view)


def delete_view(engine: Engine, user_id: uuid.UUID, view_id: uuid.UUID) -> None:
    with tenant_session(engine, user_id) as db:
        view = get_view(db, user_id, view_id)
        if view is None:
            raise job_service.not_found()
        db.delete(view)


# ---- a job found on a permitted source


def add_source_job(
    engine: Engine,
    settings: Settings,
    user_id: uuid.UUID,
    source_job_id: uuid.UUID,
    ip_hash: str | None,
) -> JobCreatedOut:
    """Make a private posting from a job found on a source that may be used right now."""
    today = datetime.now(UTC).date()
    with Session(engine) as db:
        found = db.execute(
            select(SourceJob, JobSource)
            .join(JobSource, JobSource.key == SourceJob.source_key)
            .where(
                SourceJob.id == source_job_id,
                SourceJob.closed_at.is_(None),
                *usable_where(today, settings.source_review_window_days),
            )
        ).first()
    if found is None:
        raise job_service.not_found()
    job, _source = found
    try:
        draft = build_draft(
            title=job.title,
            company=job.company_name or "",
            location=job.location or "",
            link=job.url,
            source=None,
            description=job.description or "",
            default_source="Company career page",
        )
    except ValueError as problem:
        raise ApiError(
            422,
            "VALIDATION_FAILED",
            "This listing has too little text to read. Open the original posting, copy the "
            "description and paste it instead.",
            failure_class=FailureClass.VALIDATION_FAILED,
        ) from problem
    return job_service.create_from_draft(
        engine,
        user_id=user_id,
        draft=draft,
        acquisition=ACQUISITION_SOURCE,
        audit_action="job.added_from_source",
        ip_hash=ip_hash,
    )
