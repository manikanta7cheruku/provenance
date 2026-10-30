"""Resume lifecycle: upload, state, download, delete, re-parse, confirm.

Every function runs inside one tenant session (Row Level Security) and filters by the
authenticated owner as well. Another person's resume is "not found", never "forbidden".
The file itself is only ever returned to code that has just loaded the row for its owner.
"""

import hashlib
import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from pv_api.errors import ApiError
from pv_api.schemas import ResumeOut
from pv_domain.failures import FailureClass
from pv_domain.resume import (
    ERROR_MESSAGES,
    MAX_UPLOAD_BYTES,
    ParseStatus,
    ReviewStatus,
    resume_ui_state,
    safe_display_filename,
)
from pv_domain.tasks import TASK_PARSE_RESUME
from pv_files import FileStorage, StorageError, check_upload, new_resume_key
from pv_persistence.audit import record_audit
from pv_persistence.models import Resume
from pv_persistence.resumes import flagged_entry_count, get_resume, list_entries, start_parse
from pv_persistence.tenancy import tenant_session

logger = logging.getLogger("pv_api")


def not_found() -> ApiError:
    return ApiError(404, "NOT_FOUND", "Not found.", failure_class=FailureClass.PERMANENT)


def _conflict(code: str, message: str) -> ApiError:
    return ApiError(409, code, message, failure_class=FailureClass.USER_ACTION_REQUIRED)


def to_out(resume: Resume, flagged: int) -> ResumeOut:
    ui_state = resume_ui_state(resume.parse_status, resume.review_status, flagged)
    failed = resume.parse_status == ParseStatus.PARSE_FAILED
    code = resume.error_code or ""
    return ResumeOut(
        id=resume.id,
        original_filename=resume.original_filename,
        file_kind=resume.file_kind,  # type: ignore[arg-type]
        size_bytes=resume.size_bytes,
        ui_state=ui_state.value,
        can_retry=resume.parse_status in (ParseStatus.PARSED, ParseStatus.PARSE_FAILED),
        error_message=ERROR_MESSAGES.get(code) if failed else None,
        kept_entry_count=resume.kept_entry_count,
        dropped_entry_count=resume.dropped_entry_count,
        flagged_entry_count=flagged,
        page_count=resume.page_count,
        run_id=resume.run_id,
        created_at=resume.created_at,
        parsed_at=resume.parsed_at,
        confirmed_at=resume.confirmed_at,
    )


def current(engine: Engine, user_id: uuid.UUID) -> ResumeOut | None:
    with tenant_session(engine, user_id) as db:
        resume = get_resume(db, user_id)
        if resume is None:
            return None
        return to_out(resume, flagged_entry_count(list_entries(db, user_id)))


def upload(
    engine: Engine,
    storage: FileStorage,
    *,
    user_id: uuid.UUID,
    data: bytes,
    filename: str,
    ip_hash: str | None,
) -> ResumeOut:
    if not data:
        raise ApiError(
            400,
            "EMPTY_FILE",
            "This file is empty. Choose a different file.",
            failure_class=FailureClass.VALIDATION_FAILED,
        )
    if len(data) > MAX_UPLOAD_BYTES:
        raise ApiError(
            413,
            "PAYLOAD_TOO_LARGE",
            "This file is over the 5 MB limit. Choose a smaller file.",
            failure_class=FailureClass.VALIDATION_FAILED,
        )
    kind = check_upload(data)
    if kind is None:
        raise ApiError(
            415,
            "UNSUPPORTED_FILE",
            "This file type is not supported. Choose a PDF or DOCX file.",
            failure_class=FailureClass.VALIDATION_FAILED,
        )
    key = new_resume_key()
    try:
        storage.put(key, data)
    except StorageError as exc:
        logger.error("resume_store_failed", exc_info=True)
        raise ApiError(
            503,
            "STORAGE_UNAVAILABLE",
            "We could not store your file. Nothing was saved. Try again in a moment.",
            failure_class=FailureClass.TRANSIENT,
        ) from exc
    try:
        with tenant_session(engine, user_id) as db:
            if get_resume(db, user_id) is not None:
                raise _conflict(
                    "RESUME_EXISTS",
                    "You already have a resume. Delete it first to upload a different one.",
                )
            resume = Resume(
                owner_user_id=user_id,
                original_filename=safe_display_filename(filename),
                file_kind=kind,
                size_bytes=len(data),
                sha256=hashlib.sha256(data).hexdigest(),
                storage_key=key,
            )
            db.add(resume)
            db.flush()
            start_parse(db, resume, reparse=False)
            db.flush()
            out = to_out(resume, 0)
    except IntegrityError as exc:
        _discard(storage, key)
        raise _conflict(
            "RESUME_EXISTS",
            "You already have a resume. Delete it first to upload a different one.",
        ) from exc
    except Exception:
        _discard(storage, key)
        raise
    record_audit(
        engine,
        category="audit",
        action="resume.uploaded",
        actor_user_id=user_id,
        target_type="resume",
        target_id=str(out.id),
        ip_hash=ip_hash,
        metadata={"kind": kind, "bytes": len(data)},
    )
    return out


