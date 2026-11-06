"""A person's own data: take a copy of it, and remove it all.

Export. One JSON document of what the person put into the product: their preferences, profile
entries, resumes made in the studio, jobs with the decisions and notes they wrote, application
drafts and their saved views. Never a password, a token, a storage key or anyone else's data.

Deletion. The tables that hold a person's data all reference the user with ON DELETE CASCADE, so
removing the user row removes them (a test walks every foreign key to users to prove nothing is
left). Three things the cascade cannot reach are removed here:
  - the stored files (resumes, pictures, PDFs, reports, uploaded spreadsheets), which are outside
    the database and are listed before the rows go
  - rate limit counters, whose key ends with the person's id
  - the address in an invite bound to it and in a queued email

Call the tenant functions inside tenant_session, the system functions with a plain session.
"""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, cast

from sqlalchemy import CursorResult, select, text, update
from sqlalchemy.orm import Session

from pv_persistence.models import (
    AccountDeletion,
    ApplicationDraft,
    GitHubConnection,
    ImportBatch,
    JobDecision,
    JobPosting,
    ProfileEntry,
    ProfilePreferences,
    ReportExport,
    Resume,
    ResumeDocument,
    ResumeExport,
    ResumeImage,
    User,
    UserPlan,
    WorkbenchView,
)

EXPORT_VERSION = 1


def _plain(value: Any) -> Any:
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_plain(v) for v in value]
    return value


def _row(obj: Any, keep: tuple[str, ...]) -> dict[str, Any]:
    return {name: _plain(getattr(obj, name)) for name in keep}


# ------------------------------------------------------------------ the copy


def export_data(db: Session, user: User) -> dict[str, Any]:
    """Everything the person put in, as plain data. Run inside tenant_session."""
    owner = user.id

    def rows(model: Any) -> list[Any]:
        return list(
            db.execute(
                select(model).where(model.owner_user_id == owner).order_by(model.created_at)
            ).scalars()
        )

    prefs = db.execute(
        select(ProfilePreferences).where(ProfilePreferences.owner_user_id == owner)
    ).scalar_one_or_none()
    plan = db.execute(select(UserPlan).where(UserPlan.owner_user_id == owner)).scalar_one_or_none()
    github = db.execute(
        select(GitHubConnection).where(GitHubConnection.owner_user_id == owner)
    ).scalar_one_or_none()
    decisions = {
        d.posting_id: d
        for d in db.execute(select(JobDecision).where(JobDecision.owner_user_id == owner)).scalars()
    }
    jobs = []
    for posting in rows(JobPosting):
        decision = decisions.get(posting.id)
        jobs.append(
            {
                **_row(
                    posting,
                    (
                        "title",
                        "company",
                        "source_name",
                        "source_url",
                        "acquisition_method",
                        "created_at",
                    ),
                ),
                "posting_text": posting.raw_text,
                "decision": None
                if decision is None
                else _row(decision, ("state", "note", "applied_at", "updated_at")),
            }
        )
    return {
        "export_version": EXPORT_VERSION,
        "exported_at": datetime.now(UTC).isoformat(),
        "about": (
            "A copy of the data you put into Provenance. It does not include your password, "
            "sign-in sessions, connector tokens or the files you uploaded (your resume files and "
            "pictures stay in the product until you delete them)."
        ),
        "account": {
            "email": user.email,
            "created_at": _plain(user.created_at),
            "email_verified": user.email_verified_at is not None,
            "plan": plan.plan_id if plan else None,
        },
        "preferences": None
        if prefs is None
        else _row(
            prefs,
            (
                "target_roles",
                "authorized_countries",
                "needs_sponsorship",
                "locations",
                "open_to_relocate",
                "remote_preference",
                "employment_types",
                "min_salary_amount",
                "min_salary_currency",
                "exclusions",
            ),
        ),  # fmt: skip
        "profile_entries": [
            _row(e, ("entry_type", "data", "source", "created_at", "updated_at"))
            for e in rows(ProfileEntry)
        ],
        "resumes_made_in_the_studio": [
            _row(d, ("title", "content", "created_at", "updated_at")) for d in rows(ResumeDocument)
        ],
        "uploaded_resumes": [
            _row(r, ("original_filename", "file_kind", "size_bytes", "created_at"))
            for r in rows(Resume)
        ],
        "jobs": jobs,
        "application_drafts": [
            _row(d, ("kind", "question", "body", "origin", "created_at", "updated_at"))
            for d in rows(ApplicationDraft)
        ],
        "saved_views": [_row(v, ("name", "query", "created_at")) for v in rows(WorkbenchView)],
        "github_connection": None
        if github is None
        else {"login": github.login, "connected_at": _plain(github.connected_at)},
    }


