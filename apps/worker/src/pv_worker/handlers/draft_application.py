"""Write an application draft (a cover note or an answer) for one job, and check every claim in it.

The model writes (pv_llm.draft). Code decides what is kept and what the person is told:

  - a draft is made only for a job whose evidence check is complete, and only from the evidence that
    check found for requirements the person meets or partly meets. A job with nothing supported has
    nothing true to write from, and that is a visible result, not a made-up draft
  - the requirements with no support are named to the model only so it does not claim them
  - every claim in the draft (a number, a name or tool, a word the job asked for) is checked against
    that evidence and the job heading (pv_domain.drafts.verify_draft). The claims that are in neither
    are stored with the draft so the person sees them. Nothing is hidden and nothing is sent

The task never touches a resume or sends anything. A task for an older request, or for a deleted
draft, does nothing. A missing key is a visible failure at once. Provider trouble is retried with
backoff and the last attempt becomes a visible failure. The job and evidence text is never logged and
never put in an error message.
"""

import time
import uuid
from collections.abc import Callable
from typing import Any

from sqlalchemy import select

from pv_domain.analysis import GATE_CATEGORIES, AnalysisStatus, Verdict
from pv_domain.drafts import (
    MAX_BODY_CHARS,
    MIN_BODY_CHARS,
    DraftErrorCode,
    JobHeading,
    clean_body,
    verify_draft,
)
from pv_domain.states import RunState, StepState
from pv_domain.tailoring import job_vocabulary
from pv_llm import (
    LLMError,
    LLMProvider,
    StructuredOutputError,
    build_provider,
    content_hash,
    record_result,
)
from pv_llm.draft import PROMPT_VERSION, EvidenceShown, RequirementShown, draft_text
from pv_persistence.analysis import get_analysis, list_verdicts
from pv_persistence.drafts import fail_draft, finish_draft, get_draft, mark_working
from pv_persistence.jobs import get_posting
from pv_persistence.models import EvidenceChunk, JobRequirement
from pv_persistence.runs import add_step, set_run_state
from pv_persistence.tenancy import tenant_session
from pv_persistence.workrows import fact_value
from pv_worker.contract import TaskContext, TaskFailure

ProviderFactory = Callable[[], LLMProvider]
MAX_EVIDENCE_SHOWN = 12
STORED_EVIDENCE_CHARS = 700


def handle_draft_application(ctx: TaskContext) -> None:
    run_draft(ctx, provider_factory=lambda: build_provider(ctx.settings))


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
    ctx: TaskContext, owner: uuid.UUID, draft_id: uuid.UUID, code: DraftErrorCode, calls: int = 0
) -> None:
    with tenant_session(ctx.engine, owner) as db:
        row = get_draft(db, owner, draft_id)
        if row is not None:
            fail_draft(row, code.value, model_calls=calls)


def _transient(ctx: TaskContext, owner: uuid.UUID, draft_id: uuid.UUID, calls: int) -> None:
    if ctx.attempt >= ctx.max_attempts:
        _fail(ctx, owner, draft_id, DraftErrorCode.AI_UNAVAILABLE, calls)
        return
    if ctx.run_id is not None:
        with tenant_session(ctx.engine, owner) as db:
            set_run_state(db, ctx.run_id, RunState.RETRYING)
    raise TaskFailure("The writing service is busy. Trying again.", retryable=True)


