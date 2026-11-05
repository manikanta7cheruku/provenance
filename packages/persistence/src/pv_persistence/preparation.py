"""Career preparation: the interview date and company notes, generated outputs, progress and mock
interviews.

Call everything here inside tenant_session (Row Level Security applies). Every statement also
filters by owner. What preparation means is decided in pv_domain.preparation. This module stores
it and queues the writing.
"""

import uuid
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from pv_domain.tasks import TASK_PREPARE_JOB
from pv_persistence.models import JobPreparation, MockInterview, PrepOutput, PrepProgress
from pv_persistence.queue import enqueue
from pv_persistence.runs import create_run

WORKFLOW_PREPARATION = "career_preparation"

QUEUED, WORKING, READY, FAILED = "queued", "working", "ready", "failed"


# ---------------------------------------------------------------- the date and the company notes


def get_prep(db: Session, owner_id: uuid.UUID, posting_id: uuid.UUID) -> JobPreparation | None:
    return db.execute(
        select(JobPreparation).where(
            JobPreparation.owner_user_id == owner_id, JobPreparation.posting_id == posting_id
        )
    ).scalar_one_or_none()


def ensure_prep(db: Session, owner_id: uuid.UUID, posting_id: uuid.UUID) -> JobPreparation:
    row = get_prep(db, owner_id, posting_id)
    if row is None:
        row = JobPreparation(owner_user_id=owner_id, posting_id=posting_id)
        db.add(row)
        db.flush()
    return row


def set_interview_date(
    db: Session, owner_id: uuid.UUID, posting_id: uuid.UUID, when: date | None
) -> JobPreparation:
    row = ensure_prep(db, owner_id, posting_id)
    row.interview_date = when
    row.updated_at = datetime.now(UTC)
    return row


def set_company(
    db: Session, owner_id: uuid.UUID, posting_id: uuid.UUID, link: str, notes: str
) -> JobPreparation:
    row = ensure_prep(db, owner_id, posting_id)
    row.company_link = link
    row.company_notes = notes
    row.updated_at = datetime.now(UTC)
    return row


# ---------------------------------------------------------------- generated outputs


def get_output(
    db: Session, owner_id: uuid.UUID, posting_id: uuid.UUID, action: str
) -> PrepOutput | None:
    return db.execute(
        select(PrepOutput).where(
            PrepOutput.owner_user_id == owner_id,
            PrepOutput.posting_id == posting_id,
            PrepOutput.action == action,
        )
    ).scalar_one_or_none()


def get_output_by_id(db: Session, owner_id: uuid.UUID, output_id: uuid.UUID) -> PrepOutput | None:
    return db.execute(
        select(PrepOutput).where(PrepOutput.owner_user_id == owner_id, PrepOutput.id == output_id)
    ).scalar_one_or_none()


def list_outputs(db: Session, owner_id: uuid.UUID, posting_id: uuid.UUID) -> list[PrepOutput]:
    return list(
        db.execute(
            select(PrepOutput)
            .where(PrepOutput.owner_user_id == owner_id, PrepOutput.posting_id == posting_id)
            .order_by(PrepOutput.action)
        ).scalars()
    )


def start_output(
    db: Session, *, owner_id: uuid.UUID, posting_id: uuid.UUID, action: str
) -> PrepOutput:
    """Begin or begin again. What is there stays until the new result is ready. Starting again makes
    any task for the older request do nothing (the seq moves on)."""
    row = get_output(db, owner_id, posting_id, action)
    if row is None:
        row = PrepOutput(owner_user_id=owner_id, posting_id=posting_id, action=action)
        db.add(row)
        db.flush()
    else:
        row.seq += 1
    run = create_run(
        db,
        owner_user_id=owner_id,
        workflow_type=WORKFLOW_PREPARATION,
        subject_type="job_posting",
        subject_id=str(posting_id),
    )
    row.run_id = run.id
    row.status = QUEUED
    row.error_code = None
    row.updated_at = datetime.now(UTC)
    enqueue(
        db,
        task_type=TASK_PREPARE_JOB,
        idempotency_key=f"{TASK_PREPARE_JOB}:{row.id}:{row.seq}",
        payload={"args": {"output_id": str(row.id), "seq": row.seq}},
        owner_user_id=owner_id,
        run_id=run.id,
        max_attempts=4,
    )
    db.flush()
    return row


