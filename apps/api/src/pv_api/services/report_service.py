"""Reports: ask for one, watch it, download it, delete it.

A report is built by the worker from stored data (pv_domain.report). Here the person asks for one
with the filters of the list they are looking at, sees its state, and downloads it. Everything runs
in one tenant session (Row Level Security) and filters by the signed-in owner. A report that belongs
to someone else, or has expired, is "not found", never "forbidden".

Exporting is never counted against a plan (reading and exporting what you have are free, ADR-0051).
It is limited instead by how often a report can be asked for, how many can be building at once, and
how many are kept (they also expire).
"""

import contextlib
import uuid
from datetime import UTC, datetime

from sqlalchemy.engine import Engine

from pv_api.errors import ApiError
from pv_api.schemas import ReportIn, ReportOut
from pv_api.services.job_service import not_found
from pv_config import Settings
from pv_domain.failures import FailureClass
from pv_domain.pipeline import clean_query, query_to_dict
from pv_domain.report import (
    FORMAT_LABELS,
    KEEP_EXPORTS,
    MAX_ACTIVE_EXPORTS,
    MEDIA_TYPES,
    describe_query,
    export_filename,
)
from pv_files import FileStorage, StorageError
from pv_persistence.audit import record_audit
from pv_persistence.models import ReportExport
from pv_persistence.reports import (
    count_active,
    expire_reports,
    get_report,
    list_reports,
    remove_report,
    start_report,
)
from pv_persistence.tenancy import tenant_session

_UI = {"queued": "preparing", "building": "preparing", "ready": "ready", "failed": "failed"}


def _out(item: ReportExport) -> ReportOut:
    query = clean_query(item.params.get("query", {}) if isinstance(item.params, dict) else {})
    ready = item.status == "ready"
    return ReportOut(
        id=item.id,
        format=item.format,  # type: ignore[arg-type]
        format_label=FORMAT_LABELS.get(item.format, item.format),
        ui_state=_UI[item.status],  # type: ignore[arg-type]
        size_bytes=item.size_bytes,
        job_count=item.row_count,
        criteria=list(describe_query(query)),
        query=query_to_dict(query),
        include_quotes=bool(item.params.get("include_quotes")),
        error_message=(
            "The report could not be made. Your jobs are safe. Try again."
            if item.status == "failed"
            else None
        ),
        created_at=item.created_at,
        expires_at=item.expires_at,
        download_name=(
            export_filename(item.format, item.finished_at or item.created_at) if ready else None
        ),
    )


def _delete_files(storage: FileStorage, keys: list[str]) -> None:
    for key in keys:
        with contextlib.suppress(StorageError):
            storage.delete(key)


def reports(engine: Engine, storage: FileStorage, user_id: uuid.UUID) -> list[ReportOut]:
    with tenant_session(engine, user_id) as db:
        keys = expire_reports(db, user_id, KEEP_EXPORTS)
        out = [_out(r) for r in list_reports(db, user_id)]
    _delete_files(storage, keys)
    return out


def create(
    engine: Engine,
    settings: Settings,
    storage: FileStorage,
    user_id: uuid.UUID,
    payload: ReportIn,
    ip_hash: str | None,
) -> ReportOut:
    query = clean_query(payload.query)
    with tenant_session(engine, user_id) as db:
        keys = expire_reports(db, user_id, KEEP_EXPORTS - 1)
        if count_active(db, user_id) >= MAX_ACTIVE_EXPORTS:
            raise ApiError(
                409,
                "REPORT_IN_PROGRESS",
                "Your other reports are still being made. Wait for one to finish, then ask again.",
                failure_class=FailureClass.USER_ACTION_REQUIRED,
            )
        item = start_report(
            db,
            user_id,
            payload.format,
            query,
            include_quotes=payload.include_quotes,
            retention_days=settings.report_retention_days,
        )
        out = _out(item)
    _delete_files(storage, keys)
    record_audit(
        engine,
        category="audit",
        action="report.requested",
        actor_user_id=user_id,
        target_type="report_export",
        target_id=str(out.id),
        ip_hash=ip_hash,
    )
    return out


def one(engine: Engine, user_id: uuid.UUID, report_id: uuid.UUID) -> ReportOut:
    with tenant_session(engine, user_id) as db:
        item = get_report(db, user_id, report_id)
        if item is None or item.expires_at <= datetime.now(UTC):
            raise not_found()
        return _out(item)


def download(
    engine: Engine, storage: FileStorage, user_id: uuid.UUID, report_id: uuid.UUID
) -> tuple[bytes, str, str]:
    """The file, its name and its media type. Owner only, only while ready and unexpired."""
    with tenant_session(engine, user_id) as db:
        item = get_report(db, user_id, report_id)
        if (
            item is None
            or item.status != "ready"
            or not item.storage_key
            or item.expires_at <= datetime.now(UTC)
        ):
            raise not_found()
        key = item.storage_key
        fmt = item.format
        when = item.finished_at or item.created_at
    try:
        data = storage.get(key)
    except StorageError as exc:
        raise not_found() from exc
    return data, export_filename(fmt, when), MEDIA_TYPES[fmt]


def delete(
    engine: Engine,
    storage: FileStorage,
    user_id: uuid.UUID,
    report_id: uuid.UUID,
    ip_hash: str | None,
) -> None:
    with tenant_session(engine, user_id) as db:
        item = get_report(db, user_id, report_id)
        if item is None:
            raise not_found()
        key = remove_report(db, user_id, item)
    if key:
        _delete_files(storage, [key])
    record_audit(
        engine,
        category="audit",
        action="report.deleted",
        actor_user_id=user_id,
        target_type="report_export",
        target_id=str(report_id),
        ip_hash=ip_hash,
    )
