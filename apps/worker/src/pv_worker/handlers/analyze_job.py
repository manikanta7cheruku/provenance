"""Check a pasted job against the person's own evidence, one requirement at a time.

The agent loop lives in pv_llm.evidence_agent. This handler is the durable part around it:

  - Progress is the data. A verdict is stored the moment it is accepted and a question the moment
    it is asked. If the worker dies, the next attempt reads what is stored and does only what is
    left, so nothing is paid for twice.
  - A task for a deleted job, or for an older start of the check, does nothing (resume_seq).
  - A question for the person stops only that requirement. The others still finish. When the
    person answers, the answer is stored as evidence and a new task carries on.
  - Transient provider trouble is retried with backoff. On the last attempt the check is marked
    failed, keeping every verdict earned so far. A missing key is a visible failure at once.

The person's evidence text is never logged and never put in an error message.
"""

import time
import uuid
from collections.abc import Callable
from typing import Any

from sqlalchemy import select

from pv_domain.analysis import (
    GATE_CATEGORIES,
    MAX_MODEL_CALLS_PER_RUN,
    MAX_QUESTIONS_PER_RUN,
    AnalysisErrorCode,
    AnalysisStatus,
    QuestionStatus,
)
from pv_domain.states import RunState, StepState
from pv_llm import (
    GenerationResult,
    LLMError,
    LLMProvider,
    build_provider,
    content_hash,
    hybrid_search,
    record_result,
)
from pv_llm.evidence_agent import (
    PROMPT_VERSION,
    EvidenceItem,
    RequirementInput,
    Resolution,
    RunBudget,
    resolve_requirement,
)
from pv_persistence.analysis import (
    chunk_state,
    create_question,
    fail_analysis,
    finish_analysis,
    list_questions,
    list_verdicts,
    save_verdict,
)
from pv_persistence.evidence import list_chunks_by_type
from pv_persistence.models import JobAnalysis, JobPosting, JobRequirement
from pv_persistence.runs import add_step, set_run_state
from pv_persistence.tenancy import tenant_session
from pv_worker.contract import TaskContext, TaskFailure

ProviderFactory = Callable[[], LLMProvider]
RUN_SECONDS = 600
SEARCH_LIMIT = 6
LIST_LIMIT = 8


class _DbTools:
    """The agent's two reads, scoped to one person. The owner id comes from the task, never from
    the model."""

    def __init__(self, ctx: TaskContext, owner: uuid.UUID, provider: LLMProvider) -> None:
        self._ctx = ctx
        self._owner = owner
        self._provider = provider

    def search(self, query: str) -> list[EvidenceItem]:
        outcome = hybrid_search(
            self._ctx.engine,
            self._ctx.settings,
            self._owner,
            query,
            limit=SEARCH_LIMIT,
            provider=self._provider,
        )
        return [
            EvidenceItem(
                chunk_id=str(hit.chunk_id),
                text=hit.text,
                origin="answer" if hit.source_type == "user_answer" else "profile",
                entry_type=hit.entry_type,
            )
            for hit in outcome.hits
        ]

    def list_entries(self, entry_type: str) -> list[EvidenceItem]:
        with tenant_session(self._ctx.engine, self._owner) as db:
            rows = list_chunks_by_type(db, self._owner, entry_type, LIST_LIMIT)
        return [
            EvidenceItem(
                chunk_id=str(row.id), text=row.text, origin="profile", entry_type=row.entry_type
            )
            for row in rows
        ]


def handle_analyze_job(ctx: TaskContext) -> None:
    run_analyze(ctx, provider_factory=lambda: build_provider(ctx.settings))


def _step(
    ctx: TaskContext, ordinal: int, name: str, state: StepState, started: float, **detail: int
) -> None:
    if ctx.run_id is None or ctx.owner_user_id is None:
        return
    with tenant_session(ctx.engine, ctx.owner_user_id) as db:
        add_step(
            db,
            run_id=ctx.run_id,
            owner_user_id=ctx.owner_user_id,
            step_name=name,
            ordinal=ordinal,
            state=state,
            duration_ms=round((time.perf_counter() - started) * 1000),
            detail=dict(detail),
        )


