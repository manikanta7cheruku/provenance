"""Read an uploaded resume and fill the profile.

Idempotent by design (the queue delivers at least once):
  - a task for a resume that was deleted, or for an older parse generation, does nothing
  - saving replaces parse-created entries and never touches entries the person edited
  - a failure the user can see (unreadable file, model gave nothing usable) is a RESULT, not a
    task failure: the resume is marked failed with a short code and the task completes
  - only transient trouble (the model provider busy or down, storage hiccup) raises TaskFailure
    and is retried with backoff; on the last attempt it becomes a visible failure too

No resume text is logged, stored in task rows or put in an error message.
"""

import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime

from pv_domain.resume import ParseErrorCode, ParseStatus, ReviewStatus
from pv_domain.states import RunState, StepState
from pv_files import ExtractionError, FileStorage, StorageError, build_storage, extract_text
from pv_llm import (
    PROMPT_VERSION,
    GenerationResult,
    LLMError,
    LLMProvider,
    StructuredOutputError,
    build_provider,
    content_hash,
    parse_resume_text,
    record_result,
)
from pv_persistence.evidence import sync_evidence
from pv_persistence.resumes import get_resume, replace_parsed_entries
from pv_persistence.runs import add_step, set_run_state
from pv_persistence.tenancy import tenant_session
from pv_worker.contract import TaskContext, TaskFailure

# Failures where trying again later is the sensible user action. Others need a different file.
_USER_CAN_RETRY = frozenset(
    {
        ParseErrorCode.AI_NOT_CONFIGURED,
        ParseErrorCode.AI_UNAVAILABLE,
        ParseErrorCode.AI_BAD_OUTPUT,
        ParseErrorCode.FILE_MISSING,
    }
)

ProviderFactory = Callable[[], LLMProvider]


def handle_parse_resume(ctx: TaskContext) -> None:
    run_parse(
        ctx,
        storage=build_storage(ctx.settings),
        provider_factory=lambda: build_provider(ctx.settings),
    )


def _record_step(
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
    ctx: TaskContext, owner: uuid.UUID, resume_id: uuid.UUID, code: ParseErrorCode
) -> None:
    """Make the failure visible to the user, then let the task complete normally."""
    with tenant_session(ctx.engine, owner) as db:
        resume = get_resume(db, owner)
        if resume is not None and resume.id == resume_id:
            resume.parse_status = ParseStatus.PARSE_FAILED.value
            resume.error_code = code.value
            resume.updated_at = datetime.now(UTC)
        if ctx.run_id is not None:
            set_run_state(
                db,
                ctx.run_id,
                RunState.FAILED,
                can_retry=code in _USER_CAN_RETRY,
                error_class="PARSE_FAILED",
                error_type="ResumeParse",
                error_message=code.value,
            )


def _transient(
    ctx: TaskContext, owner: uuid.UUID, resume_id: uuid.UUID, code: ParseErrorCode
) -> None:
    """Retry later, unless this was the last attempt."""
    if ctx.attempt >= ctx.max_attempts:
        _finish_failed(ctx, owner, resume_id, code)
        return
    if ctx.run_id is not None:
        with tenant_session(ctx.engine, owner) as db:
            set_run_state(db, ctx.run_id, RunState.RETRYING)
    raise TaskFailure("The reading service is busy. Trying again.", retryable=True)


