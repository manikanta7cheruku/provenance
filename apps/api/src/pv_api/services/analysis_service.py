"""The evidence check of a pasted job: start it, show it, answer the agent, give feedback.

Same rules as the job service: one tenant session per call (Row Level Security), every query
filtered by the signed-in owner, and "not found" for anything that belongs to someone else.

What is shown is computed when it is read. The band comes from the stored verdicts and the
person's CURRENT eligibility, so changing a preference changes it at once and nothing stale is
stored. The score is only produced when every requirement has a verdict: there is no partial score.
"""

import uuid

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from pv_api.errors import ApiError
from pv_api.schemas import (
    AnalysisOut,
    AnswerIn,
    CitationOut,
    FeedbackIn,
    GapOut,
    GateRequirementOut,
    QuestionOut,
    ScoreOut,
    VerdictOut,
)
from pv_api.services.job_service import _eligibility, not_found
from pv_domain.analysis import (
    ANALYSIS_ERROR_MESSAGES,
    GATE_CATEGORIES,
    MAX_ANSWER_CHARS,
    REASON_MESSAGES,
    SCORING_VERSION,
    AnalysisStatus,
    AnalysisUiState,
    QuestionStatus,
    Verdict,
    analysis_ui_state,
    confidence_for,
    gap_plan,
    score_analysis,
)
from pv_domain.eligibility import EligibilityResult, EligibilityState
from pv_domain.failures import FailureClass
from pv_domain.job import JobParseStatus
from pv_persistence.analysis import (
    answer_question,
    chunk_state,
    evidence_chunk_count,
    get_analysis,
    get_feedback,
    get_question,
    list_questions,
    list_verdicts,
    save_feedback,
    skip_question,
    start_analysis,
)
from pv_persistence.audit import record_audit
from pv_persistence.jobs import get_posting, list_requirements
from pv_persistence.models import (
    AgentQuestion,
    JobAnalysis,
    JobPosting,
    JobRequirement,
    RequirementVerdict,
)
from pv_persistence.tenancy import tenant_session


def _conflict(code: str, message: str) -> ApiError:
    return ApiError(409, code, message, failure_class=FailureClass.USER_ACTION_REQUIRED)


def _eligibility_note(result: EligibilityResult | None) -> tuple[bool, str]:
    """Whether the person may be scored, and one plain sentence about eligibility."""
    if result is None:
        return True, "Eligibility has not been checked."
    if result.state == EligibilityState.NOT_ELIGIBLE:
        return False, f"Eligibility: {result.gates[0].reason}"
    if result.state == EligibilityState.ELIGIBLE:
        return True, "Eligibility: nothing in the way."
    if result.state == EligibilityState.REQUIRES_USER_INPUT:
        return True, "Eligibility: it needs an answer from you. See the checks above."
    return True, "Eligibility: some points are worth a closer look. See the checks above."


def _start_blocker(
    db: Session,
    posting: JobPosting,
    analysis: JobAnalysis | None,
    requirements: list[JobRequirement],
    result: EligibilityResult | None,
) -> tuple[str, str] | None:
    """(code, sentence) when the check cannot start now."""
    if posting.parse_status != JobParseStatus.EXTRACTED:
        return "JOB_NOT_READY", "The job has to be read first."
    if result is not None and result.state == EligibilityState.NOT_ELIGIBLE:
        return (
            "NOT_ELIGIBLE",
            "A hard requirement is not met, so there is nothing to score. See the checks above.",
        )
    if not any(r.category not in GATE_CATEGORIES for r in requirements):
        return "NOTHING_TO_CHECK", "Every requirement here is decided by the eligibility checks."
    if evidence_chunk_count(db, posting.owner_user_id) == 0:
        return (
            "NO_EVIDENCE",
            "Add your resume or a profile entry first, so there is something to check against.",
        )
    if analysis is not None:
        if analysis.status in (AnalysisStatus.QUEUED, AnalysisStatus.ANALYZING):
            return "ANALYSIS_IN_PROGRESS", "The check is already running."
        if analysis.status == AnalysisStatus.NEEDS_USER_INPUT:
            return "NEEDS_ANSWER", "Answer or skip the questions first."
    return None


def _citations(verdict: RequirementVerdict, current: dict[uuid.UUID, str]) -> list[CitationOut]:
    out: list[CitationOut] = []
    for c in verdict.citations:
        cid = uuid.UUID(c["chunk_id"])
        out.append(
            CitationOut(
                chunk_id=cid,
                quote=c["quote"],
                source="answer" if c.get("source_type") == "user_answer" else "profile",
                entry_type=c.get("entry_type"),
                changed=current.get(cid) != c.get("content_hash"),
            )
        )
    return out


