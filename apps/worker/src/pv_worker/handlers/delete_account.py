"""Delete an account: every stored file first, then every row.

The order matters. The files are listed from the database, so they must be removed before the rows
that name them are gone. If the task stops half way it is retried and carries on: a file that is
already gone is fine, and a user row that is already gone means the work is done.

  1. a task for a person who is already gone just finishes the record
  2. list the person's stored files (resumes, pictures, PDFs, reports, uploaded spreadsheets)
  3. remove each file. A storage error is transient: retry. Only on the last attempt is the
     deletion marked failed, with a plain code, and the person's data is then NOT removed
  4. remove the stray rows the foreign keys cannot reach (counters, a bound invite, a queued email)
  5. delete the user row. Every table that holds the person's data cascades from it
  6. complete the minimal record (no person in it): how many files and stray rows

Nothing about the person is logged, put in an error, or kept in the record.
"""

import uuid

from sqlalchemy.orm import Session

from pv_files import FileStorage, StorageError, build_storage
from pv_persistence import account as store
from pv_persistence.models import User
from pv_persistence.tenancy import tenant_session
from pv_worker.contract import TaskContext, TaskFailure


def handle_delete_account(ctx: TaskContext) -> None:
    run_delete(ctx, storage=build_storage(ctx.settings))


def run_delete(ctx: TaskContext, *, storage: FileStorage) -> None:
    try:
        user_id = uuid.UUID(str(ctx.args.get("user_id")))
        deletion_id = uuid.UUID(str(ctx.args.get("deletion_id")))
    except ValueError as exc:
        raise TaskFailure("Invalid deletion task arguments.", retryable=False) from exc

    with Session(ctx.engine, expire_on_commit=False) as db, db.begin():
        user = db.get(User, user_id)
        email = user.email if user is not None else None
        store.mark_running(db, deletion_id)
    if user is None:
        with Session(ctx.engine) as db, db.begin():
            store.finish_deletion(db, deletion_id, files=0, strays=0)
        return

    with tenant_session(ctx.engine, user_id) as tdb:
        keys = store.storage_keys(tdb)
    removed = 0
    for key in keys:
        try:
            if storage.exists(key):
                storage.delete(key)
                removed += 1
        except StorageError as exc:
            if ctx.attempt >= ctx.max_attempts:
                with Session(ctx.engine) as db, db.begin():
                    store.fail_deletion(db, deletion_id, "STORAGE_FAILED")
                return
            raise TaskFailure(
                "A stored file could not be removed. Trying again.", retryable=True
            ) from exc
        ctx.extend_lease()

    with Session(ctx.engine) as db, db.begin():
        strays = store.purge_strays(db, user_id, email or "")
        store.remove_user(db, user_id)
        store.finish_deletion(db, deletion_id, files=removed, strays=strays)


__all__ = ["handle_delete_account", "run_delete"]
