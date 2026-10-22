"""What a user may see about their own runs. Metadata only: states, timings, counts, model usage.

Row Level Security hides other users' runs. The explicit owner filter in every query is the
second layer (ADR-0015): both must fail before another user's run could appear.
"""

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.engine import Engine

from pv_api.errors import ApiError
from pv_api.schemas import LlmCallOut, RunDetail, RunList, RunStepOut, RunSummary
from pv_domain.failures import FailureClass
from pv_domain.states import (
    RunState,
    StepState,
    ui_state_for_run,
    ui_state_for_step,
    workflow_label,
)
from pv_persistence.models import LlmCall, WorkflowRun, WorkflowStep
from pv_persistence.tenancy import tenant_session

MAX_PAGE = 100


def _duration_ms(started: datetime | None, finished: datetime | None) -> int | None:
    if started is None or finished is None:
        return None
    return max(0, round((finished - started).total_seconds() * 1000))


def _summary(run: WorkflowRun) -> RunSummary:
    ui = ui_state_for_run(RunState(run.state), can_retry=run.can_retry)
    return RunSummary(
        id=run.id,
        workflow_type=run.workflow_type,
        workflow_label=workflow_label(run.workflow_type),
        ui_state=ui.value,
        created_at=run.created_at,
        started_at=run.started_at,
        finished_at=run.finished_at,
        duration_ms=_duration_ms(run.started_at, run.finished_at),
    )


def list_runs(engine: Engine, user_id: uuid.UUID, *, limit: int, offset: int) -> RunList:
    limit = max(1, min(limit, MAX_PAGE))
    offset = max(0, offset)
    with tenant_session(engine, user_id) as db:
        total = db.execute(
            select(func.count())
            .select_from(WorkflowRun)
            .where(WorkflowRun.owner_user_id == user_id)
        ).scalar_one()
        runs = (
            db.execute(
                select(WorkflowRun)
                .where(WorkflowRun.owner_user_id == user_id)
                .order_by(WorkflowRun.created_at.desc(), WorkflowRun.id)
                .limit(limit)
                .offset(offset)
            )
            .scalars()
            .all()
        )
        return RunList(items=[_summary(r) for r in runs], total=total, limit=limit, offset=offset)


def get_run(engine: Engine, user_id: uuid.UUID, run_id: uuid.UUID) -> RunDetail:
    with tenant_session(engine, user_id) as db:
        run = db.execute(
            select(WorkflowRun).where(
                WorkflowRun.id == run_id, WorkflowRun.owner_user_id == user_id
            )
        ).scalar_one_or_none()
        if run is None:
            # Unknown and foreign ids look identical.
            raise ApiError(404, "NOT_FOUND", "Not found.", failure_class=FailureClass.PERMANENT)
        steps = (
            db.execute(
                select(WorkflowStep)
                .where(WorkflowStep.run_id == run_id, WorkflowStep.owner_user_id == user_id)
                .order_by(WorkflowStep.ordinal)
            )
            .scalars()
            .all()
        )
        # llm_calls is a system table without RLS, so the owner filter here is the only guard.
        calls = (
            db.execute(
                select(LlmCall)
                .where(LlmCall.run_id == run_id, LlmCall.user_id == user_id)
                .order_by(LlmCall.created_at)
            )
            .scalars()
            .all()
        )
        return RunDetail(
            run=_summary(run),
            error_summary=run.error_summary,
            steps=[
                RunStepOut(
                    ordinal=s.ordinal,
                    step_name=s.step_name,
                    ui_state=ui_state_for_step(StepState(s.state)).value,
                    duration_ms=s.duration_ms,
                    error_summary=s.error_summary,
                )
                for s in steps
            ],
            llm_calls=[
                LlmCallOut(
                    purpose=c.purpose,
                    provider=c.provider,
                    model=c.model,
                    prompt_version=c.prompt_version,
                    input_tokens=c.input_tokens,
                    output_tokens=c.output_tokens,
                    estimated_cost_usd=float(c.estimated_cost_usd),
                    latency_ms=c.latency_ms,
                    status=c.status,
                )
                for c in calls
            ],
        )
