"""Write one kind of preparation for one job (interview questions, topics, or a message to send), and
check every claim in it.

The model writes (pv_llm.prepare). Code decides what is kept and what the person is told:

  - preparation is built only for a job whose evidence check is complete, from the evidence that check
    found for the requirements the person meets or partly meets. Every requirement is named to the
    model, with whether it is shown, so questions can be about a gap and guidance never claims one
  - kinds that are about the person (questions about their resume or projects, and the messages) need
    evidence and stop with a visible result when there is none. The others can be written about the
    job alone, and say so on every item that cites no evidence
  - each item's text and guidance is checked against the evidence it cited and the job's own words
    (pv_domain.tailoring.verify_text). The claims that are in neither are stored with the item. An
    item with no cited evidence is marked "not enough evidence". Nothing is hidden and nothing is sent
  - a message to send is checked as a draft is (pv_domain.drafts.verify_draft)

A task for an older request, or for a deleted output, does nothing. A missing key is a visible failure
at once. Provider trouble is retried with backoff and the last attempt becomes a visible failure. The
job and evidence text is never logged and never put in an error message.
"""

import time
import uuid
from collections.abc import Callable
from typing import Any

from sqlalchemy import select

from pv_domain.analysis import GATE_CATEGORIES, AnalysisStatus, Verdict
from pv_domain.drafts import JobHeading, clean_body, verify_draft
from pv_domain.preparation import (
    ACTIONS,
    INSUFFICIENT_EVIDENCE,
    MAX_MESSAGE_CHARS,
    MIN_MESSAGE_CHARS,
    NEEDS_EVIDENCE,
    TEXT_ACTIONS,
    PrepErrorCode,
)
from pv_domain.states import RunState, StepState
from pv_domain.tailoring import job_vocabulary, verify_text
from pv_llm import (
    LLMError,
    LLMProvider,
    StructuredOutputError,
    build_provider,
    content_hash,
    record_result,
)
from pv_llm.prepare import PROMPT_VERSION, EvidenceShown, RequirementShown, prepare_items
from pv_persistence.analysis import get_analysis, list_verdicts
from pv_persistence.evidence import list_chunks_by_type
from pv_persistence.jobs import get_posting
from pv_persistence.models import EvidenceChunk, JobRequirement
from pv_persistence.preparation import fail_output, finish_output, get_output_by_id, mark_working
from pv_persistence.runs import add_step, set_run_state
from pv_persistence.tenancy import tenant_session
from pv_persistence.workrows import fact_value
from pv_worker.contract import TaskContext, TaskFailure

ProviderFactory = Callable[[], LLMProvider]
MAX_EVIDENCE_SHOWN = 12
STORED_EVIDENCE_CHARS = 700
MAX_REQUIREMENTS_SHOWN = 20


def handle_prepare_job(ctx: TaskContext) -> None:
    run_prepare(ctx, provider_factory=lambda: build_provider(ctx.settings))


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
    ctx: TaskContext, owner: uuid.UUID, output_id: uuid.UUID, code: PrepErrorCode, calls: int = 0
) -> None:
    with tenant_session(ctx.engine, owner) as db:
        row = get_output_by_id(db, owner, output_id)
        if row is not None:
            fail_output(row, code.value, model_calls=calls)


def _transient(ctx: TaskContext, owner: uuid.UUID, output_id: uuid.UUID) -> None:
    if ctx.attempt >= ctx.max_attempts:
        _fail(ctx, owner, output_id, PrepErrorCode.AI_UNAVAILABLE)
        return
    if ctx.run_id is not None:
        with tenant_session(ctx.engine, owner) as db:
            set_run_state(db, ctx.run_id, RunState.RETRYING)
    raise TaskFailure("The writing service is busy. Trying again.", retryable=True)


def _claims(verification: Any) -> list[dict[str, Any]]:
    return [
        {"text": c.text, "kind": c.kind, "supported": c.supported, "source": c.source}
        for c in verification.claims
    ]


