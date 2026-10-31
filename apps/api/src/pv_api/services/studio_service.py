"""The resume studio: create, save, preview, restore, export and delete a resume.

Same rules as the other services: one tenant session per call (Row Level Security), every query
filtered by the signed-in owner, and "not found" for anything that belongs to someone else.

The document is validated on every save and every preview (pv_domain.resume_doc), so what is stored
and rendered is always a clean copy, never what the browser sent.
"""

import contextlib
import re
import uuid
from typing import Any

from sqlalchemy.engine import Engine

from pv_api.errors import ApiError
from pv_api.schemas import (
    ExportOut,
    ResumeCreate,
    ResumeDocumentOut,
    ResumeDocumentSummaryOut,
    ResumeSave,
    VersionOut,
)
from pv_api.services.job_service import not_found
from pv_config import Settings
from pv_domain.failures import FailureClass
from pv_domain.resume_doc import (
    ResumeDocError,
    blank_document,
    document_from_entries,
    validate_document,
)
from pv_domain.resume_render import render_html
from pv_files import FileStorage, StorageError
from pv_persistence.audit import record_audit
from pv_persistence.models import ResumeDocument, ResumeExport
from pv_persistence.resumes import list_entries
from pv_persistence.studio import (
    RevisionConflict,
    create_document,
    delete_document,
    get_document,
    get_export,
    get_version,
    list_documents,
    list_exports,
    list_versions,
    prune_exports,
    save_document,
    start_export,
)
from pv_persistence.tenancy import tenant_session

FONT_URL = "/api/v1/studio/fonts/"
_BAD_FILENAME = re.compile(r"[^A-Za-z0-9 _.-]+")


def _validation_error(exc: ResumeDocError) -> ApiError:
    return ApiError(
        422,
        "VALIDATION_FAILED",
        "Some details need fixing.",
        failure_class=FailureClass.VALIDATION_FAILED,
        fields=exc.problems,
    )


def _summary(doc: ResumeDocument) -> ResumeDocumentSummaryOut:
    return ResumeDocumentSummaryOut(
        id=doc.id,
        title=doc.title,
        revision=doc.revision,
        template=doc.content.get("style", {}).get("template", "classic"),
        updated_at=doc.updated_at,
    )


def _out(doc: ResumeDocument) -> ResumeDocumentOut:
    return ResumeDocumentOut(**_summary(doc).model_dump(), content=doc.content)


def _export_out(e: ResumeExport) -> ExportOut:
    ui = {"queued": "preparing", "rendering": "preparing", "ready": "ready", "failed": "failed"}
    return ExportOut(
        id=e.id,
        revision=e.revision,
        ui_state=ui[e.status],  # type: ignore[arg-type]
        size_bytes=e.size_bytes,
        page_count=e.page_count,
        error_message=(
            "The PDF could not be made. Your resume is safe. Try again."
            if e.status == "failed"
            else None
        ),
        created_at=e.created_at,
    )


def list_resumes(engine: Engine, user_id: uuid.UUID) -> list[ResumeDocumentSummaryOut]:
    with tenant_session(engine, user_id) as db:
        return [_summary(d) for d in list_documents(db, user_id)]


def create(
    engine: Engine,
    settings: Settings,
    user_id: uuid.UUID,
    payload: ResumeCreate,
    ip_hash: str | None,
) -> ResumeDocumentOut:
    with tenant_session(engine, user_id) as db:
        if len(list_documents(db, user_id)) >= settings.studio_max_resumes:
            raise ApiError(
                409,
                "RESUME_LIMIT",
                "The free plan keeps one resume. Delete it first to start another.",
                failure_class=FailureClass.USER_ACTION_REQUIRED,
            )
        if payload.start == "profile":
            entries = [(e.entry_type, e.data) for e in list_entries(db, user_id)]
            content = document_from_entries(entries, template=payload.template)
        else:
            content = blank_document(payload.template)
        doc = create_document(db, user_id, payload.title or "My resume", content)
        out = _out(doc)
    record_audit(
        engine, category="audit", action="resume_doc.created", actor_user_id=user_id,
        target_type="resume_document", target_id=str(out.id), ip_hash=ip_hash,
        metadata={"start": payload.start, "template": payload.template},
    )  # fmt: skip
    return out


def get(engine: Engine, user_id: uuid.UUID, doc_id: uuid.UUID) -> ResumeDocumentOut:
    with tenant_session(engine, user_id) as db:
        doc = get_document(db, user_id, doc_id)
        if doc is None:
            raise not_found()
        return _out(doc)


def save(
    engine: Engine, user_id: uuid.UUID, doc_id: uuid.UUID, payload: ResumeSave
) -> ResumeDocumentSummaryOut:
    try:
        content = validate_document(payload.content)
    except ResumeDocError as exc:
        raise _validation_error(exc) from exc
    with tenant_session(engine, user_id) as db:
        doc = get_document(db, user_id, doc_id)
        if doc is None:
            raise not_found()
        try:
            saved = save_document(
                db,
                doc,
                content,
                expected_revision=payload.revision,
                title=payload.title,
                checkpoint=payload.checkpoint,
            )
        except RevisionConflict as conflict:
            raise ApiError(
                409,
                "REVISION_CONFLICT",
                "This resume was changed somewhere else. Reload to see the latest version.",
                failure_class=FailureClass.USER_ACTION_REQUIRED,
            ) from conflict
        return _summary(saved)


