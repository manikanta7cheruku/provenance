"""Career preparation for one job: what to prepare and why, the plan, generated practice material, a
mock interview, and a message to send.

Everything runs in one tenant session (Row Level Security) and filters by the signed-in person. The
rules (priority, difficulty, what applies, the plan, the feedback) are in pv_domain.preparation and
are pure code. A model is asked only for wording, in a worker task (pv_worker.handlers.prepare_job),
and every claim in what it writes is checked against the person's evidence.

What this never does: send anything, invent how an interview works, claim a question will be asked,
or treat missing evidence as proof the person cannot do something.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from pv_api.errors import ApiError
from pv_api.schemas import (
    MockOut,
    MockRubricOut,
    MockTurnOut,
    PrepActionOut,
    PreparationOut,
    PrepClaimOut,
    PrepCompanyOut,
    PrepConceptOut,
    PrepCoverageOut,
    PrepEvidenceOut,
    PrepItemOut,
    PrepPlanDayOut,
    PrepProgressOut,
)
from pv_api.services import entitlement_service, job_service
from pv_config import Settings
from pv_domain.analysis import GATE_CATEGORIES, AnalysisStatus, Verdict
from pv_domain.drafts import JobHeading, clean_body, verify_draft
from pv_domain.entitlements import UNIT_MATERIAL
from pv_domain.failures import FailureClass
from pv_domain.preparation import (
    ACTIONS,
    GENERATED_LABEL,
    LIKELY_LABEL,
    MAX_MESSAGE_CHARS,
    MIN_ANSWER_CHARS,
    MIN_MESSAGE_CHARS,
    PREP_ERROR_MESSAGES,
    PRIORITY_LABELS,
    RULES_VERSION,
    TEXT_ACTIONS,
    Concept,
    Priority,
    ReqRow,
    applicable_actions,
    build_concepts,
    clean_answer,
    coverage,
    make_plan,
    mock_questions,
    progress,
    role_family,
    score_answer,
    seniority_years,
)
from pv_domain.tailoring import job_vocabulary
from pv_persistence.analysis import get_analysis, list_verdicts
from pv_persistence.audit import record_audit
from pv_persistence.evidence import list_chunks_by_type
from pv_persistence.jobs import get_posting
from pv_persistence.models import (
    EvidenceChunk,
    JobPosting,
    JobPreparation,
    JobRequirement,
    MockInterview,
    PrepOutput,
)
from pv_persistence.preparation import (
    QUEUED,
    WORKING,
    add_turn,
    done_keys,
    finish_mock,
    get_mock,
    get_output,
    get_prep,
    latest_mock,
    list_outputs,
    save_output_edit,
    set_company,
    set_done,
    set_interview_date,
    start_mock,
    start_output,
)
from pv_persistence.tenancy import tenant_session
from pv_persistence.workrows import fact_value

CLAIM_TEXT_ACTIONS = TEXT_ACTIONS


def _conflict(code: str, message: str) -> ApiError:
    return ApiError(409, code, message, failure_class=FailureClass.USER_ACTION_REQUIRED)


def _posting(db: Session, user_id: uuid.UUID, job_id: uuid.UUID) -> JobPosting:
    posting = get_posting(db, user_id, job_id)
    if posting is None:
        raise job_service.not_found()
    return posting


def _concept_key(requirement_id: str) -> str:
    return f"concept:{requirement_id}"


def _item_key(action: str, index: int) -> str:
    return f"item:{action}:{index}"


class _Context:
    """What preparation reads for one job, loaded once."""

    def __init__(self, db: Session, user_id: uuid.UUID, posting: JobPosting) -> None:
        self.posting = posting
        analysis = get_analysis(db, user_id, posting.id)
        self.complete = analysis is not None and analysis.status == AnalysisStatus.COMPLETE
        requirements = list(
            db.execute(
                select(JobRequirement)
                .where(
                    JobRequirement.owner_user_id == user_id, JobRequirement.posting_id == posting.id
                )
                .order_by(JobRequirement.ordinal)
            ).scalars()
        )
        self.requirements = requirements
        verdicts = (
            {v.requirement_id: v for v in list_verdicts(db, user_id, analysis.id)}
            if analysis and self.complete
            else {}
        )
        self.rows = [
            ReqRow(
                requirement_id=str(r.id),
                ordinal=r.ordinal,
                text=r.text,
                kind=r.kind,
                category=r.category,
                years_min=r.years_min,
                verdict=verdicts[r.id].verdict if r.id in verdicts else "unchecked",
            )
            for r in requirements
        ]
        cited = sorted(
            {
                uuid.UUID(c["chunk_id"])
                for v in verdicts.values()
                if v.verdict in (Verdict.MET, Verdict.PARTIAL)
                for c in v.citations
            }
        )
        self.evidence_texts = [
            c.text
            for c in db.execute(
                select(EvidenceChunk).where(
                    EvidenceChunk.owner_user_id == user_id, EvidenceChunk.id.in_(cited)
                )
            ).scalars()
        ][:12]
        self.has_projects = bool(list_chunks_by_type(db, user_id, "project", 1))
        years_fact = fact_value(posting, "min_years_experience")
        self.years = seniority_years(
            self.rows, int(years_fact) if years_fact and years_fact.isdigit() else None
        )
        self.family = role_family(
            posting.title or "", [r.text for r in requirements if r.category not in GATE_CATEGORIES]
        )
        self.concepts = build_concepts(self.rows, self.years)
        self.heading = JobHeading(
            title=posting.title or "",
            company=posting.company or "",
            location=fact_value(posting, "location") or "",
        )
        self.job_words = job_vocabulary(
            r.text for r in requirements if r.category not in GATE_CATEGORIES
        )


def _claims(raw: Any) -> list[PrepClaimOut]:
    return [
        PrepClaimOut(
            text=str(c.get("text", "")),
            kind=str(c.get("kind", "")),
            supported=bool(c.get("supported")),
            source=c.get("source"),
        )
        for c in (raw or [])
    ]


def _item_out(action: str, index: int, raw: dict[str, Any], done: set[str]) -> PrepItemOut:
    claims = _claims(raw.get("claims"))
    return PrepItemOut(
        key=_item_key(action, index),
        text=str(raw.get("text", "")),
        guidance=str(raw.get("guidance", "")),
        category=str(raw.get("category", "")),
        difficulty=str(raw.get("difficulty", "")),
        requirement_id=raw.get("requirement_id"),
        evidence_count=len(raw.get("evidence") or []),
        insufficient_evidence=bool(raw.get("insufficient_evidence")),
        note=str(raw.get("note", "")),
        claims=claims,
        unsupported_count=sum(1 for c in claims if not c.supported),
        done=_item_key(action, index) in done,
    )


def _action_out(key: str, row: PrepOutput | None, done: set[str]) -> PrepActionOut:
    spec = ACTIONS[key]
    error = None
    if row is not None and row.status == "failed" and row.error_code:
        error = PREP_ERROR_MESSAGES.get(row.error_code, PREP_ERROR_MESSAGES["ai_unavailable"])
    ready = row is not None and row.status == "ready"
    return PrepActionOut(
        key=key,
        label=spec.label,
        description=spec.description,
        shape=spec.shape,
        status=row.status if row else None,
        error=error,
        origin=row.origin if row else None,
        items=[_item_out(key, i, raw, done) for i, raw in enumerate(row.items)]
        if ready and row
        else [],
        body=row.body if ready and row else "",
        word_count=len(row.body.split()) if ready and row else 0,
        claims=_claims(row.claims) if ready and row else [],
        evidence=[
            PrepEvidenceOut(
                text=str(e.get("text", "")),
                source=str(e.get("source", "")),
                cited=bool(e.get("cited")),
            )
            for e in (row.evidence if ready and row else [])
        ],
        updated_at=row.updated_at if row else None,
    )


def _mock_out(row: MockInterview | None) -> MockOut | None:
    if row is None:
        return None
    turns = [
        MockTurnOut(
            question=str(t.get("question", "")),
            answer=str(t.get("answer", "")),
            rubric=[MockRubricOut(**r) for r in t.get("rubric", [])],
            total=int(t.get("total", 0)),
            maximum=int(t.get("maximum", 0)),
            unsupported_claims=list(t.get("unsupported_claims", [])),
            follow_up=str(t.get("follow_up", "")),
            words=int(t.get("words", 0)),
        )
        for t in row.turns
    ]
    index = len(row.turns)
    current = (
        str(row.questions[index]["text"])
        if row.state == "active" and index < len(row.questions)
        else None
    )
    return MockOut(
        id=row.id,
        state=row.state,
        question_count=len(row.questions),
        turns=turns,
        current_question=current,
        current_index=index,
    )


def _company(posting: JobPosting, prep: JobPreparation | None) -> PrepCompanyOut:
    says: list[str] = []
    for label, key in (
        ("Place", "location"),
        ("Work arrangement", "work_mode"),
        ("Employment type", "employment_type"),
    ):
        value = fact_value(posting, key)
        if value:
            says.append(f"{label}: {value}")
    return PrepCompanyOut(
        name=posting.company or "",
        location=fact_value(posting, "location") or "",
        source_name=posting.source_name,
        source_url=posting.source_url,
        link=prep.company_link if prep else "",
        notes=prep.company_notes if prep else "",
        says=says,
    )


def _view(db: Session, user_id: uuid.UUID, posting: JobPosting) -> PreparationOut:
    ctx = _Context(db, user_id, posting)
    prep = get_prep(db, user_id, posting.id)
    outputs = {o.action: o for o in list_outputs(db, user_id, posting.id)}
    done = done_keys(db, user_id, posting.id)
    keys = applicable_actions(
        family=ctx.family,
        years=ctx.years,
        title=posting.title or "",
        has_projects=ctx.has_projects,
        has_evidence=bool(ctx.evidence_texts),
    )
    concept_keys = [
        _concept_key(c.requirement_id) for c in ctx.concepts if c.priority is not Priority.OPTIONAL
    ]
    item_keys = [
        _item_key(k, i)
        for k in keys
        if k in outputs and outputs[k].status == "ready"
        for i in range(len(outputs[k].items))
    ]
    plan = make_plan(datetime.now(UTC).date(), prep.interview_date if prep else None, ctx.concepts)
    return PreparationOut(
        job_id=posting.id,
        title=posting.title or "",
        company=posting.company or "",
        can_prepare=ctx.complete,
        blocker=None if ctx.complete else PREP_ERROR_MESSAGES["analysis_needed"],
        family=ctx.family,
        years=ctx.years,
        rules_version=RULES_VERSION,
        coverage=PrepCoverageOut(**coverage(ctx.rows)),
        concepts=[_concept_out(c, done) for c in ctx.concepts],
        actions=[_action_out(k, outputs.get(k), done) for k in keys],
        interview_date=prep.interview_date if prep else None,
        plan=[PrepPlanDayOut(date=d.day, kind=d.kind, topics=list(d.topics)) for d in plan],
        company_info=_company(posting, prep),
        progress=PrepProgressOut(**progress(done, [*concept_keys, *item_keys])),
        mock=_mock_out(latest_mock(db, user_id, posting.id)),
        likely_label=LIKELY_LABEL,
        generated_label=GENERATED_LABEL,
    )


def _concept_out(c: Concept, done: set[str]) -> PrepConceptOut:
    return PrepConceptOut(
        key=_concept_key(c.requirement_id),
        requirement_id=c.requirement_id,
        text=c.text,
        kind=c.kind,
        category=c.category,
        verdict=c.verdict,
        priority=c.priority.value,
        priority_label=PRIORITY_LABELS[c.priority],
        difficulty=c.difficulty,
        why=c.why,
        done=_concept_key(c.requirement_id) in done,
    )


def view(engine: Engine, user_id: uuid.UUID, job_id: uuid.UUID) -> PreparationOut:
    with tenant_session(engine, user_id) as db:
        return _view(db, user_id, _posting(db, user_id, job_id))


# ---------------------------------------------------------------- generated material


def start_action(
    engine: Engine,
    user_id: uuid.UUID,
    job_id: uuid.UUID,
    action: str,
    replace: bool,
    ip_hash: str | None,
    *,
    settings: Settings,
) -> PreparationOut:
    if action not in ACTIONS:
        raise job_service.not_found()
    with tenant_session(engine, user_id) as db:
        posting = _posting(db, user_id, job_id)
        ctx = _Context(db, user_id, posting)
        if not ctx.complete:
            raise _conflict("ANALYSIS_NEEDED", PREP_ERROR_MESSAGES["analysis_needed"])
        existing = get_output(db, user_id, job_id, action)
        if existing is not None:
            if existing.status in (QUEUED, WORKING):
                raise _conflict("PREPARATION_IN_PROGRESS", "This is already being written.")
            if existing.origin == "edited" and not replace:
                raise _conflict(
                    "EDITED_TEXT",
                    "You edited this text. Writing it again replaces your edits. Confirm to go ahead.",
                )
        entitlement_service.charge(
            db, settings, user_id, UNIT_MATERIAL, f"material:{uuid.uuid4().hex}"
        )
        start_output(db, owner_id=user_id, posting_id=job_id, action=action)
        out = _view(db, user_id, posting)
    record_audit(
        engine, category="audit", action="career_preparation.started", actor_user_id=user_id,
        target_type="job_posting", target_id=str(job_id), ip_hash=ip_hash,
        metadata={"action": action},
    )  # fmt: skip
    return out


def edit_text(
    engine: Engine, user_id: uuid.UUID, job_id: uuid.UUID, action: str, text: str
) -> PreparationOut:
    if action not in CLAIM_TEXT_ACTIONS:
        raise job_service.not_found()
    body = clean_body(text)
    if not MIN_MESSAGE_CHARS <= len(body) <= MAX_MESSAGE_CHARS:
        raise ApiError(
            422, "VALIDATION_FAILED", "Some details need fixing.",
            failure_class=FailureClass.VALIDATION_FAILED,
            fields={"text": f"Write between {MIN_MESSAGE_CHARS} and {MAX_MESSAGE_CHARS} characters."},
        )  # fmt: skip
    with tenant_session(engine, user_id) as db:
        posting = _posting(db, user_id, job_id)
        row = get_output(db, user_id, job_id, action)
        if row is None or row.status != "ready":
            raise job_service.not_found()
        ctx = _Context(db, user_id, posting)
        verification = verify_draft(
            body,
            evidence=[str(e.get("text", "")) for e in row.evidence],
            heading=ctx.heading,
            job_words=ctx.job_words,
        )
        save_output_edit(
            row,
            body=body,
            claims=[
                {"text": c.text, "kind": c.kind, "supported": c.supported, "source": c.source}
                for c in verification.claims
            ],
        )
        return _view(db, user_id, posting)


# ---------------------------------------------------------------- the date, the company, progress


def set_date(engine: Engine, user_id: uuid.UUID, job_id: uuid.UUID, when: Any) -> PreparationOut:
    with tenant_session(engine, user_id) as db:
        posting = _posting(db, user_id, job_id)
        if when is not None and when < datetime.now(UTC).date():
            raise ApiError(
                422, "VALIDATION_FAILED", "Some details need fixing.",
                failure_class=FailureClass.VALIDATION_FAILED,
                fields={"interview_date": "Choose today or a day after it."},
            )  # fmt: skip
        set_interview_date(db, user_id, job_id, when)
        return _view(db, user_id, posting)


def set_company_notes(
    engine: Engine, user_id: uuid.UUID, job_id: uuid.UUID, link: str, notes: str
) -> PreparationOut:
    link = link.strip()
    if link and not (link.startswith("https://") or link.startswith("http://")):
        raise ApiError(
            422, "VALIDATION_FAILED", "Some details need fixing.",
            failure_class=FailureClass.VALIDATION_FAILED,
            fields={"link": "Use an address that starts with https://. It is kept for you to open. It is never fetched."},
        )  # fmt: skip
    with tenant_session(engine, user_id) as db:
        posting = _posting(db, user_id, job_id)
        set_company(
            db,
            user_id,
            job_id,
            link,
            "".join(ch for ch in notes if ch >= " " or ch in "\n\t").strip(),
        )
        return _view(db, user_id, posting)


def set_progress(
    engine: Engine, user_id: uuid.UUID, job_id: uuid.UUID, key: str, done: bool
) -> PreparationOut:
    if not (key.startswith("concept:") or key.startswith("item:")):
        raise ApiError(
            422, "VALIDATION_FAILED", "Some details need fixing.",
            failure_class=FailureClass.VALIDATION_FAILED,
            fields={"key": "That is not something that can be ticked."},
        )  # fmt: skip
    with tenant_session(engine, user_id) as db:
        posting = _posting(db, user_id, job_id)
        set_done(db, user_id, job_id, key, done)
        return _view(db, user_id, posting)


# ---------------------------------------------------------------- the mock interview


def mock_begin(engine: Engine, user_id: uuid.UUID, job_id: uuid.UUID) -> PreparationOut:
    with tenant_session(engine, user_id) as db:
        posting = _posting(db, user_id, job_id)
        ctx = _Context(db, user_id, posting)
        if not ctx.complete:
            raise _conflict("ANALYSIS_NEEDED", PREP_ERROR_MESSAGES["analysis_needed"])
        questions = [
            {"requirement_id": q.requirement_id, "text": q.text, "priority": q.priority.value}
            for q in mock_questions(ctx.concepts)
        ]
        start_mock(db, user_id, job_id, questions)
        return _view(db, user_id, posting)


def mock_answer(
    engine: Engine, user_id: uuid.UUID, job_id: uuid.UUID, mock_id: uuid.UUID, answer: str
) -> PreparationOut:
    text = clean_answer(answer)
    if len(text) < MIN_ANSWER_CHARS:
        raise ApiError(
            422, "VALIDATION_FAILED", "Some details need fixing.",
            failure_class=FailureClass.VALIDATION_FAILED,
            fields={"answer": "Write your answer in a few sentences, as you would say it."},
        )  # fmt: skip
    with tenant_session(engine, user_id) as db:
        posting = _posting(db, user_id, job_id)
        row = get_mock(db, user_id, mock_id)
        if row is None or row.posting_id != job_id:
            raise job_service.not_found()
        if row.state != "active":
            raise _conflict(
                "MOCK_FINISHED", "This practice interview is finished. Start a new one."
            )
        index = len(row.turns)
        question = row.questions[index]
        ctx = _Context(db, user_id, posting)
        requirement = next(
            (r for r in ctx.rows if r.requirement_id == question.get("requirement_id")), None
        )
        following = row.questions[index + 1]["text"] if index + 1 < len(row.questions) else None
        next_topic = _topic_of(following) if following else None
        feedback = score_answer(
            text,
            requirement_text=requirement.text if requirement else question["text"],
            evidence_texts=ctx.evidence_texts,
            job_words=ctx.job_words,
            next_topic=next_topic,
        )
        add_turn(
            row,
            {
                "question": question["text"],
                "answer": text,
                "rubric": [
                    {"name": r.name, "score": r.score, "note": r.note} for r in feedback.rubric
                ],
                "total": feedback.total,
                "maximum": feedback.maximum,
                "unsupported_claims": list(feedback.unsupported_claims),
                "follow_up": feedback.follow_up,
                "words": feedback.words,
            },
        )
        return _view(db, user_id, posting)


def _topic_of(question_text: str) -> str:
    start = question_text.find('"')
    end = question_text.find('"', start + 1)
    return question_text[start + 1 : end] if start >= 0 and end > start else question_text[:80]


def mock_end(
    engine: Engine, user_id: uuid.UUID, job_id: uuid.UUID, mock_id: uuid.UUID
) -> PreparationOut:
    with tenant_session(engine, user_id) as db:
        posting = _posting(db, user_id, job_id)
        row = get_mock(db, user_id, mock_id)
        if row is None or row.posting_id != job_id:
            raise job_service.not_found()
        finish_mock(row)
        return _view(db, user_id, posting)