def run_prepare(ctx: TaskContext, *, provider_factory: ProviderFactory) -> None:
    owner = ctx.owner_user_id
    if owner is None:
        raise TaskFailure("The preparation task has no owner.", retryable=False)
    try:
        output_id = uuid.UUID(str(ctx.args.get("output_id")))
    except ValueError as exc:
        raise TaskFailure("Invalid preparation task arguments.", retryable=False) from exc
    seq: Any = ctx.args.get("seq")

    started = time.perf_counter()
    with tenant_session(ctx.engine, owner) as db:
        row = get_output_by_id(db, owner, output_id)
        if row is None or row.seq != seq or row.action not in ACTIONS:
            return  # deleted, or asked for again since this task was queued
        mark_working(row)
        if ctx.run_id is not None:
            set_run_state(db, ctx.run_id, RunState.RUNNING)
        action, posting_id = row.action, row.posting_id
        posting = get_posting(db, owner, posting_id)
        analysis = get_analysis(db, owner, posting_id) if posting else None
        complete = analysis is not None and analysis.status == AnalysisStatus.COMPLETE
        requirements = (
            list(
                db.execute(
                    select(JobRequirement)
                    .where(
                        JobRequirement.owner_user_id == owner,
                        JobRequirement.posting_id == posting_id,
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
        )
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
        if action == "project_questions":
            seen = {item[0] for item in evidence}
            for chunk in list_chunks_by_type(db, owner, "project", MAX_EVIDENCE_SHOWN):
                if chunk.id not in seen:
                    evidence.append((chunk.id, chunk.text, "profile"))
        evidence = evidence[:MAX_EVIDENCE_SHOWN]
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
        _fail(ctx, owner, output_id, PrepErrorCode.ANALYSIS_NEEDED)
        return

    shown = [r for r in requirements if r.category not in GATE_CATEGORIES][:MAX_REQUIREMENTS_SHOWN]
    labelled_req = {f"R{i}": r for i, r in enumerate(shown, start=1)}
    labelled_evidence = {f"E{i}": item for i, item in enumerate(evidence, start=1)}

    def status_of(requirement: JobRequirement) -> str:
        verdict = verdicts[requirement.id].verdict if requirement.id in verdicts else None
        return (
            "met"
            if verdict == Verdict.MET
            else "partial"
            if verdict == Verdict.PARTIAL
            else "not shown"
        )

    _step(
        ctx, 1, "load", StepState.SUCCEEDED, started,
        requirements=len(shown), evidence=len(evidence),
    )  # fmt: skip
    ctx.extend_lease()
    if action in NEEDS_EVIDENCE and not evidence:
        _fail(ctx, owner, output_id, PrepErrorCode.NO_EVIDENCE)
        return

    started = time.perf_counter()
    try:
        provider = provider_factory()
    except LLMError:
        _step(ctx, 2, "write", StepState.FAILED, started)
        _fail(ctx, owner, output_id, PrepErrorCode.AI_NOT_CONFIGURED)
        return
    model = ctx.settings.llm_model
    input_hash = content_hash(f"{output_id}:{seq}")

    def record(calls: list[Any], error_class: str | None = None) -> None:
        for call in calls or [None]:
            record_result(
                ctx.engine,
                ctx.settings,
                provider=provider.name,
                model=model,
                purpose="prepare_job",
                result=call,
                input_hash=input_hash,
                prompt_version=PROMPT_VERSION,
                run_id=ctx.run_id,
                user_id=owner,
                error_class=error_class,
            )

    try:
        outcome = prepare_items(
            provider,
            model=model,
            action=action,
            heading=" | ".join(heading.texts()) or "(no heading)",
            requirements=[
                RequirementShown(label, r.text, status_of(r)) for label, r in labelled_req.items()
            ],
            evidence=[EvidenceShown(label, item[1]) for label, item in labelled_evidence.items()],
        )
    except StructuredOutputError as exc:
        record(exc.calls)
        _step(ctx, 2, "write", StepState.FAILED, started)
        _fail(ctx, owner, output_id, PrepErrorCode.AI_BAD_OUTPUT, len(exc.calls))
        return
    except LLMError as exc:
        record([], "LLM_RETRYABLE" if exc.retryable else "LLM_REJECTED")
        _step(ctx, 2, "write", StepState.FAILED, started)
        if exc.retryable:
            _transient(ctx, owner, output_id)
        else:
            _fail(ctx, owner, output_id, PrepErrorCode.AI_UNAVAILABLE)
        return
    record(outcome.calls)
    _step(ctx, 2, "write", StepState.SUCCEEDED, started, model_calls=len(outcome.calls))

    started = time.perf_counter()
    job_words = job_vocabulary(r.text for r in requirements if r.category not in GATE_CATEGORIES)
    stored_evidence: list[dict[str, Any]] = [
        {
            "chunk_id": str(item[0]),
            "text": item[1][:STORED_EVIDENCE_CHARS],
            "source": item[2],
        }
        for item in labelled_evidence.values()
    ]
    items: list[dict[str, Any]] = []
    body = ""
    all_claims: list[dict[str, Any]] = []
    if action in TEXT_ACTIONS:
        first = outcome.value.items[0]
        body = clean_body(first.text)
        if not MIN_MESSAGE_CHARS <= len(body) <= MAX_MESSAGE_CHARS:
            _fail(ctx, owner, output_id, PrepErrorCode.AI_BAD_OUTPUT, len(outcome.calls))
            return
        cited = [e for e in first.evidence if e in labelled_evidence]
        verification = verify_draft(
            body, evidence=[item[1] for item in evidence], heading=heading, job_words=job_words
        )
        all_claims = _claims(verification)
        stored_evidence = [
            {**e, "cited": label in cited}
            for e, label in zip(stored_evidence, labelled_evidence, strict=True)
        ]
    else:
        for item in outcome.value.items:
            cited_labels = [e for e in item.evidence if e in labelled_evidence]
            cited_texts = [labelled_evidence[e][1] for e in cited_labels]
            requirement = labelled_req.get(item.requirement)
            verification = verify_text(
                [clean_body(item.text), clean_body(item.guidance)],
                before=[*heading.texts(), requirement.text if requirement else ""],
                evidence=cited_texts,
                job_words=job_words,
            )
            claims = _claims(verification)
            items.append(
                {
                    "text": clean_body(item.text),
                    "guidance": clean_body(item.guidance),
                    "category": " ".join(item.category.split())[:60],
                    "difficulty": item.difficulty
                    if item.difficulty in ("easy", "medium", "hard", "expert")
                    else "",
                    "requirement_id": str(requirement.id) if requirement else None,
                    "evidence": [str(labelled_evidence[e][0]) for e in cited_labels],
                    "insufficient_evidence": not cited_labels,
                    "note": INSUFFICIENT_EVIDENCE if not cited_labels else "",
                    "claims": claims,
                }
            )
    with tenant_session(ctx.engine, owner) as db:
        row = get_output_by_id(db, owner, output_id)
        if row is None or row.seq != seq:
            return
        finish_output(
            row,
            items=items,
            body=body,
            evidence=stored_evidence,
            claims=all_claims,
            prompt_version=PROMPT_VERSION,
            model_calls=len(outcome.calls),
        )
    unsupported = sum(1 for c in all_claims if not c["supported"]) + sum(
        1 for i in items for c in i["claims"] if not c["supported"]
    )
    _step(
        ctx, 3, "verify", StepState.SUCCEEDED, started,
        items=len(items) or 1, unsupported=unsupported,
    )  # fmt: skip
