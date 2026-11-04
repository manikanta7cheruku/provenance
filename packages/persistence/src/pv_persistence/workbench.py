"""The workbench: decisions about jobs, their log, notes, saved views, and the fit band for a list.

Call everything here inside tenant_session (Row Level Security applies). Every statement also
filters by owner. The rules for which move is allowed live in pv_domain.pipeline. This module stores
what that decided.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from pv_domain.analysis import GATE_CATEGORIES, AnalysisStatus, Verdict, score_analysis
from pv_domain.pipeline import MAX_VIEWS, Action, DecisionState
from pv_persistence.models import (
    JobAnalysis,
    JobDecision,
    JobDecisionEvent,
    JobRequirement,
    RequirementVerdict,
    WorkbenchView,
)


class ViewError(Exception):
    """A saved view could not be made. code is short and stable, message is for the person."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def decisions_for(db: Session, owner_id: uuid.UUID) -> dict[uuid.UUID, JobDecision]:
    rows = db.execute(select(JobDecision).where(JobDecision.owner_user_id == owner_id)).scalars()
    return {r.posting_id: r for r in rows}


def get_decision(db: Session, owner_id: uuid.UUID, posting_id: uuid.UUID) -> JobDecision | None:
    return db.execute(
        select(JobDecision).where(
            JobDecision.owner_user_id == owner_id, JobDecision.posting_id == posting_id
        )
    ).scalar_one_or_none()


def state_of(decision: JobDecision | None) -> DecisionState:
    return DecisionState(decision.state) if decision else DecisionState.NEW


def previous_before_applied(
    db: Session, owner_id: uuid.UUID, posting_id: uuid.UUID
) -> DecisionState | None:
    """Where the job was just before it was last marked applied."""
    state = db.execute(
        select(JobDecisionEvent.from_state)
        .where(
            JobDecisionEvent.owner_user_id == owner_id,
            JobDecisionEvent.posting_id == posting_id,
            JobDecisionEvent.to_state == DecisionState.APPLIED.value,
        )
        .order_by(JobDecisionEvent.created_at.desc(), JobDecisionEvent.id)
        .limit(1)
    ).scalar_one_or_none()
    try:
        return DecisionState(state) if state else None
    except ValueError:
        return None


def record_move(
    db: Session,
    *,
    owner_id: uuid.UUID,
    posting_id: uuid.UUID,
    action: Action,
    to_state: DecisionState,
    applied_at: datetime | None = None,
) -> JobDecision:
    """Store a move that pv_domain.pipeline already allowed, and log it."""
    decision = get_decision(db, owner_id, posting_id)
    from_state = state_of(decision)
    now = datetime.now(UTC)
    if decision is None:
        decision = JobDecision(owner_user_id=owner_id, posting_id=posting_id)
        db.add(decision)
    decision.state = to_state.value
    decision.updated_at = now
    if to_state is DecisionState.APPLIED:
        decision.applied_at = applied_at or now
    elif action is Action.UNDO_APPLIED:
        decision.applied_at = None
    db.add(
        JobDecisionEvent(
            posting_id=posting_id,
            owner_user_id=owner_id,
            action=action.value,
            from_state=from_state.value,
            to_state=to_state.value,
        )
    )
    db.flush()
    return decision


def set_note(db: Session, owner_id: uuid.UUID, posting_id: uuid.UUID, note: str) -> JobDecision:
    decision = get_decision(db, owner_id, posting_id)
    if decision is None:
        decision = JobDecision(owner_user_id=owner_id, posting_id=posting_id, state="new")
        db.add(decision)
    decision.note = note
    decision.updated_at = datetime.now(UTC)
    db.flush()
    return decision


def fit_bands(
    db: Session, owner_id: uuid.UUID, eligible: dict[uuid.UUID, bool]
) -> dict[uuid.UUID, str]:
    """The fit band of each posting whose evidence check is complete, worked out the same way the
    job page does (pv_domain.analysis.score_analysis), in three queries for the whole list.

    eligible maps posting id to whether the person may be scored (no hard rule stands in the way).
    Postings with no complete check are left out."""
    if not eligible:
        return {}
    analyses = {
        a.id: a.posting_id
        for a in db.execute(
            select(JobAnalysis).where(
                JobAnalysis.owner_user_id == owner_id,
                JobAnalysis.posting_id.in_(list(eligible)),
                JobAnalysis.status == AnalysisStatus.COMPLETE.value,
            )
        ).scalars()
    }
    if not analyses:
        return {}
    posting_ids = list(analyses.values())
    requirements = list(
        db.execute(
            select(JobRequirement).where(
                JobRequirement.owner_user_id == owner_id,
                JobRequirement.posting_id.in_(posting_ids),
                JobRequirement.category.not_in(list(GATE_CATEGORIES)),
            )
        ).scalars()
    )
    verdicts: dict[uuid.UUID, str] = {
        v.requirement_id: v.verdict
        for v in db.execute(
            select(RequirementVerdict).where(
                RequirementVerdict.owner_user_id == owner_id,
                RequirementVerdict.analysis_id.in_(list(analyses)),
            )
        ).scalars()
    }
    by_posting: dict[uuid.UUID, list[tuple[str, str]]] = {p: [] for p in posting_ids}
    for req in requirements:
        by_posting[req.posting_id].append(
            (req.kind, verdicts.get(req.id, Verdict.NOT_VERIFIED.value))
        )
    return {
        posting: score_analysis(
            items, eligible=eligible.get(posting, True), eligibility_note=""
        ).band.value
        for posting, items in by_posting.items()
    }


# ---- saved views


def list_views(db: Session, owner_id: uuid.UUID) -> list[WorkbenchView]:
    return list(
        db.execute(
            select(WorkbenchView)
            .where(WorkbenchView.owner_user_id == owner_id)
            .order_by(WorkbenchView.created_at, WorkbenchView.id)
        ).scalars()
    )


def get_view(db: Session, owner_id: uuid.UUID, view_id: uuid.UUID) -> WorkbenchView | None:
    return db.execute(
        select(WorkbenchView).where(
            WorkbenchView.owner_user_id == owner_id, WorkbenchView.id == view_id
        )
    ).scalar_one_or_none()


def create_view(
    db: Session, owner_id: uuid.UUID, name: str, query: dict[str, Any]
) -> WorkbenchView:
    if len(list_views(db, owner_id)) >= MAX_VIEWS:
        raise ViewError(
            "too_many", f"You can keep up to {MAX_VIEWS} saved views. Delete one to make room."
        )
    view = WorkbenchView(owner_user_id=owner_id, name=name, query=query)
    try:
        with db.begin_nested():
            db.add(view)
            db.flush()
    except IntegrityError as exc:
        raise ViewError("name_taken", "You already have a saved view with that name.") from exc
    return view
