"""Read an uploaded spreadsheet and turn each row into a private job posting, with a report.

Idempotent, because the queue delivers at least once:
  - a task for a batch that is gone, or already finished, does nothing
  - all rows of one file are saved in one transaction, so a retry never finds half a file
  - a file that cannot be used (unreadable, no description column, too many rows) is a RESULT: the
    batch is marked failed with a short code the person can act on, and the task completes
  - only storage trouble raises TaskFailure and is retried

The file is deleted from private storage when the batch ends, whatever the outcome. No cell text is
logged or put in an error message, and the report holds no posting text.
"""

import contextlib
import uuid

from pv_domain.job_import import (
    ACQUISITION_CSV,
    ACQUISITION_XLSX,
    BatchStatus,
    ImportFileError,
    ItemStatus,
    plan_rows,
)
from pv_files import FileStorage, StorageError, build_storage, read_table
from pv_persistence.imports import finish_batch, get_batch, store_draft
from pv_persistence.models import ImportItem
from pv_persistence.tenancy import tenant_session
from pv_worker.contract import TaskContext, TaskFailure

_ALREADY_SAVED = "You already have this posting. Nothing new was made."


def handle_import_file(ctx: TaskContext) -> None:
    run_import_file(ctx, storage=build_storage(ctx.settings))


def _fail(ctx: TaskContext, owner: uuid.UUID, batch_id: uuid.UUID, code: str) -> str | None:
    """Close the batch as failed. Returns the file key so the caller can delete the file."""
    with tenant_session(ctx.engine, owner) as db:
        batch = get_batch(db, owner, batch_id)
        if batch is None:
            return None
        key = batch.file_key
        finish_batch(db, batch, status=BatchStatus.FAILED, error_code=code)
        return key


def run_import_file(ctx: TaskContext, *, storage: FileStorage) -> None:
    owner = ctx.owner_user_id
    if owner is None:
        raise TaskFailure("The task has no owner.", retryable=False)
    batch_id = uuid.UUID(str(ctx.args["batch_id"]))
    with tenant_session(ctx.engine, owner) as db:
        batch = get_batch(db, owner, batch_id)
        if batch is None or batch.status not in (BatchStatus.QUEUED, BatchStatus.RUNNING):
            return
        batch.status = BatchStatus.RUNNING.value
        key, default_source = batch.file_key, batch.default_source
    if key is None:
        _fail(ctx, owner, batch_id, "unreadable")
        return

    try:
        data = storage.get(key)
    except StorageError as exc:
        if ctx.attempt < ctx.max_attempts:
            raise TaskFailure("The uploaded file could not be read from storage.") from exc
        _fail(ctx, owner, batch_id, "unreadable")
        return

    try:
        kind, table = read_table(data)
        plan = plan_rows(table, default_source=default_source)
    except ImportFileError as file_problem:
        _fail(ctx, owner, batch_id, file_problem.code)
        _delete_file(storage, key)
        return

    acquisition = ACQUISITION_XLSX if kind == "xlsx" else ACQUISITION_CSV
    with tenant_session(ctx.engine, owner) as db:
        batch = get_batch(db, owner, batch_id)
        if batch is None or batch.status != BatchStatus.RUNNING:
            return
        for row in plan.rows:
            item = ImportItem(
                batch_id=batch.id, owner_user_id=owner, row_number=row.row_number, title=row.title
            )
            if row.draft is None:
                reason = row.problem
                item.status = ItemStatus.REJECTED.value
                item.code = reason.code if reason else "rejected"
                item.message = reason.message if reason else "This row could not be used."
            else:
                posting, created = store_draft(
                    db, owner_id=owner, draft=row.draft, acquisition=acquisition
                )
                item.posting_id = posting.id
                if created:
                    item.status = ItemStatus.CREATED.value
                else:
                    item.status = ItemStatus.DUPLICATE.value
                    item.code = "already_saved"
                    item.message = _ALREADY_SAVED
            db.add(item)
        db.flush()
        batch.ignored_columns = list(plan.ignored_columns)
        finish_batch(db, batch, status=BatchStatus.DONE)
    _delete_file(storage, key)


def _delete_file(storage: FileStorage, key: str) -> None:
    # a leftover file is harmless: its key is cleared and nothing refers to it
    with contextlib.suppress(StorageError):
        storage.delete(key)
