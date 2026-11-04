"""Read one web page a person asked for and turn it into a private job posting.

The only request goes through pv_worker.safe_fetch, which refuses private networks, checks every
address it connects to and follows no more than a few redirects. This handler decides what happens
with the answer:
  - a page that cannot be read is a RESULT: the report row says why, in words, and the task
    completes. Trouble that may pass (the site is busy, the network failed) is retried and becomes a
    visible result on the last attempt
  - the page is read for a job (structured data first, then its visible text). A page with no
    usable text is rejected with advice to paste the description instead
  - the same text saved twice is reported as already saved

The page text is data: it is stored as the posting, read like any pasted posting, and never obeyed.
No page text is logged or put in an error message.
"""

import uuid
from collections.abc import Callable

from pv_domain.job_import import (
    ACQUISITION_URL,
    PAGE_MESSAGES,
    ROW_MESSAGES,
    BatchStatus,
    ItemStatus,
    build_draft,
)
from pv_domain.job_page import extract_job_page
from pv_persistence.imports import finish_batch, get_batch, list_items, store_draft
from pv_persistence.models import ImportItem
from pv_persistence.tenancy import tenant_session
from pv_worker.contract import TaskContext, TaskFailure
from pv_worker.safe_fetch import PageFetcher, PageFetchError, SafePageFetcher

FetcherFactory = Callable[[], PageFetcher]


def handle_import_url(ctx: TaskContext) -> None:
    fetcher = SafePageFetcher()
    try:
        run_import_url(ctx, fetcher=fetcher)
    finally:
        fetcher.close()


def _reject(item: ImportItem, code: str, message: str) -> None:
    item.status = ItemStatus.REJECTED.value
    item.code = code[:40]
    item.message = message[:300]


def run_import_url(ctx: TaskContext, *, fetcher: PageFetcher) -> None:
    owner = ctx.owner_user_id
    if owner is None:
        raise TaskFailure("The task has no owner.", retryable=False)
    batch_id = uuid.UUID(str(ctx.args["batch_id"]))
    with tenant_session(ctx.engine, owner) as db:
        batch = get_batch(db, owner, batch_id)
        if batch is None or batch.status not in (BatchStatus.QUEUED, BatchStatus.RUNNING):
            return
        items = list_items(db, owner, batch_id)
        if not items:
            finish_batch(db, batch, status=BatchStatus.FAILED, error_code="unreadable")
            return
        batch.status = BatchStatus.RUNNING.value
        url, default_source = items[0].source_url or "", batch.default_source

    outcome: tuple[str, str] | None = None  # a rejection: (code, message)
    draft = None
    try:
        page = fetcher.fetch_page(url)
    except PageFetchError as error:
        if error.retryable and ctx.attempt < ctx.max_attempts:
            raise TaskFailure(f"The page could not be read ({error.code}).") from error
        outcome = (error.code, PAGE_MESSAGES.get(error.code, error.message))
    else:
        job = extract_job_page(page.html)
        if job is None:
            outcome = ("no_text", PAGE_MESSAGES["no_text"])
        else:
            try:
                draft = build_draft(
                    title=job.title or "",
                    company=job.company or "",
                    location=job.location or "",
                    link=page.url,
                    source=None,
                    description=job.text,
                    default_source=default_source,
                )
            except ValueError as problem:
                code = str(problem)
                if code in ("too_short", "no_description"):
                    outcome = ("no_text", PAGE_MESSAGES["no_text"])
                else:
                    outcome = (code, ROW_MESSAGES.get(code, PAGE_MESSAGES["no_text"]))

    with tenant_session(ctx.engine, owner) as db:
        batch = get_batch(db, owner, batch_id)
        if batch is None or batch.status != BatchStatus.RUNNING:
            return
        item = list_items(db, owner, batch_id)[0]
        if draft is not None:
            item.title = draft.title
            posting, created = store_draft(
                db, owner_id=owner, draft=draft, acquisition=ACQUISITION_URL
            )
            item.posting_id = posting.id
            if created:
                item.status = ItemStatus.CREATED.value
            else:
                item.status = ItemStatus.DUPLICATE.value
                item.code = "already_saved"
                item.message = ROW_MESSAGES["already_saved"]
        elif outcome is not None:
            _reject(item, *outcome)
        db.flush()
        finish_batch(db, batch, status=BatchStatus.DONE)
