"""Make the PDF of a resume.

The browser preview and this PDF are drawn from the same HTML (pv_domain.resume_render), so layout
comes from one place. What this task adds is the durable part:

  - a task for a deleted resume, or an export that is no longer waiting, does nothing
  - the PDF is stored under a server-made key in private storage, then the row says ready
  - a PDF that cannot be made (the engine failed) is a RESULT: the export is marked failed with a
    plain message and the task completes. Retrying the same input would fail the same way
  - a storage hiccup is transient: raise TaskFailure and retry, visible on the last attempt

The resume text is never logged and never put in an error message.
"""

import contextlib
import time
import uuid
from typing import Any

from pv_domain.resume_doc import ResumeDocError, validate_document
from pv_domain.resume_render import render_html
from pv_domain.states import RunState, StepState
from pv_files import (
    FileStorage,
    RenderError,
    StorageError,
    build_storage,
    fonts_dir,
    html_to_pdf,
    new_export_key,
)
from pv_persistence.models import ResumeDocument, ResumeExport
from pv_persistence.runs import add_step, set_run_state
from pv_persistence.studio import fail_export, finish_export
from pv_persistence.tenancy import tenant_session
from pv_worker.contract import TaskContext, TaskFailure


def handle_render_resume(ctx: TaskContext) -> None:
    run_render(ctx, storage=build_storage(ctx.settings))


def _step(
    ctx: TaskContext, ordinal: int, name: str, state: StepState, started: float, **detail: int
) -> None:
    if ctx.run_id is None or ctx.owner_user_id is None:
        return
    with tenant_session(ctx.engine, ctx.owner_user_id) as db:
        add_step(
            db,
            run_id=ctx.run_id,
            owner_user_id=ctx.owner_user_id,
            step_name=name,
            ordinal=ordinal,
            state=state,
            duration_ms=round((time.perf_counter() - started) * 1000),
            detail=dict(detail),
        )


def _fail(ctx: TaskContext, owner: uuid.UUID, export_id: uuid.UUID, code: str) -> None:
    with tenant_session(ctx.engine, owner) as db:
        item = db.get(ResumeExport, export_id)
        if item is not None and item.owner_user_id == owner:
            fail_export(db, item, code)
        if ctx.run_id is not None:
            set_run_state(
                db,
                ctx.run_id,
                RunState.FAILED,
                can_retry=True,
                error_class="RESUME_EXPORT_FAILED",
                error_type="ResumeExport",
                error_message=code,
            )


def run_render(ctx: TaskContext, *, storage: FileStorage) -> None:
    owner = ctx.owner_user_id
    try:
        export_id = uuid.UUID(str(ctx.args.get("export_id")))
    except ValueError as exc:
        raise TaskFailure("Invalid export task arguments.", retryable=False) from exc
    if owner is None:
        raise TaskFailure("The export task has no owner.", retryable=False)

    started = time.perf_counter()
    content: dict[str, Any]
    with tenant_session(ctx.engine, owner) as db:
        item = db.get(ResumeExport, export_id)
        if (
            item is None
            or item.owner_user_id != owner
            or item.status not in ("queued", "rendering")
        ):
            return  # deleted or already finished
        document = db.get(ResumeDocument, item.document_id)
        if document is None:
            return
        item.status = "rendering"
        item.revision = document.revision  # the PDF shows exactly what was saved when it ran
        content = dict(document.content)
        if ctx.run_id is not None:
            set_run_state(db, ctx.run_id, RunState.RUNNING)
    _step(ctx, 1, "load_resume", StepState.SUCCEEDED, started)
    ctx.extend_lease()

    started = time.perf_counter()
    try:
        clean = validate_document(content)
        html = render_html(clean, font_base=fonts_dir().as_uri() + "/")
        pdf = html_to_pdf(html)
    except (ResumeDocError, RenderError):
        _step(ctx, 2, "render_pdf", StepState.FAILED, started)
        _fail(ctx, owner, export_id, "RENDER_FAILED")
        return
    _step(ctx, 2, "render_pdf", StepState.SUCCEEDED, started, pages=pdf.page_count,
          bytes=len(pdf.data))  # fmt: skip
    ctx.extend_lease()

    started = time.perf_counter()
    key = new_export_key()
    try:
        storage.put(key, pdf.data)
    except StorageError as exc:
        _step(ctx, 3, "store_pdf", StepState.FAILED, started)
        if ctx.attempt >= ctx.max_attempts:
            _fail(ctx, owner, export_id, "STORAGE_FAILED")
            return
        raise TaskFailure("The PDF could not be stored. Trying again.", retryable=True) from exc
    with tenant_session(ctx.engine, owner) as db:
        item = db.get(ResumeExport, export_id)
        if item is None or item.owner_user_id != owner:
            _discard(storage, key)  # the resume was deleted while the PDF was being made
            return
        finish_export(
            db, item, storage_key=key, size_bytes=len(pdf.data), page_count=pdf.page_count
        )
        if ctx.run_id is not None:
            set_run_state(db, ctx.run_id, RunState.SUCCEEDED)
    _step(ctx, 3, "store_pdf", StepState.SUCCEEDED, started)


def _discard(storage: FileStorage, key: str) -> None:
    with contextlib.suppress(StorageError):
        storage.delete(key)
