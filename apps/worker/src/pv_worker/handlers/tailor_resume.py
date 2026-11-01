"""Suggest changes to a resume for one job, and check every suggestion before it is shown.

The model proposes (pv_llm.tailor). Code decides what is kept:

  - only parts of the resume that tailoring may change are shown to the model (pv_domain.tailoring)
  - only requirements the earlier evidence check confirmed (met or partial) are offered as things to
    emphasise. The rest are listed as "do not claim", and every word the job asks for counts as a
    claim that must be backed by the resume part or the cited evidence
  - the evidence a suggestion may cite is the evidence that check found, named by labels code
    assigned, so a suggestion cannot cite anything else
  - each suggestion is verified claim by claim. One that adds a fact is stored as blocked, with the
    claims and which were not found, so the person can see why. It is never applied silently.

The resume text is never logged and never put in an error message. A task for an older start of
the run, or a deleted resume, does nothing. A missing key is a visible failure at once. Provider
trouble is retried with backoff, and the last attempt marks the run failed, keeping the resume
unchanged (this task never writes to the resume).
"""

import time
import uuid
from collections.abc import Callable
from typing import Any

from sqlalchemy import select

from pv_domain.analysis import GATE_CATEGORIES, AnalysisStatus, Verdict
from pv_domain.states import RunState, StepState
from pv_domain.tailoring import (
    MAX_SUGGESTIONS,
    TailoringErrorCode,
    clean_lines,
    extract_units,
    job_vocabulary,
    verify_text,
)
from pv_llm import LLMError, LLMProvider, build_provider, content_hash, record_result
from pv_llm.tailor import (
    PROMPT_VERSION,
    EvidenceShown,
    PartShown,
    RequirementShown,
    propose,
)
from pv_persistence.analysis import get_analysis, list_verdicts
from pv_persistence.models import (
    EvidenceChunk,
    JobRequirement,
    ResumeDocument,
    ResumeTailoring,
)
from pv_persistence.runs import add_step, set_run_state
from pv_persistence.tailoring import (
    add_suggestion,
    fail_tailoring,
    finish_tailoring,
    get_tailoring_by_id,
    mark_working,
)
from pv_persistence.tenancy import tenant_session
from pv_worker.contract import TaskContext, TaskFailure

ProviderFactory = Callable[[], LLMProvider]
QUOTE_CHARS = 240


def handle_tailor_resume(ctx: TaskContext) -> None:
    run_tailor(ctx, provider_factory=lambda: build_provider(ctx.settings))


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
    ctx: TaskContext,
    owner: uuid.UUID,
    tailoring_id: uuid.UUID,
    code: TailoringErrorCode,
    model_calls: int = 0,
) -> None:
    with tenant_session(ctx.engine, owner) as db:
        row = get_tailoring_by_id(db, owner, tailoring_id)
        if row is not None:
            fail_tailoring(db, row, code.value, model_calls=model_calls)


def _transient(ctx: TaskContext, owner: uuid.UUID, tailoring_id: uuid.UUID, calls: int) -> None:
    if ctx.attempt >= ctx.max_attempts:
        _fail(ctx, owner, tailoring_id, TailoringErrorCode.AI_UNAVAILABLE, calls)
        return
    if ctx.run_id is not None:
        with tenant_session(ctx.engine, owner) as db:
            set_run_state(db, ctx.run_id, RunState.RETRYING)
    raise TaskFailure("The suggestion service is busy. Trying again.", retryable=True)