def _fail(
    ctx: TaskContext, owner: uuid.UUID, analysis_id: uuid.UUID, code: AnalysisErrorCode
) -> None:
    with tenant_session(ctx.engine, owner) as db:
        analysis = db.get(JobAnalysis, analysis_id)
        if analysis is not None and analysis.owner_user_id == owner:
            fail_analysis(db, analysis, code)


def _transient(ctx: TaskContext, owner: uuid.UUID, analysis_id: uuid.UUID) -> None:
    if ctx.attempt >= ctx.max_attempts:
        _fail(ctx, owner, analysis_id, AnalysisErrorCode.AI_UNAVAILABLE)
        return
    if ctx.run_id is not None:
        with tenant_session(ctx.engine, owner) as db:
            set_run_state(db, ctx.run_id, RunState.RETRYING)
    raise TaskFailure("The checking service is busy. Trying again.", retryable=True)


def _requirement_input(r: JobRequirement) -> RequirementInput:
    return RequirementInput(
        text=r.text, kind=r.kind, category=r.category, years_min=r.years_min, quote=r.quote
    )


def run_analyze(ctx: TaskContext, *, provider_factory: ProviderFactory) -> None:
    owner = ctx.owner_user_id
    try:
        analysis_id = uuid.UUID(str(ctx.args.get("analysis_id")))
    except ValueError as exc:
        raise TaskFailure("Invalid analysis task arguments.", retryable=False) from exc
    if owner is None:
        raise TaskFailure("The analysis task has no owner.", retryable=False)
    seq: Any = ctx.args.get("seq")

    started = time.perf_counter()
    with tenant_session(ctx.engine, owner) as db:
        analysis = get_analysis_by_id(db, owner, analysis_id)
        if analysis is None or analysis.resume_seq != seq:
            return  # deleted, or the check was started again since this task was queued
        analysis.status = AnalysisStatus.ANALYZING.value
        if ctx.run_id is not None:
            set_run_state(db, ctx.run_id, RunState.RUNNING)
        posting = db.get(JobPosting, analysis.posting_id)
        requirements = (
            list(
                db.execute(
                    select(JobRequirement)
                    .where(
                        JobRequirement.owner_user_id == owner,
                        JobRequirement.posting_id == analysis.posting_id,
                    )
                    .order_by(JobRequirement.ordinal)
                ).scalars()
            )
            if posting is not None
            else []
        )
        done = {v.requirement_id for v in list_verdicts(db, owner, analysis_id)}
        questions = {q.requirement_id: q for q in list_questions(db, owner, analysis_id)}
    todo = [
        r
        for r in requirements
        if r.category not in GATE_CATEGORIES
        and r.id not in done
        and (r.id not in questions or questions[r.id].status == QuestionStatus.ANSWERED.value)
    ]
    todo.sort(key=lambda r: (r.kind != "required", r.ordinal))
    pending_now = sum(1 for q in questions.values() if q.status == QuestionStatus.PENDING.value)
    _step(ctx, 1, "load_requirements", StepState.SUCCEEDED, started, to_check=len(todo),
          already_done=len(done))  # fmt: skip
    ctx.extend_lease()

    started = time.perf_counter()
    try:
        provider = provider_factory()
    except LLMError:
        _step(ctx, 2, "check_requirements", StepState.FAILED, started)
        _fail(ctx, owner, analysis_id, AnalysisErrorCode.AI_NOT_CONFIGURED)
        return
    model = ctx.settings.llm_model
    tools = _DbTools(ctx, owner, provider)
    budget = RunBudget(
        model_calls_left=MAX_MODEL_CALLS_PER_RUN,
        questions_left=max(0, MAX_QUESTIONS_PER_RUN - pending_now),
        deadline=time.monotonic() + RUN_SECONDS,
    )
    model_calls = tool_calls = 0
    checked = asked = 0

    for requirement in todo:
        ctx.extend_lease()
        input_hash = content_hash(requirement.text)

        def record(calls: list[GenerationResult], _hash: str = input_hash) -> None:
            for call in calls:
                record_result(
                    ctx.engine,
                    ctx.settings,
                    provider=provider.name,
                    model=model,
                    purpose="evidence_agent",
                    result=call,
                    input_hash=_hash,
                    prompt_version=PROMPT_VERSION,
                    run_id=ctx.run_id,
                    user_id=owner,
                )

        answered = (
            requirement.id in questions
            and questions[requirement.id].status == QuestionStatus.ANSWERED.value
        )
        try:
            resolution = resolve_requirement(
                provider,
                model=model,
                requirement=_requirement_input(requirement),
                tools=tools,
                budget=budget,
                can_ask=not answered,
                record=record,
            )
        except LLMError as exc:
            record_result(
                ctx.engine,
                ctx.settings,
                provider=provider.name,
                model=model,
                purpose="evidence_agent",
                result=None,
                input_hash=input_hash,
                prompt_version=PROMPT_VERSION,
                run_id=ctx.run_id,
                user_id=owner,
                error_class="LLM_RETRYABLE" if exc.retryable else "LLM_REJECTED",
            )
            _step(ctx, 2, "check_requirements", StepState.FAILED, started, checked=checked)
            _bank(ctx, owner, analysis_id, model_calls, tool_calls)
            if exc.retryable:
                _transient(ctx, owner, analysis_id)
            else:
                _fail(ctx, owner, analysis_id, AnalysisErrorCode.AI_UNAVAILABLE)
            return
        model_calls += resolution.model_calls
        tool_calls += resolution.tool_calls
        if not _store(ctx, owner, analysis_id, seq, requirement, resolution):
            return  # started again or deleted while the model was working
        if resolution.question is not None:
            asked += 1
        else:
            checked += 1
    _step(ctx, 2, "check_requirements", StepState.SUCCEEDED, started, checked=checked,
          questions=asked, model_calls=model_calls)  # fmt: skip

    started = time.perf_counter()
    with tenant_session(ctx.engine, owner) as db:
        analysis = get_analysis_by_id(db, owner, analysis_id)
        if analysis is None or analysis.resume_seq != seq:
            return
        waiting = any(
            q.status == QuestionStatus.PENDING.value for q in list_questions(db, owner, analysis_id)
        )
        finish_analysis(
            db,
            analysis,
            status=AnalysisStatus.NEEDS_USER_INPUT if waiting else AnalysisStatus.COMPLETE,
            model_calls=model_calls,
            tool_calls=tool_calls,
            prompt_version=PROMPT_VERSION,
        )
    _step(ctx, 3, "finish", StepState.SUCCEEDED, started)