def preview(engine: Engine, user_id: uuid.UUID, doc_id: uuid.UUID, content: dict[str, Any]) -> str:
    """The HTML of unsaved content, for the live preview. Nothing is stored."""
    try:
        clean = validate_document(content)
    except ResumeDocError as exc:
        raise _validation_error(exc) from exc
    with tenant_session(engine, user_id) as db:
        if get_document(db, user_id, doc_id) is None:
            raise not_found()
    return render_html(clean, font_base=FONT_URL, preview=True)


def versions(engine: Engine, user_id: uuid.UUID, doc_id: uuid.UUID) -> list[VersionOut]:
    with tenant_session(engine, user_id) as db:
        if get_document(db, user_id, doc_id) is None:
            raise not_found()
        return [
            VersionOut(id=v.id, revision=v.revision, created_at=v.created_at)
            for v in list_versions(db, user_id, doc_id)
        ]


def restore(
    engine: Engine, user_id: uuid.UUID, doc_id: uuid.UUID, version_id: uuid.UUID, revision: int
) -> ResumeDocumentOut:
    """Make an earlier version current. The present content is kept as a version first."""
    with tenant_session(engine, user_id) as db:
        doc = get_document(db, user_id, doc_id)
        version = get_version(db, user_id, doc_id, version_id)
        if doc is None or version is None:
            raise not_found()
        try:
            saved = save_document(
                db, doc, dict(version.content), expected_revision=revision, checkpoint=True
            )
        except RevisionConflict as conflict:
            raise ApiError(
                409,
                "REVISION_CONFLICT",
                "This resume was changed somewhere else. Reload to see the latest version.",
                failure_class=FailureClass.USER_ACTION_REQUIRED,
            ) from conflict
        return _out(saved)


def remove(
    engine: Engine,
    storage: FileStorage,
    user_id: uuid.UUID,
    doc_id: uuid.UUID,
    ip_hash: str | None,
) -> None:
    with tenant_session(engine, user_id) as db:
        doc = get_document(db, user_id, doc_id)
        if doc is None:
            raise not_found()
        keys = delete_document(db, user_id, doc)
    for key in keys:
        with contextlib.suppress(StorageError):
            storage.delete(key)
    record_audit(
        engine, category="audit", action="resume_doc.deleted", actor_user_id=user_id,
        target_type="resume_document", target_id=str(doc_id), ip_hash=ip_hash,
    )  # fmt: skip


def exports(engine: Engine, user_id: uuid.UUID, doc_id: uuid.UUID) -> list[ExportOut]:
    with tenant_session(engine, user_id) as db:
        if get_document(db, user_id, doc_id) is None:
            raise not_found()
        return [_export_out(e) for e in list_exports(db, user_id, doc_id)]


def export(
    engine: Engine,
    settings: Settings,
    storage: FileStorage,
    user_id: uuid.UUID,
    doc_id: uuid.UUID,
    ip_hash: str | None,
) -> ExportOut:
    with tenant_session(engine, user_id) as db:
        doc = get_document(db, user_id, doc_id)
        if doc is None:
            raise not_found()
        if any(e.status in ("queued", "rendering") for e in list_exports(db, user_id, doc_id)):
            raise ApiError(
                409,
                "EXPORT_IN_PROGRESS",
                "A PDF is already being made. It will appear here in a moment.",
                failure_class=FailureClass.USER_ACTION_REQUIRED,
            )
        created = start_export(db, doc)
        removed = prune_exports(db, user_id, doc_id, settings.studio_max_exports)
        out = _export_out(created)
    for key in removed:
        with contextlib.suppress(StorageError):
            storage.delete(key)
    record_audit(
        engine, category="audit", action="resume_doc.export_started", actor_user_id=user_id,
        target_type="resume_document", target_id=str(doc_id), ip_hash=ip_hash,
    )  # fmt: skip
    return out


def download(
    engine: Engine, storage: FileStorage, user_id: uuid.UUID, export_id: uuid.UUID
) -> tuple[bytes, str]:
    with tenant_session(engine, user_id) as db:
        item = get_export(db, user_id, export_id)
        if item is None or item.status != "ready" or not item.storage_key:
            raise not_found()
        doc = get_document(db, user_id, item.document_id)
        key = item.storage_key
        name = doc.content.get("header", {}).get("name", "") if doc else ""
    try:
        data = storage.get(key)
    except StorageError as exc:
        raise not_found() from exc
    base = _BAD_FILENAME.sub("", name).strip() or "Resume"
    return data, f"{base} Resume.pdf" if base != "Resume" else "Resume.pdf"