def run_tailor(ctx: TaskContext, *, provider_factory: ProviderFactory) -> None:
    owner = ctx.owner_user_id
    try:
        tailoring_id = uuid.UUID(str(ctx.args.get("tailoring_id")))
    except ValueError as exc:
        raise TaskFailure("Invalid tailoring task arguments.", retryable=False) from exc
    if owner is None:
        raise TaskFailure("The tailoring task has no owner.", retryable=False)
    seq: Any = ctx.args.get("seq")

    started = time.perf_counter()
    with tenant_session(ctx.engine, owner) as db:
        row = get_tailoring_by_id(db, owner, tailoring_id)
        if row is None or row.seq != seq:
            return  # deleted, or started again since this task was queued
        mark_working(db, row)
        if ctx.run_id is not None:
            set_run_state(db, ctx.run_id, RunState.RUNNING)
        document = db.get(ResumeDocument, row.document_id)
        content: dict[str, Any] = dict(document.content) if document is not None else {}
        analysis = get_analysis(db, owner, row.posting_id)
        complete = analysis is not None and analysis.status == AnalysisStatus.COMPLETE
        requirements = list(
            db.execute(
                select(JobRequirement)
                .where(
                    JobRequirement.owner_user_id == owner,
                    JobRequirement.posting_id == row.posting_id,
                )
                .order_by(JobRequirement.ordinal)
            ).scalars()
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
        )
        chunks = {
            c.id: c
            for c in db.execute(
                select(EvidenceChunk).where(
                    EvidenceChunk.owner_user_id == owner, EvidenceChunk.id.in_(cited_ids)
                )
            ).scalars()
        }
        chunk_info = {
            cid: (c.text, "answer" if c.source_type == "user_answer" else "profile", c.entry_type)
            for cid, c in chunks.items()
        }
    if document is None or not complete:
        _fail(ctx, owner, tailoring_id, TailoringErrorCode.ANALYSIS_NEEDED)
        return

    units = extract_units(content)
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
    _step(ctx, 1, "load", StepState.SUCCEEDED, started, parts=len(units), supported=len(claimable))
    ctx.extend_lease()
    if not units or not claimable:
        with tenant_session(ctx.engine, owner) as db:
            row = get_tailoring_by_id(db, owner, tailoring_id)
            if row is not None and row.seq == seq:
                finish_tailoring(db, row, model_calls=0, prompt_version=PROMPT_VERSION)
        return

    started = time.perf_counter()
    try:
        provider = provider_factory()
    except LLMError:
        _step(ctx, 2, "propose", StepState.FAILED, started)
        _fail(ctx, owner, tailoring_id, TailoringErrorCode.AI_NOT_CONFIGURED)
        return
    model = ctx.settings.llm_model

    labelled_reqs = {f"R{i}": r for i, r in enumerate(claimable, start=1)}
    labelled_parts = {f"P{i}": u for i, u in enumerate(units, start=1)}
    labelled_evidence = {
        f"E{i}": cid for i, cid in enumerate(cited_ids, start=1) if cid in chunk_info
    }
    input_hash = content_hash(f"{tailoring_id}:{seq}")

    def record(calls: list[Any]) -> None:
        for call in calls:
            record_result(
                ctx.engine,
                ctx.settings,
                provider=provider.name,
                model=model,
                purpose="tailor_resume",
                result=call,
                input_hash=input_hash,
                prompt_version=PROMPT_VERSION,
                run_id=ctx.run_id,
                user_id=owner,
            )

    try:
        outcome = propose(
            provider,
            model=model,
            requirements=[
                RequirementShown(label, r.text, verdicts[r.id].verdict)
                for label, r in labelled_reqs.items()
            ],
            unsupported=unsupported,
            parts=[
                PartShown(label, u.label, u.kind, u.lines) for label, u in labelled_parts.items()
            ],
            evidence=[
                EvidenceShown(label, chunk_info[cid][0]) for label, cid in labelled_evidence.items()
            ],
        )
    except LLMError as exc:
        record_result(
            ctx.engine, ctx.settings, provider=provider.name, model=model, purpose="tailor_resume",
            result=None, input_hash=input_hash, prompt_version=PROMPT_VERSION, run_id=ctx.run_id,
            user_id=owner, error_class="LLM_RETRYABLE" if exc.retryable else "LLM_REJECTED",
        )  # fmt: skip
        _step(ctx, 2, "propose", StepState.FAILED, started)
        if exc.retryable:
            _transient(ctx, owner, tailoring_id, 0)
        else:
            _fail(ctx, owner, tailoring_id, TailoringErrorCode.AI_UNAVAILABLE)
        return
    record(outcome.calls)
    _step(ctx, 2, "propose", StepState.SUCCEEDED, started, model_calls=len(outcome.calls))

    started = time.perf_counter()
    words = job_vocabulary(r.text for r in requirements if r.category not in GATE_CATEGORIES)
    prepared: list[dict[str, Any]] = []
    seen_parts: set[str] = set()
    for answer in outcome.value.suggestions:
        unit = labelled_parts.get(answer.part)
        lines = clean_lines(answer.after)
        if unit is None or lines is None or answer.part in seen_parts or lines == list(unit.lines):
            continue
        if unit.kind == "paragraph" and len(lines) != 1:
            continue
        seen_parts.add(answer.part)
        cited = [
            labelled_evidence[e] for e in dict.fromkeys(answer.evidence) if e in labelled_evidence
        ]
        verification = verify_text(
            lines,
            before=unit.lines,
            evidence=[chunk_info[cid][0] for cid in cited],
            job_words=words,
        )
        prepared.append(
            {
                "unit_id": unit.unit_id,
                "target_id": unit.target_id,
                "kind": unit.kind,
                "label": unit.label[:120],
                "before_lines": list(unit.lines),
                "after_lines": lines,
                "reason": " ".join(answer.reason.split())[:400],
                "requirement_ids": [
                    str(labelled_reqs[r].id)
                    for r in dict.fromkeys(answer.requirements)
                    if r in labelled_reqs
                ],
                "citations": [
                    {
                        "chunk_id": str(cid),
                        "quote": chunk_info[cid][0][:QUOTE_CHARS],
                        "source": chunk_info[cid][1],
                        "entry_type": chunk_info[cid][2],
                    }
                    for cid in cited
                ],
                "claims": [
                    {"text": c.text, "kind": c.kind, "supported": c.supported, "source": c.source}
                    for c in verification.claims
                ],
                "blocked": verification.blocked,
            }
        )
    prepared = prepared[:MAX_SUGGESTIONS]

    with tenant_session(ctx.engine, owner) as db:
        row = get_tailoring_by_id(db, owner, tailoring_id)
        if row is None or row.seq != seq:
            return
        for ordinal, fields in enumerate(prepared):
            add_suggestion(db, row, ordinal, **fields)
        finish_tailoring(db, row, model_calls=len(outcome.calls), prompt_version=PROMPT_VERSION)
    _step(
        ctx, 3, "verify", StepState.SUCCEEDED, started,
        suggestions=len(prepared), blocked=sum(1 for p in prepared if p["blocked"]),
    )  # fmt: skip


__all__ = ["ResumeTailoring", "handle_tailor_resume", "run_tailor"]