def run_parse(ctx: TaskContext, *, storage: FileStorage, provider_factory: ProviderFactory) -> None:
    owner = ctx.owner_user_id
    try:
        resume_id = uuid.UUID(str(ctx.args.get("resume_id")))
    except ValueError as exc:
        raise TaskFailure("Invalid resume task arguments.", retryable=False) from exc
    if owner is None:
        raise TaskFailure("The resume task has no owner.", retryable=False)

    with tenant_session(ctx.engine, owner) as db:
        resume = get_resume(db, owner)
        if (
            resume is None
            or resume.id != resume_id
            or resume.parse_generation != ctx.args.get("generation")
        ):
            return  # deleted or replaced since this task was queued: nothing to do
        resume.parse_status = ParseStatus.PARSING.value
        resume.updated_at = datetime.now(UTC)
        storage_key, file_kind = resume.storage_key, resume.file_kind
        if ctx.run_id is not None:
            set_run_state(db, ctx.run_id, RunState.RUNNING)

    # 1. read the stored file
    started = time.perf_counter()
    try:
        data = storage.get(storage_key)
    except StorageError:
        _record_step(ctx, 1, "read_file", StepState.FAILED, started)
        _finish_failed(ctx, owner, resume_id, ParseErrorCode.FILE_MISSING)
        return
    _record_step(ctx, 1, "read_file", StepState.SUCCEEDED, started)

    # 2. extract text (untrusted file: limits and safe parsers live in pv_files)
    started = time.perf_counter()
    try:
        extracted = extract_text(file_kind, data)
    except ExtractionError as exc:
        _record_step(ctx, 2, "extract_text", StepState.FAILED, started)
        _finish_failed(ctx, owner, resume_id, exc.code)
        return
    _record_step(
        ctx, 2, "extract_text", StepState.SUCCEEDED, started, characters=len(extracted.text)
    )
    ctx.extend_lease()

    # 3. one validated model call, then validation and grounding in code
    started = time.perf_counter()
    try:
        provider = provider_factory()
    except LLMError:
        _record_step(ctx, 3, "structure_profile", StepState.FAILED, started)
        _finish_failed(ctx, owner, resume_id, ParseErrorCode.AI_NOT_CONFIGURED)
        return
    model = ctx.settings.llm_model
    input_hash = content_hash(extracted.text)

    def record(calls: list[GenerationResult]) -> None:
        for call in calls:
            record_result(
                ctx.engine,
                ctx.settings,
                provider=provider.name,
                model=model,
                purpose="resume_parse",
                result=call,
                input_hash=input_hash,
                prompt_version=PROMPT_VERSION,
                run_id=ctx.run_id,
                user_id=owner,
            )

    try:
        outcome = parse_resume_text(provider, model=model, resume_text=extracted.text)
    except StructuredOutputError as exc:
        record(exc.calls)
        _record_step(ctx, 3, "structure_profile", StepState.FAILED, started)
        _finish_failed(ctx, owner, resume_id, ParseErrorCode.AI_BAD_OUTPUT)
        return
    except LLMError as exc:
        record_result(
            ctx.engine,
            ctx.settings,
            provider=provider.name,
            model=model,
            purpose="resume_parse",
            result=None,
            input_hash=input_hash,
            prompt_version=PROMPT_VERSION,
            run_id=ctx.run_id,
            user_id=owner,
            error_class="LLM_RETRYABLE" if exc.retryable else "LLM_REJECTED",
        )
        _record_step(ctx, 3, "structure_profile", StepState.FAILED, started)
        if exc.retryable:
            _transient(ctx, owner, resume_id, ParseErrorCode.AI_UNAVAILABLE)
        else:
            _finish_failed(ctx, owner, resume_id, ParseErrorCode.AI_UNAVAILABLE)
        return
    record(outcome.calls)
    _record_step(
        ctx,
        3,
        "structure_profile",
        StepState.SUCCEEDED,
        started,
        calls=len(outcome.calls),
        entries_kept=len(outcome.entries),
        entries_dropped=outcome.dropped,
    )

    # 4. save. Replaces only entries this parse created earlier and the person never edited.
    started = time.perf_counter()
    with tenant_session(ctx.engine, owner) as db:
        resume = get_resume(db, owner)
        if (
            resume is None
            or resume.id != resume_id
            or resume.parse_generation != ctx.args.get("generation")
        ):
            return  # deleted or replaced while the model was working
        stored = replace_parsed_entries(
            db, owner_id=owner, resume_id=resume_id, entries=outcome.entries
        )
        sync_evidence(db, owner)  # chunks follow the new entries in the same transaction
        now = datetime.now(UTC)
        resume.parse_status = ParseStatus.PARSED.value
        resume.review_status = ReviewStatus.PENDING.value
        resume.error_code = None
        resume.page_count = extracted.pages
        resume.char_count = len(extracted.text)
        resume.kept_entry_count = stored
        resume.dropped_entry_count = outcome.dropped
        resume.parser_version = PROMPT_VERSION
        resume.parsed_at = now
        resume.updated_at = now
        if ctx.run_id is not None:
            set_run_state(db, ctx.run_id, RunState.SUCCEEDED)
    _record_step(ctx, 4, "save_profile", StepState.SUCCEEDED, started, entries_stored=stored)