def _verdict_out(
    r: JobRequirement,
    v: RequirementVerdict | None,
    current: dict[uuid.UUID, str],
    feedback: dict[uuid.UUID | None, str],
) -> VerdictOut:
    citations = _citations(v, current) if v is not None else []
    reason = ""
    if v is not None:
        reason = v.reason if citations else REASON_MESSAGES.get(v.reason_code or "", "")
    return VerdictOut(
        requirement_id=r.id,
        requirement=r.text,
        kind=r.kind,  # type: ignore[arg-type]
        category=r.category,
        posting_quote=r.quote,
        verdict=v.verdict if v else None,  # type: ignore[arg-type]
        evidence_kind=v.evidence_kind if v else None,  # type: ignore[arg-type]
        confidence=(confidence_for(v.verdict, v.evidence_kind).value if v else None),
        citations=citations,
        reason=reason,
        capped=bool(v.capped) if v else False,
        feedback=feedback.get(r.id),  # type: ignore[arg-type]
    )


def _score_and_gaps(
    verdicts: list[VerdictOut], result: EligibilityResult | None
) -> tuple[ScoreOut, list[GapOut]]:
    eligible, note = _eligibility_note(result)
    items = [(v.kind, v.verdict or Verdict.NOT_VERIFIED.value) for v in verdicts]
    scored = score_analysis(items, eligible=eligible, eligibility_note=note)
    score = ScoreOut(
        scoring_version=scored.scoring_version,
        band=scored.band.value,
        required_total=scored.required_total,
        met=scored.met,
        partial=scored.partial,
        conflicting=scored.conflicting,
        not_verified=scored.not_verified,
        preferred_total=scored.preferred_total,
        preferred_supported=scored.preferred_supported,
        reasons=list(scored.reasons),
    )
    plan = gap_plan(
        [
            (str(v.requirement_id), v.requirement, v.kind, v.category, v.verdict or "")
            for v in verdicts
        ]
    )
    gaps = [
        GapOut(
            requirement_id=uuid.UUID(g.requirement_id),
            requirement=g.requirement,
            state=g.state,
            proof_needed=g.proof_needed,
            next_step=g.next_step,
        )
        for g in plan
    ]
    return score, gaps


def _view(db: Session, posting: JobPosting) -> AnalysisOut:
    owner = posting.owner_user_id
    requirements = list_requirements(db, owner, posting.id)
    result = _eligibility(db, posting)
    analysis = get_analysis(db, owner, posting.id)
    blocker = _start_blocker(db, posting, analysis, requirements, result)

    checked_reqs = [r for r in requirements if r.category not in GATE_CATEGORIES]
    gate_reqs = [r for r in requirements if r.category in GATE_CATEGORIES]
    by_req = {r.id: r for r in requirements}
    verdicts: dict[uuid.UUID, RequirementVerdict] = {}
    questions: list[QuestionOut] = []
    if analysis is not None:
        verdicts = {v.requirement_id: v for v in list_verdicts(db, owner, analysis.id)}
        questions = [
            QuestionOut(
                id=q.id,
                requirement_id=q.requirement_id,
                requirement=by_req[q.requirement_id].text if q.requirement_id in by_req else "",
                question=q.question,
                status=q.status,  # type: ignore[arg-type]
                answer=q.answer,
            )
            for q in list_questions(db, owner, analysis.id)
        ]

    feedback: dict[uuid.UUID | None, str] = {
        f.requirement_id: f.answer for f in get_feedback(db, owner, posting.id)
    }
    cited = [uuid.UUID(c["chunk_id"]) for v in verdicts.values() for c in v.citations]
    current = chunk_state(db, owner, cited)

    ordered = sorted(checked_reqs, key=lambda x: (x.kind != "required", x.ordinal))
    verdict_out = [_verdict_out(r, verdicts.get(r.id), current, feedback) for r in ordered]
    stale = any(c.changed for v in verdict_out for c in v.citations)

    ui = analysis_ui_state(analysis.status if analysis else None)
    score: ScoreOut | None = None
    gaps: list[GapOut] = []
    if ui == AnalysisUiState.READY:
        score, gaps = _score_and_gaps(verdict_out, result)

    error = None
    if analysis is not None and ui == AnalysisUiState.FAILED:
        error = ANALYSIS_ERROR_MESSAGES.get(analysis.error_code or "")
    return AnalysisOut(
        ui_state=ui.value,
        can_start=blocker is None,
        blocker=blocker[1] if blocker else None,
        error_message=error,
        checked=sum(1 for v in verdict_out if v.verdict is not None),
        total=len(verdict_out),
        score=score,
        verdicts=verdict_out,
        gate_requirements=[
            GateRequirementOut(
                requirement_id=r.id,
                requirement=r.text,
                kind=r.kind,  # type: ignore[arg-type]
            )
            for r in gate_reqs
        ],
        questions=questions,
        gaps=gaps,
        stale=stale,
        recommendation_feedback=feedback.get(None),  # type: ignore[arg-type]
        scoring_version=SCORING_VERSION,
        prompt_version=analysis.prompt_version if analysis else None,
    )