# ------------------------------------------------------------------ the files


def storage_keys(db: Session) -> list[str]:
    """Every stored file that belongs to the person in this tenant session, so they can be removed
    before the rows that name them are gone."""
    keys: list[str] = []
    for model, column in (
        (Resume, Resume.storage_key),
        (ResumeImage, ResumeImage.storage_key),
        (ResumeExport, ResumeExport.storage_key),
        (ReportExport, ReportExport.storage_key),
        (ImportBatch, ImportBatch.file_key),
    ):
        keys += [
            str(k)
            for k in db.execute(select(column).where(model.owner_user_id == _owner(db))).scalars()
            if k
        ]
    return sorted(set(keys))


def _count(result: object) -> int:
    return int(cast(CursorResult[object], result).rowcount or 0)


def _owner(db: Session) -> uuid.UUID:
    value: object = db.execute(
        text("SELECT nullif(current_setting('app.user_id', true), '')::uuid")
    ).scalar_one()
    return uuid.UUID(str(value))


# ------------------------------------------------------------------ the request and the record


def request_deletion(db: Session, user_id: uuid.UUID) -> uuid.UUID:
    """Mark the account as being deleted (inactive, cannot sign in) and open the minimal record."""
    now = datetime.now(UTC)
    db.execute(
        update(User).where(User.id == user_id).values(is_active=False, deletion_requested_at=now)
    )
    record = AccountDeletion(requested_at=now)
    db.add(record)
    db.flush()
    return record.id


def mark_running(db: Session, deletion_id: uuid.UUID) -> None:
    db.execute(
        update(AccountDeletion)
        .where(AccountDeletion.id == deletion_id, AccountDeletion.status == "queued")
        .values(status="running", started_at=datetime.now(UTC))
    )


def finish_deletion(db: Session, deletion_id: uuid.UUID, *, files: int, strays: int) -> None:
    db.execute(
        update(AccountDeletion)
        .where(AccountDeletion.id == deletion_id)
        .values(
            status="done",
            completed_at=datetime.now(UTC),
            files_removed=files,
            stray_rows_removed=strays,
            error_code=None,
        )
    )


def fail_deletion(db: Session, deletion_id: uuid.UUID, code: str) -> None:
    db.execute(
        update(AccountDeletion)
        .where(AccountDeletion.id == deletion_id)
        .values(status="failed", error_code=code[:40])
    )


# ------------------------------------------------------------------ what the cascade cannot reach


def purge_strays(db: Session, user_id: uuid.UUID, email: str) -> int:
    """Remove what the foreign keys do not: rate limit counters named with the id, the address in a
    bound invite, and an unsent email to the address. Returns how many rows were touched."""
    touched = 0
    touched += _count(
        db.execute(
            text("DELETE FROM rate_limit_buckets WHERE bucket_key LIKE :suffix"),
            {"suffix": f"%:{user_id}"},
        )
    )
    touched += _count(
        db.execute(
            text("UPDATE invites SET email = NULL WHERE lower(email) = lower(:e)"), {"e": email}
        )
    )
    touched += _count(
        db.execute(
            text(
                "DELETE FROM tasks WHERE state IN ('queued', 'retry_scheduled') "
                "AND lower(payload->'secret'->>'to') = lower(:e)"
            ),
            {"e": email},
        )
    )
    return touched


def remove_user(db: Session, user_id: uuid.UUID) -> bool:
    """Delete the user row. Every table that holds the person's data cascades from it."""
    return _count(db.execute(text("DELETE FROM users WHERE id = :u"), {"u": user_id})) > 0
