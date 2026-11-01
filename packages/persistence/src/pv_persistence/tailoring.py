"""Resume tailoring: the run for one resume and job, and the suggestions it made.

Call everything here inside tenant_session (Row Level Security applies). Every statement also
filters by owner. The run holds no resume text. A suggestion holds the old and new lines of one
part of the resume, because the person needs to see and decide on them.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from pv_domain.tailoring import SuggestionStatus, TailoringStatus
from pv_domain.tasks import TASK_TAILOR_RESUME
from pv_persistence.models import ResumeTailoring, TailoringSuggestion
from pv_persistence.queue import enqueue
from pv_persistence.runs import create_run

WORKFLOW_RESUME_TAILORING = "resume_tailoring"


def get_tailoring(
    db: Session, owner_id: uuid.UUID, document_id: uuid.UUID, posting_id: uuid.UUID
) -> ResumeTailoring | None:
    return db.execute(
        select(ResumeTailoring).where(
            ResumeTailoring.owner_user_id == owner_id,
            ResumeTailoring.document_id == document_id,
            ResumeTailoring.posting_id == posting_id,
        )
    ).scalar_one_or_none()


def get_tailoring_by_id(
    db: Session, owner_id: uuid.UUID, tailoring_id: uuid.UUID
) -> ResumeTailoring | None:
    row = db.get(ResumeTailoring, tailoring_id)
    return row if row is not None and row.owner_user_id == owner_id else None


def list_tailorings(
    db: Session, owner_id: uuid.UUID, document_id: uuid.UUID
) -> list[ResumeTailoring]:
    return list(
        db.execute(
            select(ResumeTailoring)
            .where(
                ResumeTailoring.owner_user_id == owner_id,
                ResumeTailoring.document_id == document_id,
            )
            .order_by(ResumeTailoring.updated_at.desc())
        ).scalars()
    )


def start_tailoring(
    db: Session, owner_id: uuid.UUID, document_id: uuid.UUID, posting_id: uuid.UUID
) -> ResumeTailoring:
    """Begin or begin again. Starting again drops the suggestions of the last run and makes any
    task for it do nothing (the seq moves on)."""
    row = get_tailoring(db, owner_id, document_id, posting_id)
    if row is None:
        row = ResumeTailoring(
            owner_user_id=owner_id, document_id=document_id, posting_id=posting_id
        )
        db.add(row)
        db.flush()
    else:
        row.seq += 1
        row.completed_at = None
        row.model_calls = 0
        db.execute(delete(TailoringSuggestion).where(TailoringSuggestion.tailoring_id == row.id))
    run = create_run(
        db,
        owner_user_id=owner_id,
        workflow_type=WORKFLOW_RESUME_TAILORING,
        subject_type="resume_document",
        subject_id=str(document_id),
    )
    row.run_id = run.id
    row.status = TailoringStatus.QUEUED.value
    row.error_code = None
    row.updated_at = datetime.now(UTC)
    enqueue(
        db,
        task_type=TASK_TAILOR_RESUME,
        idempotency_key=f"{TASK_TAILOR_RESUME}:{row.id}:{row.seq}",
        payload={"args": {"tailoring_id": str(row.id), "seq": row.seq}},
        owner_user_id=owner_id,
        run_id=run.id,
        max_attempts=4,
    )
    db.flush()
    return row


def mark_working(db: Session, row: ResumeTailoring) -> None:
    row.status = TailoringStatus.WORKING.value
    row.updated_at = datetime.now(UTC)


def finish_tailoring(
    db: Session, row: ResumeTailoring, *, model_calls: int, prompt_version: str
) -> None:
    row.status = TailoringStatus.READY.value
    row.error_code = None
    row.model_calls = model_calls
    row.prompt_version = prompt_version
    row.completed_at = datetime.now(UTC)
    row.updated_at = row.completed_at


def fail_tailoring(db: Session, row: ResumeTailoring, code: str, *, model_calls: int = 0) -> None:
    row.status = TailoringStatus.FAILED.value
    row.error_code = code
    row.model_calls += model_calls
    row.updated_at = datetime.now(UTC)


def list_suggestions(
    db: Session, owner_id: uuid.UUID, tailoring_id: uuid.UUID
) -> list[TailoringSuggestion]:
    return list(
        db.execute(
            select(TailoringSuggestion)
            .where(
                TailoringSuggestion.owner_user_id == owner_id,
                TailoringSuggestion.tailoring_id == tailoring_id,
            )
            .order_by(TailoringSuggestion.ordinal)
        ).scalars()
    )


def get_suggestion(
    db: Session, owner_id: uuid.UUID, tailoring_id: uuid.UUID, suggestion_id: uuid.UUID
) -> TailoringSuggestion | None:
    return db.execute(
        select(TailoringSuggestion).where(
            TailoringSuggestion.id == suggestion_id,
            TailoringSuggestion.tailoring_id == tailoring_id,
            TailoringSuggestion.owner_user_id == owner_id,
        )
    ).scalar_one_or_none()


def add_suggestion(
    db: Session, row: ResumeTailoring, ordinal: int, **fields: Any
) -> TailoringSuggestion:
    suggestion = TailoringSuggestion(
        owner_user_id=row.owner_user_id, tailoring_id=row.id, ordinal=ordinal, **fields
    )
    db.add(suggestion)
    db.flush()
    return suggestion


def decide(db: Session, suggestion: TailoringSuggestion, status: SuggestionStatus) -> None:
    suggestion.status = status.value
    suggestion.decided_at = datetime.now(UTC)
