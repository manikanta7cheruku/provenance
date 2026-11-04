"""Bringing jobs in: type one in, upload a spreadsheet, or ask us to read a web page.

Everything runs in one tenant session (Row Level Security) and filters by the signed-in owner.
A batch that belongs to someone else is "not found", never "forbidden".

The API itself never requests a web address and never opens a spreadsheet: it checks the address or
the first bytes of the file, stores the file in private storage and queues a task. The worker does
the reading, with its own limits (see pv_worker.safe_fetch and pv_files.tabular). What a person
sees is the batch and its report.
"""

import contextlib
import uuid

from sqlalchemy.engine import Engine

from pv_api.errors import ApiError
from pv_api.schemas import (
    ImportBatchOut,
    ImportDetailOut,
    ImportItemOut,
    ImportUrlIn,
    JobCreatedOut,
    JobManualIn,
)
from pv_api.services import job_service
from pv_domain.failures import FailureClass
from pv_domain.job import SOURCE_NAMES
from pv_domain.job_import import (
    ACQUISITION_MANUAL,
    FILE_MESSAGES,
    PAGE_MESSAGES,
    ROW_MESSAGES,
    ImportFileError,
    build_draft,
)
from pv_domain.url_safety import UrlRefused, check_import_url
from pv_files import FileStorage, StorageError, check_table_upload, new_import_key
from pv_persistence.audit import record_audit
from pv_persistence.imports import (
    create_file_batch,
    create_url_batch,
    get_batch,
    list_batches,
    list_items,
)
from pv_persistence.models import ImportBatch
from pv_persistence.tenancy import tenant_session

_FIELD_OF_PROBLEM = {
    "title_too_long": "title",
    "company_too_long": "company",
    "location_too_long": "location",
    "bad_link": "source_url",
    "too_short": "description",
    "too_long": "description",
    "no_description": "description",
}


def _validation(fields: dict[str, str]) -> ApiError:
    return ApiError(
        422,
        "VALIDATION_FAILED",
        "Some details need fixing.",
        failure_class=FailureClass.VALIDATION_FAILED,
        fields=fields,
    )


def _error_message(code: str | None) -> str | None:
    if not code:
        return None
    return FILE_MESSAGES.get(code) or PAGE_MESSAGES.get(code) or FILE_MESSAGES["unreadable"]


def _batch_out(batch: ImportBatch) -> ImportBatchOut:
    return ImportBatchOut(
        id=batch.id,
        kind=batch.kind,  # type: ignore[arg-type]
        label=batch.label,
        default_source=batch.default_source,
        status=batch.status,  # type: ignore[arg-type]
        error_message=_error_message(batch.error_code),
        total_rows=batch.total_rows,
        created_count=batch.created_count,
        duplicate_count=batch.duplicate_count,
        rejected_count=batch.rejected_count,
        ignored_columns=list(batch.ignored_columns or []),
        created_at=batch.created_at,
        finished_at=batch.finished_at,
    )


def source_or_other(name: str | None) -> str:
    wanted = (name or "").strip().casefold()
    return next((s for s in SOURCE_NAMES if s.casefold() == wanted), "Other")


def manual(
    engine: Engine, *, user_id: uuid.UUID, payload: JobManualIn, ip_hash: str | None
) -> JobCreatedOut:
    try:
        draft = build_draft(
            title=payload.title,
            company=payload.company,
            location=payload.location,
            link=payload.source_url or "",
            source=payload.source_name,
            description=payload.description,
            default_source="Other",
        )
    except ValueError as problem:
        code = str(problem)
        raise _validation(
            {
                _FIELD_OF_PROBLEM.get(code, "description"): ROW_MESSAGES.get(
                    code, "Check this entry."
                )
            }
        ) from problem
    return job_service.create_from_draft(
        engine,
        user_id=user_id,
        draft=draft,
        acquisition=ACQUISITION_MANUAL,
        audit_action="job.entered",
        ip_hash=ip_hash,
    )


def start_file(
    engine: Engine,
    storage: FileStorage,
    *,
    user_id: uuid.UUID,
    data: bytes,
    filename: str,
    source_name: str | None,
    ip_hash: str | None,
) -> ImportBatchOut:
    try:
        kind = check_table_upload(data)
    except ImportFileError as problem:
        status = 413 if problem.code == "too_big" else 422
        raise ApiError(
            status,
            "PAYLOAD_TOO_LARGE" if status == 413 else "VALIDATION_FAILED",
            problem.message,
            failure_class=FailureClass.VALIDATION_FAILED,
        ) from problem
    key = new_import_key()
    try:
        storage.put(key, data)
    except StorageError as exc:
        raise ApiError(
            503, "STORAGE_UNAVAILABLE", "The file could not be saved. Try again.",
            failure_class=FailureClass.TRANSIENT,
        ) from exc  # fmt: skip
    try:
        with tenant_session(engine, user_id) as db:
            batch = create_file_batch(
                db,
                owner_id=user_id,
                kind=kind,
                label=filename[:200] or "spreadsheet",
                default_source=source_or_other(source_name),
                file_key=key,
            )
            out = _batch_out(batch)
    except Exception:
        with contextlib.suppress(StorageError):
            storage.delete(key)
        raise
    record_audit(
        engine, category="audit", action="import.file_started", actor_user_id=user_id,
        target_type="import_batch", target_id=str(out.id), ip_hash=ip_hash,
        metadata={"kind": kind, "bytes": len(data)},
    )  # fmt: skip
    return out


def start_url(
    engine: Engine, *, user_id: uuid.UUID, payload: ImportUrlIn, ip_hash: str | None
) -> ImportBatchOut:
    try:
        safe = check_import_url(payload.url)
    except UrlRefused as refused:
        raise _validation({"url": refused.message}) from refused
    with tenant_session(engine, user_id) as db:
        batch = create_url_batch(
            db,
            owner_id=user_id,
            url=safe.url,
            host=safe.host,
            default_source=source_or_other(payload.source_name),
        )
        out = _batch_out(batch)
    record_audit(
        engine, category="audit", action="import.url_started", actor_user_id=user_id,
        target_type="import_batch", target_id=str(out.id), ip_hash=ip_hash,
        metadata={"host": safe.host},
    )  # fmt: skip
    return out


def list_all(engine: Engine, user_id: uuid.UUID) -> list[ImportBatchOut]:
    with tenant_session(engine, user_id) as db:
        return [_batch_out(b) for b in list_batches(db, user_id)]


def detail(engine: Engine, user_id: uuid.UUID, batch_id: uuid.UUID) -> ImportDetailOut:
    with tenant_session(engine, user_id) as db:
        batch = get_batch(db, user_id, batch_id)
        if batch is None:
            raise job_service.not_found()
        base = _batch_out(batch)
        items = [
            ImportItemOut(
                row_number=i.row_number,
                status=i.status,  # type: ignore[arg-type]
                code=i.code,
                message=i.message,
                title=i.title,
                source_url=i.source_url,
                posting_id=i.posting_id,
            )
            for i in list_items(db, user_id, batch.id)
        ]
        return ImportDetailOut(**base.model_dump(), items=items)
