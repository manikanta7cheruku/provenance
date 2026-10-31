"""The evidence check of a job: the analysis, its verdicts, the agent's questions, feedback.

Call everything here inside tenant_session (Row Level Security applies). Every statement also
filters by owner.

The agent's progress is the data itself. A verdict is saved the moment it is accepted, a question
the moment it is asked. A worker that dies and restarts reads this and carries on with the
requirements that have neither, so there is no separate checkpoint to keep in step.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from pv_domain.analysis import AnalysisErrorCode, AnalysisStatus, QuestionStatus, Verdict
from pv_domain.evidence import clean_chunk_text, content_hash
from pv_domain.states import RunState
from pv_domain.tasks import TASK_ANALYZE_JOB
from pv_persistence.evidence import enqueue_embedding
from pv_persistence.models import (
    AgentQuestion,
    EvidenceChunk,
    JobAnalysis,
    JobPosting,
    RequirementVerdict,
    VerdictFeedback,
)
from pv_persistence.queue import enqueue
from pv_persistence.runs import create_run, set_run_state

WORKFLOW_JOB_ANALYSIS = "job_analysis"
SOURCE_USER_ANSWER = "user_answer"
ANSWER_PREFIX = "In my own words: "


def get_analysis(db: Session, owner_id: uuid.UUID, posting_id: uuid.UUID) -> JobAnalysis | None:
    return db.execute(
        select(JobAnalysis).where(
            JobAnalysis.owner_user_id == owner_id, JobAnalysis.posting_id == posting_id
        )
    ).scalar_one_or_none()


def evidence_chunk_count(db: Session, owner_id: uuid.UUID) -> int:
    return int(
        db.execute(
            text("SELECT count(*) FROM evidence_chunks WHERE owner_user_id = :o"), {"o": owner_id}
        ).scalar_one()
    )


def list_verdicts(
    db: Session, owner_id: uuid.UUID, analysis_id: uuid.UUID
) -> list[RequirementVerdict]:
    return list(
        db.execute(
            select(RequirementVerdict).where(
                RequirementVerdict.owner_user_id == owner_id,
                RequirementVerdict.analysis_id == analysis_id,
            )
        ).scalars()
    )


def list_questions(db: Session, owner_id: uuid.UUID, analysis_id: uuid.UUID) -> list[AgentQuestion]:
    return list(
        db.execute(
            select(AgentQuestion)
            .where(
                AgentQuestion.owner_user_id == owner_id, AgentQuestion.analysis_id == analysis_id
            )
            .order_by(AgentQuestion.created_at)
        ).scalars()
    )


def get_question(
    db: Session, owner_id: uuid.UUID, analysis_id: uuid.UUID, question_id: uuid.UUID
) -> AgentQuestion | None:
    return db.execute(
        select(AgentQuestion).where(
            AgentQuestion.id == question_id,
            AgentQuestion.analysis_id == analysis_id,
            AgentQuestion.owner_user_id == owner_id,
        )
    ).scalar_one_or_none()


def chunk_state(db: Session, owner_id: uuid.UUID, ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
    """The current content hash of each chunk that still exists."""
    if not ids:
        return {}
    rows = db.execute(
        select(EvidenceChunk.id, EvidenceChunk.content_hash).where(
            EvidenceChunk.owner_user_id == owner_id, EvidenceChunk.id.in_(ids)
        )
    )
    return {row.id: row.content_hash for row in rows}


def _queue(db: Session, analysis: JobAnalysis, posting_id: uuid.UUID) -> None:
    run = create_run(
        db,
        owner_user_id=analysis.owner_user_id,
        workflow_type=WORKFLOW_JOB_ANALYSIS,
        subject_type="job_posting",
        subject_id=str(posting_id),
    )
    analysis.run_id = run.id
    analysis.status = AnalysisStatus.QUEUED.value
    analysis.error_code = None
    analysis.updated_at = datetime.now(UTC)
    enqueue(
        db,
        task_type=TASK_ANALYZE_JOB,
        idempotency_key=f"{TASK_ANALYZE_JOB}:{analysis.id}:{analysis.resume_seq}",
        payload={"args": {"analysis_id": str(analysis.id), "seq": analysis.resume_seq}},
        owner_user_id=analysis.owner_user_id,
        run_id=run.id,
        max_attempts=4,
    )


def start_analysis(db: Session, posting: JobPosting, existing: JobAnalysis | None) -> JobAnalysis:
    """Begin or continue an evidence check.

    New: create it. Failed: continue, keeping the verdicts already earned. Complete: start over
    (the profile may have changed), keeping answers the person already gave, because those are
    evidence now.
    """
    if existing is None:
        analysis = JobAnalysis(owner_user_id=posting.owner_user_id, posting_id=posting.id)
        db.add(analysis)
        db.flush()
    else:
        analysis = existing
        analysis.resume_seq += 1
        if existing.status == AnalysisStatus.COMPLETE:
            db.execute(
                delete(RequirementVerdict).where(RequirementVerdict.analysis_id == analysis.id)
            )
            db.execute(
                delete(AgentQuestion).where(
                    AgentQuestion.analysis_id == analysis.id,
                    AgentQuestion.status != QuestionStatus.ANSWERED.value,
                )
            )
            analysis.completed_at = None
    _queue(db, analysis, posting.id)
    db.flush()
    return analysis


def save_verdict(
    db: Session,
    analysis: JobAnalysis,
    requirement_id: uuid.UUID,
    *,
    verdict: str,
    evidence_kind: str | None,
    reason_code: str | None,
    reason: str,
    citations: list[dict[str, Any]],
    capped: bool,
    steps: int,
) -> bool:
    """Store a verdict unless the requirement already has one. Returns True if stored."""
    present = db.execute(
        select(RequirementVerdict.id).where(
            RequirementVerdict.analysis_id == analysis.id,
            RequirementVerdict.requirement_id == requirement_id,
        )
    ).first()
    if present is not None:
        return False
    db.add(
        RequirementVerdict(
            owner_user_id=analysis.owner_user_id,
            analysis_id=analysis.id,
            requirement_id=requirement_id,
            verdict=verdict,
            evidence_kind=evidence_kind,
            reason_code=reason_code,
            reason=reason,
            citations=citations,
            capped=capped,
            steps=steps,
        )
    )
    db.flush()
    return True


def create_question(
    db: Session, analysis: JobAnalysis, requirement_id: uuid.UUID, question: str
) -> AgentQuestion:
    existing = db.execute(
        select(AgentQuestion).where(
            AgentQuestion.analysis_id == analysis.id, AgentQuestion.requirement_id == requirement_id
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    item = AgentQuestion(
        owner_user_id=analysis.owner_user_id,
        analysis_id=analysis.id,
        requirement_id=requirement_id,
        question=question,
    )
    db.add(item)
    db.flush()
    return item


def finish_analysis(
    db: Session,
    analysis: JobAnalysis,
    *,
    status: AnalysisStatus,
    model_calls: int,
    tool_calls: int,
    prompt_version: str,
) -> None:
    now = datetime.now(UTC)
    analysis.status = status.value
    analysis.model_calls += model_calls
    analysis.tool_calls += tool_calls
    analysis.prompt_version = prompt_version
    analysis.error_code = None
    analysis.updated_at = now
    analysis.completed_at = now if status == AnalysisStatus.COMPLETE else None
    if analysis.run_id is not None:
        set_run_state(db, analysis.run_id, RunState.SUCCEEDED)


def fail_analysis(db: Session, analysis: JobAnalysis, code: AnalysisErrorCode) -> None:
    analysis.status = AnalysisStatus.FAILED.value
    analysis.error_code = code.value
    analysis.updated_at = datetime.now(UTC)
    if analysis.run_id is not None:
        set_run_state(
            db,
            analysis.run_id,
            RunState.FAILED,
            can_retry=True,
            error_class="JOB_ANALYSIS_FAILED",
            error_type="JobAnalysis",
            error_message=code.value,
        )


def answer_question(
    db: Session, analysis: JobAnalysis, question: AgentQuestion, answer: str
) -> None:
    """Record the answer as evidence and queue the agent to carry on."""
    body = clean_chunk_text(ANSWER_PREFIX + answer)
    question.status = QuestionStatus.ANSWERED.value
    question.answer = answer
    question.answered_at = datetime.now(UTC)
    chunk = db.execute(
        select(EvidenceChunk).where(
            EvidenceChunk.owner_user_id == analysis.owner_user_id,
            EvidenceChunk.source_type == SOURCE_USER_ANSWER,
            EvidenceChunk.source_record_id == question.id,
        )
    ).scalar_one_or_none()
    if chunk is None:
        db.add(
            EvidenceChunk(
                owner_user_id=analysis.owner_user_id,
                source_type=SOURCE_USER_ANSWER,
                source_record_id=question.id,
                entry_type=None,
                text=body,
                content_hash=content_hash(body),
            )
        )
    db.flush()
    enqueue_embedding(db, analysis.owner_user_id)
    analysis.resume_seq += 1
    _queue(db, analysis, analysis.posting_id)
    db.flush()


def skip_question(db: Session, analysis: JobAnalysis, question: AgentQuestion) -> None:
    """The person declined. The requirement stays unverified and the check can finish."""
    question.status = QuestionStatus.SKIPPED.value
    question.answered_at = datetime.now(UTC)
    save_verdict(
        db,
        analysis,
        question.requirement_id,
        verdict=Verdict.NOT_VERIFIED.value,
        evidence_kind=None,
        reason_code="user_skipped",
        reason="",
        citations=[],
        capped=False,
        steps=0,
    )
    pending = db.execute(
        select(AgentQuestion.id).where(
            AgentQuestion.analysis_id == analysis.id,
            AgentQuestion.status == QuestionStatus.PENDING.value,
        )
    ).first()
    if pending is None and analysis.status == AnalysisStatus.NEEDS_USER_INPUT:
        analysis.status = AnalysisStatus.COMPLETE.value
        analysis.completed_at = datetime.now(UTC)
    analysis.updated_at = datetime.now(UTC)
    db.flush()


def delete_analysis(db: Session, owner_id: uuid.UUID, posting_id: uuid.UUID) -> None:
    """Remove an analysis and the answers given for it. Deleting a job deletes its answers too."""
    analysis = get_analysis(db, owner_id, posting_id)
    if analysis is None:
        return
    db.execute(
        text(
            "DELETE FROM evidence_chunks WHERE owner_user_id = :o AND source_type = 'user_answer' "
            "AND source_record_id IN (SELECT id FROM agent_questions WHERE analysis_id = :a)"
        ),
        {"o": owner_id, "a": analysis.id},
    )
    db.execute(
        text(
            "UPDATE tasks SET state = 'cancelled', finished_at = now(), updated_at = now() "
            "WHERE task_type = :t AND state IN ('queued', 'retry_scheduled') "
            "AND payload->'args'->>'analysis_id' = :a"
        ),
        {"t": TASK_ANALYZE_JOB, "a": str(analysis.id)},
    )
    db.delete(analysis)
    db.flush()


def get_feedback(db: Session, owner_id: uuid.UUID, posting_id: uuid.UUID) -> list[VerdictFeedback]:
    return list(
        db.execute(
            select(VerdictFeedback).where(
                VerdictFeedback.owner_user_id == owner_id, VerdictFeedback.posting_id == posting_id
            )
        ).scalars()
    )


def save_feedback(
    db: Session,
    *,
    owner_id: uuid.UUID,
    posting_id: uuid.UUID,
    requirement_id: uuid.UUID | None,
    shown: str,
    answer: str,
    note: str | None,
    scoring_version: str,
    prompt_version: str | None,
) -> VerdictFeedback:
    """One answer per item. Answering again replaces the earlier answer."""
    subject = "verdict" if requirement_id is not None else "recommendation"
    query = select(VerdictFeedback).where(
        VerdictFeedback.owner_user_id == owner_id, VerdictFeedback.posting_id == posting_id
    )
    if requirement_id is None:
        query = query.where(VerdictFeedback.requirement_id.is_(None))
    else:
        query = query.where(VerdictFeedback.requirement_id == requirement_id)
    row = db.execute(query).scalars().first()
    if row is None:
        row = VerdictFeedback(
            owner_user_id=owner_id,
            posting_id=posting_id,
            requirement_id=requirement_id,
            subject=subject,
            shown=shown,
            answer=answer,
            note=note,
            scoring_version=scoring_version,
            prompt_version=prompt_version,
        )
        db.add(row)
    else:
        row.shown = shown
        row.answer = answer
        row.note = note
        row.scoring_version = scoring_version
        row.prompt_version = prompt_version
        row.updated_at = datetime.now(UTC)
    db.flush()
    return row
