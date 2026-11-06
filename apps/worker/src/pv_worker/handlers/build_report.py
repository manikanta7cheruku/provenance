"""Build a report (CSV, Excel workbook or Word document) from a person's stored jobs.

The rules for what goes in a report, and how a cell is made safe, are in pv_domain.report. The three
file formats are written by pv_files from one Report model. What this task adds is the durable part:

  - a task for a deleted report, or one that is no longer waiting, does nothing
  - the report is built from the data stored when the task runs, with the filters saved on the
    row, so it holds exactly what the person asked for
  - the file is stored under a server-made key in private storage, then the row says ready
  - a report whose file cannot be written is a RESULT: the row is marked failed with a plain code
    and the task completes. Building the same input again would fail the same way. A database error
    while gathering is transient and the task retries
  - a storage hiccup is transient: raise TaskFailure and retry, visible on the last attempt

Job text, notes and evidence are never logged and never put in an error message.
"""

import contextlib
import time
import uuid

from pv_domain.report import build_report
from pv_domain.states import RunState, StepState
from pv_files import FileStorage, StorageError, build_storage, new_export_key, write_report
from pv_persistence.models import ReportExport
from pv_persistence.reports import fail_report, finish_report, load_report_input
from pv_persistence.runs import add_step, set_run_state
from pv_persistence.tenancy import tenant_session
from pv_worker.contract import TaskContext, TaskFailure


def handle_build_report(ctx: TaskContext) -> None:
    run_build(ctx, storage=build_storage(ctx.settings))


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


def _fail(ctx: TaskContext, owner: uuid.UUID, report_id: uuid.UUID, code: str) -> None:
    with tenant_session(ctx.engine, owner) as db:
        item = db.get(ReportExport, report_id)
        if item is not None and item.owner_user_id == owner:
            fail_report(db, item, code)
        if ctx.run_id is not None:
            set_run_state(
                db,
                ctx.run_id,
                RunState.FAILED,
                can_retry=True,
                error_class="REPORT_EXPORT_FAILED",
                error_type="ReportExport",
                error_message=code,
            )


def run_build(ctx: TaskContext, *, storage: FileStorage) -> None:
    owner = ctx.owner_user_id
    try:
        report_id = uuid.UUID(str(ctx.args.get("report_id")))
    except ValueError as exc:
        raise TaskFailure("Invalid report task arguments.", retryable=False) from exc
    if owner is None:
        raise TaskFailure("The report task has no owner.", retryable=False)

    started = time.perf_counter()
    with tenant_session(ctx.engine, owner) as db:
        item = db.get(ReportExport, report_id)
        if item is None or item.owner_user_id != owner or item.status not in ("queued", "building"):
            return  # deleted, or already finished
        item.status = "building"
        fmt = item.format
        params = dict(item.params)
        data = load_report_input(db, owner, params)
        if ctx.run_id is not None:
            set_run_state(db, ctx.run_id, RunState.RUNNING)
    _step(ctx, 1, "gather_jobs", StepState.SUCCEEDED, started, jobs=len(data.jobs))
    ctx.extend_lease()

    started = time.perf_counter()
    try:
        payload = write_report(build_report(data), fmt)
    except Exception:  # noqa: BLE001 - the file could not be written: a result, not a crash
        _step(ctx, 2, "write_file", StepState.FAILED, started)
        _fail(ctx, owner, report_id, "BUILD_FAILED")
        return
    _step(ctx, 2, "write_file", StepState.SUCCEEDED, started, bytes=len(payload))
    ctx.extend_lease()

    started = time.perf_counter()
    key = new_export_key()
    try:
        storage.put(key, payload)
    except StorageError as exc:
        _step(ctx, 3, "store_file", StepState.FAILED, started)
        if ctx.attempt >= ctx.max_attempts:
            _fail(ctx, owner, report_id, "STORAGE_FAILED")
            return
        raise TaskFailure("The report could not be stored. Trying again.", retryable=True) from exc
    with tenant_session(ctx.engine, owner) as db:
        item = db.get(ReportExport, report_id)
        if item is None or item.owner_user_id != owner:
            _discard(storage, key)  # the report was deleted while it was being built
            return
        finish_report(db, item, storage_key=key, size_bytes=len(payload), row_count=len(data.jobs))
        if ctx.run_id is not None:
            set_run_state(db, ctx.run_id, RunState.SUCCEEDED)
    _step(ctx, 3, "store_file", StepState.SUCCEEDED, started)


def _discard(storage: FileStorage, key: str) -> None:
    with contextlib.suppress(StorageError):
        storage.delete(key)
