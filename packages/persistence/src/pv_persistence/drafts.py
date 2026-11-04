"""Application drafts: a cover note or an answer, for one posting.

Call everything here inside tenant_session (Row Level Security applies). Every statement also filters
by owner. What a draft says is checked in pv_domain.drafts. This module stores it and queues the
writing.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from pv_domain.drafts import DraftStatus, question_key
from pv_domain.tasks import TASK_DRAFT_APPLICATION
from pv_persistence.models import ApplicationDraft
from pv_persistence.queue import enqueue
from pv_persistence.runs import create_run

WORKFLOW_APPLICATION_DRAFT = "application_draft"


def get_draft(db: Session, owner_id: uuid.UUID, draft_id: uuid.UUID) -> ApplicationDraft | None:
    return db.execute(
        select(ApplicationDraft).where(
            ApplicationDraft.owner_user_id == owner_id, ApplicationDraft.id == draft_id
        )
    ).scalar_one_or_none()


def find_draft(
    db: Session, owner_id: uuid.UUID, posting_id: uuid.UUID, kind: str, question: str
) -> ApplicationDraft | None:
    return db.execute(
        select(ApplicationDraft).where(
            ApplicationDraft.owner_user_id == owner_id,
            ApplicationDraft.posting_id == posting_id,
            ApplicationDraft.kind == kind,
            ApplicationDraft.question_key == question_key(question),
        )
    ).scalar_one_or_none()


def list_drafts(db: Session, owner_id: uuid.UUID, posting_id: uuid.UUID) -> list[ApplicationDraft]:
    return list(
        db.execute(
            select(ApplicationDraft)
            .where(
                ApplicationDraft.owner_user_id == owner_id,
                ApplicationDraft.posting_id == posting_id,
            )
            .order_by(ApplicationDraft.kind, ApplicationDraft.created_at, ApplicationDraft.id)
        ).scalars()
    )


def count_drafts(db: Session, owner_id: uuid.UUID, posting_id: uuid.UUID) -> int:
    return int(
        db.execute(
            select(func.count())
            .select_from(ApplicationDraft)
            .where(
                ApplicationDraft.owner_user_id == owner_id,
                ApplicationDraft.posting_id == posting_id,
            )
        ).scalar_one()
    )


def start_draft(
    db: Session, *, owner_id: uuid.UUID, posting_id: uuid.UUID, kind: str, question: str
) -> ApplicationDraft:
    """Begin or begin again. The text already there stays until the new one is ready. Starting again
    makes any task for the older request do nothing (the seq moves on)."""
    row = find_draft(db, owner_id, posting_id, kind, question)
    if row is None:
        row = ApplicationDraft(
            owner_user_id=owner_id,
            posting_id=posting_id,
            kind=kind,
            question=question,
            question_key=question_key(question),
        )
        db.add(row)
        db.flush()
    else:
        row.seq += 1
    run = create_run(
        db,
        owner_user_id=owner_id,
        workflow_type=WORKFLOW_APPLICATION_DRAFT,
        subject_type="job_posting",
        subject_id=str(posting_id),
    )
    row.run_id = run.id
    row.status = DraftStatus.QUEUED.value
    row.error_code = None
    row.updated_at = datetime.now(UTC)
    enqueue(
        db,
        task_type=TASK_DRAFT_APPLICATION,
        idempotency_key=f"{TASK_DRAFT_APPLICATION}:{row.id}:{row.seq}",
        payload={"args": {"draft_id": str(row.id), "seq": row.seq}},
        owner_user_id=owner_id,
        run_id=run.id,
        max_attempts=4,
    )
    db.flush()
    return row


def mark_working(row: ApplicationDraft) -> None:
    row.status = DraftStatus.WORKING.value
    row.updated_at = datetime.now(UTC)


def finish_draft(
    row: ApplicationDraft,
    *,
    body: str,
    evidence: list[dict[str, Any]],
    claims: list[dict[str, Any]],
    prompt_version: str,
    model_calls: int,
) -> None:
    row.body = body
    row.origin = "model"
    row.evidence = evidence
    row.claims = claims
    row.status = DraftStatus.READY.value
    row.error_code = None
    row.prompt_version = prompt_version
    row.model_calls = model_calls
    row.updated_at = datetime.now(UTC)


def fail_draft(row: ApplicationDraft, code: str, *, model_calls: int = 0) -> None:
    row.status = DraftStatus.FAILED.value
    row.error_code = code
    row.model_calls = model_calls
    row.updated_at = datetime.now(UTC)


def save_edit(row: ApplicationDraft, *, body: str, claims: list[dict[str, Any]]) -> None:
    row.body = body
    row.origin = "edited"
    row.claims = claims
    row.updated_at = datetime.now(UTC)


def delete_draft(db: Session, row: ApplicationDraft) -> None:
    db.execute(delete(ApplicationDraft).where(ApplicationDraft.id == row.id))