def get_analysis_by_id(db: Any, owner: uuid.UUID, analysis_id: uuid.UUID) -> JobAnalysis | None:
    row = db.get(JobAnalysis, analysis_id)
    return row if row is not None and row.owner_user_id == owner else None


def _bank(
    ctx: TaskContext, owner: uuid.UUID, analysis_id: uuid.UUID, model_calls: int, tool_calls: int
) -> None:
    """Keep the usage counts of work that was done before a failure."""
    with tenant_session(ctx.engine, owner) as db:
        analysis = get_analysis_by_id(db, owner, analysis_id)
        if analysis is not None:
            analysis.model_calls += model_calls
            analysis.tool_calls += tool_calls


def _store(
    ctx: TaskContext,
    owner: uuid.UUID,
    analysis_id: uuid.UUID,
    seq: Any,
    requirement: JobRequirement,
    resolution: Resolution,
) -> bool:
    """Save the verdict or the question. False if the check was replaced in the meantime."""
    with tenant_session(ctx.engine, owner) as db:
        analysis = get_analysis_by_id(db, owner, analysis_id)
        if analysis is None or analysis.resume_seq != seq:
            return False
        if resolution.question is not None:
            create_question(db, analysis, requirement.id, resolution.question)
            return True
        accepted = resolution.verdict
        if accepted is None:
            return True
        hashes = chunk_state(db, owner, [uuid.UUID(c.chunk_id) for c in resolution.citations])
        citations = [
            {
                "chunk_id": c.chunk_id,
                "quote": c.quote,
                "content_hash": hashes.get(uuid.UUID(c.chunk_id), c.content_hash),
                "source_type": c.source_type,
                "entry_type": c.entry_type,
            }
            for c in resolution.citations
        ]
        save_verdict(
            db,
            analysis,
            requirement.id,
            verdict=accepted.verdict.value,
            evidence_kind=accepted.evidence_kind.value if accepted.evidence_kind else None,
            reason_code=resolution.reason_code,
            reason=accepted.reason if accepted.citations else "",
            citations=citations,
            capped=accepted.capped,
            steps=resolution.steps,
        )
    return True