def run_draft(ctx: TaskContext, *, provider_factory: ProviderFactory) -> None:
    owner = ctx.owner_user_id
    if owner is None:
        raise TaskFailure("The draft task has no owner.", retryable=False)
    try:
        draft_id = uuid.UUID(str(ctx.args.get("draft_id")))
    except ValueError as exc:
        raise TaskFailure("Invalid draft task arguments.", retryable=False) from exc
    seq: Any = ctx.args.get("seq")

    started = time.perf_counter()
    with tenant_session(ctx.engine, owner) as db:
        row = get_draft(db, owner, draft_id)
        if row is None or row.seq != seq:
            return  # deleted, or asked for again since this task was queued
        mark_working(row)
        if ctx.run_id is not None:
            set_run_state(db, ctx.run_id, RunState.RUNNING)
        kind, question = row.kind, row.question
        posting = get_posting(db, owner, row.posting_id)
        analysis = get_analysis(db, owner, row.posting_id) if posting else None
        complete = analysis is not None and analysis.status == AnalysisStatus.COMPLETE
        requirements = (
            list(
                db.execute(
                    select(JobRequirement)
                    .where(
                        JobRequirement.owner_user_id == owner,
                        JobRequirement.posting_id == row.posting_id,
                    )
                    .order_by(JobRequirement.ordinal)
                ).scalars()
            )
            if posting
            else []
        )
        verdicts = (
            {v.requirement_id: v for v in list_verdicts(db, owner, analysis.id)} if analysis else {}
        )
        cited_ids = sorted(
            {
                uuid.UUID(c["chunk_id"])
                for v in verdicts.values()
                if v.verdict in (Verdict.MET, Verdict.PARTIAL)
                for c in v.citations
            }
        )[:MAX_EVIDENCE_SHOWN]
        chunks = {
            c.id: c
            for c in db.execute(
                select(EvidenceChunk).where(
                    EvidenceChunk.owner_user_id == owner, EvidenceChunk.id.in_(cited_ids)
                )
            ).scalars()
        }
        evidence = [
            (
                cid,
                chunks[cid].text,
                "answer" if chunks[cid].source_type == "user_answer" else "profile",
            )
            for cid in cited_ids
            if cid in chunks
        ]
        heading = (
            JobHeading(
                title=posting.title or "",
                company=posting.company or "",
                location=fact_value(posting, "location") or "",
            )
            if posting
            else JobHeading("", "", "")
        )
    if posting is None or not complete:
        _fail(ctx, owner, draft_id, DraftErrorCode.ANALYSIS_NEEDED)
        return

    claimable = [
        r
        for r in requirements
        if r.category not in GATE_CATEGORIES
        and r.id in verdicts
        and verdicts[r.id].verdict in (Verdict.MET, Verdict.PARTIAL)
    ]
    unsupported = [
        r.text for r in requirements if r.category not in GATE_CATEGORIES and r not in claimable
    ]
    _step(
        ctx,
        1,
        "load",
        StepState.SUCCEEDED,
        started,
        supported=len(claimable),
        evidence=len(evidence),
    )
    ctx.extend_lease()
    if not claimable or not evidence:
        _fail(ctx, owner, draft_id, DraftErrorCode.NO_EVIDENCE)
        return

    started = time.perf_counter()
    try:
        provider = provider_factory()
    except LLMError:
        _step(ctx, 2, "write", StepState.FAILED, started)
        _fail(ctx, owner, draft_id, DraftErrorCode.AI_NOT_CONFIGURED)
        return
    model = ctx.settings.llm_model
    labelled = {f"R{i}": r for i, r in enumerate(claimable, start=1)}
    labelled_evidence = {f"E{i}": item for i, item in enumerate(evidence, start=1)}
    input_hash = content_hash(f"{draft_id}:{seq}")

    def record(calls: list[Any], error_class: str | None = None) -> None:
        for call in calls or [None]:
            record_result(
                ctx.engine,
                ctx.settings,
                provider=provider.name,
                model=model,
                purpose="draft_application",
                result=call,
                input_hash=input_hash,
                prompt_version=PROMPT_VERSION,
                run_id=ctx.run_id,
                user_id=owner,
                error_class=error_class,
            )

    try:
        outcome = draft_text(
            provider,
            model=model,
            kind=kind,
            question=question,
            heading=" | ".join(heading.texts()) or "(no heading)",
            requirements=[
                RequirementShown(label, r.text, verdicts[r.id].verdict)
                for label, r in labelled.items()
            ],
            unsupported=unsupported,
            evidence=[EvidenceShown(label, item[1]) for label, item in labelled_evidence.items()],
        )
    except StructuredOutputError as exc:
        record(exc.calls)
        _step(ctx, 2, "write", StepState.FAILED, started)
        _fail(ctx, owner, draft_id, DraftErrorCode.AI_BAD_OUTPUT, len(exc.calls))
        return
    except LLMError as exc:
        record([], "LLM_RETRYABLE" if exc.retryable else "LLM_REJECTED")
        _step(ctx, 2, "write", StepState.FAILED, started)
        if exc.retryable:
            _transient(ctx, owner, draft_id, 0)
        else:
            _fail(ctx, owner, draft_id, DraftErrorCode.AI_UNAVAILABLE)
        return
    record(outcome.calls)
    _step(ctx, 2, "write", StepState.SUCCEEDED, started, model_calls=len(outcome.calls))

    started = time.perf_counter()
    body = clean_body(outcome.value.text)
    if not MIN_BODY_CHARS <= len(body) <= MAX_BODY_CHARS:
        _fail(ctx, owner, draft_id, DraftErrorCode.AI_BAD_OUTPUT, len(outcome.calls))
        return
    cited = {e for e in outcome.value.evidence if e in labelled_evidence}
    verification = verify_draft(
        body,
        evidence=[item[1] for item in evidence],
        heading=heading,
        job_words=job_vocabulary(r.text for r in requirements if r.category not in GATE_CATEGORIES),
    )
    stored_evidence = [
        {
            "chunk_id": str(item[0]),
            "text": item[1][:STORED_EVIDENCE_CHARS],
            "source": item[2],
            "cited": label in cited,
        }
        for label, item in labelled_evidence.items()
    ]
    claims = [
        {"text": c.text, "kind": c.kind, "supported": c.supported, "source": c.source}
        for c in verification.claims
    ]
    with tenant_session(ctx.engine, owner) as db:
        row = get_draft(db, owner, draft_id)
        if row is None or row.seq != seq:
            return
        finish_draft(
            row,
            body=body,
            evidence=stored_evidence,
            claims=claims,
            prompt_version=PROMPT_VERSION,
            model_calls=len(outcome.calls),
        )
    _step(
        ctx, 3, "verify", StepState.SUCCEEDED, started,
        claims=len(claims), unsupported=sum(1 for c in claims if not c["supported"]),
    )  # fmt: skip
