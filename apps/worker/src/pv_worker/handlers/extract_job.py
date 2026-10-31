"""Read a pasted job posting and store its facts and requirements.

Same shape as the resume parser, for the same reasons:
  - a task for a deleted posting, or for an older analysis generation, does nothing
  - saving replaces the stored analysis, so running the task twice leaves one result
  - a failure the person can act on (nothing found, the model gave nothing usable, AI not set up)
    is a RESULT: the posting is marked failed with a short code and the task completes
  - only transient trouble raises TaskFailure and is retried with backoff, and on the last
    attempt it becomes a visible failure too

The posting text is never logged and never put in an error message.
"""

import time
import uuid
from collections.abc import Callable
from typing import Any

from pv_domain.job import PROMPT_VERSION, JobErrorCode, JobParseStatus
from pv_domain.states import RunState, StepState
from pv_llm import (
    GenerationResult,
    LLMError,
    LLMProvider,
    StructuredOutputError,
    build_provider,
    content_hash,
    extract_job_text,
    record_result,
)
from pv_persistence.jobs import fail_run, get_posting, mark_failed, save_extraction
from pv_persistence.runs import add_step, set_run_state
from pv_persistence.tenancy import tenant_session
from pv_worker.contract import TaskContext, TaskFailure

_USER_CAN_RETRY = frozenset(
    {JobErrorCode.AI_NOT_CONFIGURED, JobErrorCode.AI_UNAVAILABLE, JobErrorCode.AI_BAD_OUTPUT}
)

ProviderFactory = Callable[[], LLMProvider]


def handle_extract_job(ctx: TaskContext) -> None:
    run_extract(ctx, provider_factory=lambda: build_provider(ctx.settings))


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


def _finish_failed(
    ctx: TaskContext, owner: uuid.UUID, posting_id: uuid.UUID, code: JobErrorCode
) -> None:
    with tenant_session(ctx.engine, owner) as db:
        posting = get_posting(db, owner, posting_id)
        if posting is not None:
            mark_failed(db, posting, code)
        fail_run(db, ctx.run_id, code, can_retry=code in _USER_CAN_RETRY)


def _transient(
    ctx: TaskContext, owner: uuid.UUID, posting_id: uuid.UUID, code: JobErrorCode
) -> None:
    if ctx.attempt >= ctx.max_attempts:
        _finish_failed(ctx, owner, posting_id, code)
        return
    if ctx.run_id is not None:
        with tenant_session(ctx.engine, owner) as db:
            set_run_state(db, ctx.run_id, RunState.RETRYING)
    raise TaskFailure("The reading service is busy. Trying again.", retryable=True)


def run_extract(ctx: TaskContext, *, provider_factory: ProviderFactory) -> None:
    owner = ctx.owner_user_id
    try:
        posting_id = uuid.UUID(str(ctx.args.get("posting_id")))
    except ValueError as exc:
        raise TaskFailure("Invalid job task arguments.", retryable=False) from exc
    if owner is None:
        raise TaskFailure("The job task has no owner.", retryable=False)
    generation: Any = ctx.args.get("generation")

    started = time.perf_counter()
    with tenant_session(ctx.engine, owner) as db:
        posting = get_posting(db, owner, posting_id)
        if posting is None or posting.analysis_generation != generation:
            return  # deleted or replaced since this task was queued: nothing to do
        posting.parse_status = JobParseStatus.EXTRACTING.value
        raw_text = posting.raw_text
        if ctx.run_id is not None:
            set_run_state(db, ctx.run_id, RunState.RUNNING)
    _step(ctx, 1, "read_posting", StepState.SUCCEEDED, started, characters=len(raw_text))
    ctx.extend_lease()

    started = time.perf_counter()
    try:
        provider = provider_factory()
    except LLMError:
        _step(ctx, 2, "extract_requirements", StepState.FAILED, started)
        _finish_failed(ctx, owner, posting_id, JobErrorCode.AI_NOT_CONFIGURED)
        return
    model = ctx.settings.llm_model
    input_hash = content_hash(raw_text)

    def record(calls: list[GenerationResult]) -> None:
        for call in calls:
            record_result(
                ctx.engine,
                ctx.settings,
                provider=provider.name,
                model=model,
                purpose="job_extraction",
                result=call,
                input_hash=input_hash,
                prompt_version=PROMPT_VERSION,
                run_id=ctx.run_id,
                user_id=owner,
            )

    try:
        outcome = extract_job_text(provider, model=model, posting_text=raw_text)
    except StructuredOutputError as exc:
        record(exc.calls)
        _step(ctx, 2, "extract_requirements", StepState.FAILED, started)
        _finish_failed(ctx, owner, posting_id, JobErrorCode.AI_BAD_OUTPUT)
        return
    except LLMError as exc:
        record_result(
            ctx.engine,
            ctx.settings,
            provider=provider.name,
            model=model,
            purpose="job_extraction",
            result=None,
            input_hash=input_hash,
            prompt_version=PROMPT_VERSION,
            run_id=ctx.run_id,
            user_id=owner,
            error_class="LLM_RETRYABLE" if exc.retryable else "LLM_REJECTED",
        )
        _step(ctx, 2, "extract_requirements", StepState.FAILED, started)
        if exc.retryable:
            _transient(ctx, owner, posting_id, JobErrorCode.AI_UNAVAILABLE)
        else:
            _finish_failed(ctx, owner, posting_id, JobErrorCode.AI_UNAVAILABLE)
        return
    record(outcome.calls)
    grounded = outcome.grounded
    _step(ctx, 2, "extract_requirements", StepState.SUCCEEDED, started, calls=len(outcome.calls),
          requirements_proposed=grounded.requirements_proposed)  # fmt: skip

    started = time.perf_counter()
    if not grounded.requirements:
        _step(
            ctx,
            3,
            "check_quotes",
            StepState.FAILED,
            started,
            requirements_dropped=grounded.requirements_dropped,
        )
        code = (
            JobErrorCode.AI_BAD_OUTPUT
            if grounded.requirements_proposed
            else JobErrorCode.NO_REQUIREMENTS
        )
        _finish_failed(ctx, owner, posting_id, code)
        return
    kept, dropped = len(grounded.requirements), grounded.requirements_dropped
    _step(ctx, 3, "check_quotes", StepState.SUCCEEDED, started, requirements_kept=kept,
          requirements_dropped=dropped, facts_dropped=grounded.facts_dropped)  # fmt: skip

    started = time.perf_counter()
    with tenant_session(ctx.engine, owner) as db:
        posting = get_posting(db, owner, posting_id)
        if posting is None or posting.analysis_generation != generation:
            return  # deleted or replaced while the model was working
        save_extraction(db, posting, grounded, prompt_version=PROMPT_VERSION)
        if ctx.run_id is not None:
            set_run_state(db, ctx.run_id, RunState.SUCCEEDED)
    _step(ctx, 4, "save_analysis", StepState.SUCCEEDED, started)