def get_view(engine: Engine, user_id: uuid.UUID, job_id: uuid.UUID) -> AnalysisOut:
    with tenant_session(engine, user_id) as db:
        posting = get_posting(db, user_id, job_id)
        if posting is None:
            raise not_found()
        return _view(db, posting)


def start(
    engine: Engine, user_id: uuid.UUID, job_id: uuid.UUID, ip_hash: str | None
) -> AnalysisOut:
    with tenant_session(engine, user_id) as db:
        posting = get_posting(db, user_id, job_id)
        if posting is None:
            raise not_found()
        analysis = get_analysis(db, user_id, job_id)
        blocker = _start_blocker(
            db, posting, analysis, list_requirements(db, user_id, job_id), _eligibility(db, posting)
        )
        if blocker is not None:
            raise _conflict(*blocker)
        start_analysis(db, posting, analysis)
        out = _view(db, posting)
    record_audit(
        engine, category="audit", action="job.analysis_started", actor_user_id=user_id,
        target_type="job_posting", target_id=str(job_id), ip_hash=ip_hash,
    )  # fmt: skip
    return out


def _pending_question(
    db: Session, user_id: uuid.UUID, job_id: uuid.UUID, question_id: uuid.UUID
) -> tuple[JobPosting, JobAnalysis, AgentQuestion]:
    posting = get_posting(db, user_id, job_id)
    analysis = get_analysis(db, user_id, job_id)
    if posting is None or analysis is None:
        raise not_found()
    question = get_question(db, user_id, analysis.id, question_id)
    if question is None:
        raise not_found()
    if question.status != QuestionStatus.PENDING:
        raise _conflict("ALREADY_ANSWERED", "This question was already dealt with.")
    return posting, analysis, question


def answer(
    engine: Engine,
    user_id: uuid.UUID,
    job_id: uuid.UUID,
    question_id: uuid.UUID,
    payload: AnswerIn,
    ip_hash: str | None,
) -> AnalysisOut:
    text = " ".join(payload.answer.split())
    if not text or len(text) > MAX_ANSWER_CHARS:
        raise ApiError(
            422, "VALIDATION_FAILED", "Some details need fixing.",
            failure_class=FailureClass.VALIDATION_FAILED,
            fields={"answer": f"Write between 1 and {MAX_ANSWER_CHARS} characters."},
        )  # fmt: skip
    with tenant_session(engine, user_id) as db:
        posting, analysis, question = _pending_question(db, user_id, job_id, question_id)
        answer_question(db, analysis, question, text)
        out = _view(db, posting)
    record_audit(
        engine, category="audit", action="job.question_answered", actor_user_id=user_id,
        target_type="job_posting", target_id=str(job_id), ip_hash=ip_hash,
        metadata={"characters": len(text)},
    )  # fmt: skip
    return out


def skip(
    engine: Engine, user_id: uuid.UUID, job_id: uuid.UUID, question_id: uuid.UUID
) -> AnalysisOut:
    with tenant_session(engine, user_id) as db:
        posting, analysis, question = _pending_question(db, user_id, job_id, question_id)
        skip_question(db, analysis, question)
        return _view(db, posting)


def give_feedback(
    engine: Engine, user_id: uuid.UUID, job_id: uuid.UUID, payload: FeedbackIn
) -> AnalysisOut:
    with tenant_session(engine, user_id) as db:
        posting = get_posting(db, user_id, job_id)
        analysis = get_analysis(db, user_id, job_id)
        if posting is None or analysis is None:
            raise not_found()
        view = _view(db, posting)
        if payload.requirement_id is None:
            if view.score is None:
                raise _conflict("NOTHING_TO_RATE", "There is no recommendation to rate yet.")
            shown: str = view.score.band
        else:
            item = next(
                (v for v in view.verdicts if v.requirement_id == payload.requirement_id), None
            )
            if item is None:
                raise not_found()
            if item.verdict is None:
                raise _conflict("NOTHING_TO_RATE", "This requirement has no verdict yet.")
            shown = item.verdict
        note = " ".join(payload.note.split()) if payload.note else None
        save_feedback(
            db,
            owner_id=user_id,
            posting_id=job_id,
            requirement_id=payload.requirement_id,
            shown=shown,
            answer=payload.answer,
            note=note or None,
            scoring_version=SCORING_VERSION,
            prompt_version=analysis.prompt_version,
        )
        return _view(db, posting)