def _discard(storage: FileStorage, key: str) -> None:
    try:
        storage.delete(key)
    except StorageError:
        logger.warning("orphan_file", extra={"path": key})


def download(engine: Engine, storage: FileStorage, user_id: uuid.UUID) -> tuple[bytes, str, str]:
    """Return (bytes, file_kind, display name) for the owner's resume."""
    with tenant_session(engine, user_id) as db:
        resume = get_resume(db, user_id)
        if resume is None:
            raise not_found()
        key, kind, name = resume.storage_key, resume.file_kind, resume.original_filename
    try:
        return storage.get(key), kind, name
    except StorageError as exc:
        raise not_found() from exc


def delete(
    engine: Engine, storage: FileStorage, *, user_id: uuid.UUID, ip_hash: str | None
) -> None:
    """Remove the file and the row. Profile entries stay: they belong to the person."""
    with tenant_session(engine, user_id) as db:
        resume = get_resume(db, user_id)
        if resume is None:
            raise not_found()
        key, resume_id = resume.storage_key, resume.id
        # A parse that has not started yet must not run for a resume that no longer exists.
        db.execute(
            text(
                "UPDATE tasks SET state = 'cancelled', finished_at = now(), updated_at = now() "
                "WHERE task_type = :task_type AND state IN ('queued', 'retry_scheduled') "
                "AND payload->'args'->>'resume_id' = :resume_id"
            ),
            {"task_type": TASK_PARSE_RESUME, "resume_id": str(resume_id)},
        )
        db.delete(resume)
    try:
        storage.delete(key)
    except StorageError:
        # The row is gone, so the file is unreachable. Log the opaque key for a cleanup sweep.
        logger.warning("orphan_file", extra={"path": key})
    record_audit(
        engine,
        category="audit",
        action="resume.deleted",
        actor_user_id=user_id,
        target_type="resume",
        target_id=str(resume_id),
        ip_hash=ip_hash,
    )


def reparse(engine: Engine, *, user_id: uuid.UUID) -> ResumeOut:
    with tenant_session(engine, user_id) as db:
        resume = get_resume(db, user_id)
        if resume is None:
            raise not_found()
        if resume.parse_status not in (ParseStatus.PARSED, ParseStatus.PARSE_FAILED):
            raise _conflict("PARSE_IN_PROGRESS", "Your resume is still being read. Please wait.")
        start_parse(db, resume, reparse=True)
        db.flush()
        return to_out(resume, flagged_entry_count(list_entries(db, user_id)))


def confirm(engine: Engine, *, user_id: uuid.UUID) -> ResumeOut:
    with tenant_session(engine, user_id) as db:
        resume = get_resume(db, user_id)
        if resume is None:
            raise not_found()
        if resume.parse_status != ParseStatus.PARSED:
            raise _conflict(
                "NOT_READY", "Your resume has not been read yet. Confirm after it finishes."
            )
        resume.review_status = ReviewStatus.CONFIRMED.value
        resume.confirmed_at = datetime.now(UTC)
        resume.updated_at = datetime.now(UTC)
        db.flush()
        return to_out(resume, flagged_entry_count(list_entries(db, user_id)))
