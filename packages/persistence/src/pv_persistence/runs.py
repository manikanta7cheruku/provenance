"""Workflow runs and steps. Call these inside tenant_session (Row Level Security applies).

A run records WHAT happened (states, timings, counts, error classes), never the content
of a resume, a job or a model response.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from pv_domain.redaction import error_summary
from pv_domain.states import RunState, StepState
from pv_persistence.models import WorkflowRun, WorkflowStep

_FINISHED_STEP_STATES = (StepState.SUCCEEDED, StepState.FAILED, StepState.SKIPPED)


def create_run(
    db: Session,
    *,
    owner_user_id: uuid.UUID,
    workflow_type: str,
    subject_type: str | None = None,
    subject_id: str | None = None,
) -> WorkflowRun:
    run = WorkflowRun(
        owner_user_id=owner_user_id,
        workflow_type=workflow_type,
        state=RunState.QUEUED.value,
        subject_type=subject_type,
        subject_id=subject_id,
    )
    db.add(run)
    db.flush()
    return run


def set_run_state(
    db: Session,
    run_id: uuid.UUID,
    state: RunState,
    *,
    can_retry: bool = False,
    error_class: str | None = None,
    error_type: str | None = None,
    error_message: str = "",
) -> None:
    """Move a run to a new state. Owner filtering is done by RLS plus the caller's session."""
    run = db.execute(select(WorkflowRun).where(WorkflowRun.id == run_id)).scalar_one_or_none()
    if run is None:
        return
    now = datetime.now(UTC)
    run.state = state.value
    run.updated_at = now
    if state is RunState.RUNNING and run.started_at is None:
        run.started_at = now
    if state in (RunState.SUCCEEDED, RunState.FAILED, RunState.CANCELLED):
        run.finished_at = now
    run.can_retry = can_retry if state is RunState.FAILED else False
    if state is RunState.FAILED:
        run.error_class = error_class
        run.error_summary = error_summary(error_type or "Error", error_message)


def add_step(
    db: Session,
    *,
    run_id: uuid.UUID,
    owner_user_id: uuid.UUID,
    step_name: str,
    ordinal: int,
    state: StepState,
    duration_ms: int | None = None,
    error_class: str | None = None,
    error_message: str = "",
    detail: dict[str, Any] | None = None,
) -> WorkflowStep:
    now = datetime.now(UTC)
    step = WorkflowStep(
        run_id=run_id,
        owner_user_id=owner_user_id,
        step_name=step_name,
        ordinal=ordinal,
        state=state.value,
        started_at=now if state is not StepState.PENDING else None,
        finished_at=now if state in _FINISHED_STEP_STATES else None,
        duration_ms=duration_ms,
        error_class=error_class,
        error_summary=error_summary("Error", error_message) if error_message else None,
        detail=detail or {},
    )
    db.add(step)
    db.flush()
    return step