def mark_working(row: PrepOutput) -> None:
    row.status = WORKING
    row.updated_at = datetime.now(UTC)


def finish_output(
    row: PrepOutput,
    *,
    items: list[dict[str, Any]],
    body: str,
    evidence: list[dict[str, Any]],
    claims: list[dict[str, Any]],
    prompt_version: str,
    model_calls: int,
) -> None:
    row.items = items
    row.body = body
    row.origin = "model"
    row.evidence = evidence
    row.claims = claims
    row.status = READY
    row.error_code = None
    row.prompt_version = prompt_version
    row.model_calls = model_calls
    row.updated_at = datetime.now(UTC)


def fail_output(row: PrepOutput, code: str, *, model_calls: int = 0) -> None:
    row.status = FAILED
    row.error_code = code
    row.model_calls = model_calls
    row.updated_at = datetime.now(UTC)


def save_output_edit(row: PrepOutput, *, body: str, claims: list[dict[str, Any]]) -> None:
    row.body = body
    row.origin = "edited"
    row.claims = claims
    row.updated_at = datetime.now(UTC)


# ---------------------------------------------------------------- progress


def done_keys(db: Session, owner_id: uuid.UUID, posting_id: uuid.UUID) -> set[str]:
    return set(
        db.execute(
            select(PrepProgress.item_key).where(
                PrepProgress.owner_user_id == owner_id,
                PrepProgress.posting_id == posting_id,
                PrepProgress.done.is_(True),
            )
        ).scalars()
    )


def set_done(db: Session, owner_id: uuid.UUID, posting_id: uuid.UUID, key: str, done: bool) -> None:
    row = db.execute(
        select(PrepProgress).where(
            PrepProgress.owner_user_id == owner_id,
            PrepProgress.posting_id == posting_id,
            PrepProgress.item_key == key,
        )
    ).scalar_one_or_none()
    if row is None:
        db.add(PrepProgress(owner_user_id=owner_id, posting_id=posting_id, item_key=key, done=done))
    else:
        row.done = done
        row.updated_at = datetime.now(UTC)
    db.flush()


# ---------------------------------------------------------------- mock interviews


def latest_mock(db: Session, owner_id: uuid.UUID, posting_id: uuid.UUID) -> MockInterview | None:
    return db.execute(
        select(MockInterview)
        .where(MockInterview.owner_user_id == owner_id, MockInterview.posting_id == posting_id)
        .order_by(MockInterview.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()


def get_mock(db: Session, owner_id: uuid.UUID, mock_id: uuid.UUID) -> MockInterview | None:
    return db.execute(
        select(MockInterview).where(
            MockInterview.owner_user_id == owner_id, MockInterview.id == mock_id
        )
    ).scalar_one_or_none()


def start_mock(
    db: Session, owner_id: uuid.UUID, posting_id: uuid.UUID, questions: list[dict[str, Any]]
) -> MockInterview:
    """Begin a practice session. An earlier unfinished one is finished: one live session."""
    current = latest_mock(db, owner_id, posting_id)
    if current is not None and current.state == "active":
        current.state = "finished"
        current.finished_at = datetime.now(UTC)
    row = MockInterview(
        owner_user_id=owner_id, posting_id=posting_id, questions=questions, turns=[], state="active"
    )
    db.add(row)
    db.flush()
    return row


def add_turn(row: MockInterview, turn: dict[str, Any]) -> None:
    row.turns = [*row.turns, turn]
    if len(row.turns) >= len(row.questions):
        row.state = "finished"
        row.finished_at = datetime.now(UTC)


def finish_mock(row: MockInterview) -> None:
    row.state = "finished"
    row.finished_at = datetime.now(UTC)
