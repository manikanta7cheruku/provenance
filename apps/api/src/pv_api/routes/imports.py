"""Bringing jobs in from a spreadsheet or a web address, and the report of each import.

A spreadsheet is sent as the raw request body (as a resume is: no multipart parser, the type is
decided from the first bytes, never from the name or the Content-Type), with the original name in
X-Filename and the source label in X-Source-Name, both percent-encoded.

This router never requests a web address. It checks the address and queues a task. The worker reads
the page with its own limits, so a person cannot make the API server talk to anything.
"""

import uuid
from typing import Annotated
from urllib.parse import unquote

from fastapi import APIRouter, Header, Request
from starlette.concurrency import run_in_threadpool

from pv_api.deps import CurrentUser, EngineDep, LimiterDep, SettingsDep, WriterUser, ip_hash_of
from pv_api.errors import ApiError
from pv_api.schemas import ImportBatchOut, ImportDetailOut, ImportUrlIn
from pv_api.services import import_service
from pv_domain.failures import FailureClass
from pv_domain.job_import import MAX_IMPORT_BYTES
from pv_domain.resume import safe_display_filename
from pv_files import FileStorage

router = APIRouter(prefix="/imports", tags=["imports"])


def get_storage(request: Request) -> FileStorage:
    storage: FileStorage = request.app.state.storage
    return storage


async def _read_capped(request: Request) -> bytes:
    """Read the body but stop as soon as it passes the limit, whatever Content-Length said."""
    chunks: list[bytes] = []
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > MAX_IMPORT_BYTES:
            raise ApiError(
                413,
                "PAYLOAD_TOO_LARGE",
                "This file is over the 5 MB limit. Split it or remove columns you do not need.",
                failure_class=FailureClass.VALIDATION_FAILED,
            )
        chunks.append(chunk)
    return b"".join(chunks)


@router.get("", response_model=list[ImportBatchOut])
def list_imports(auth: CurrentUser, engine: EngineDep) -> list[ImportBatchOut]:
    return import_service.list_all(engine, auth.user_id)


@router.get("/{batch_id}", response_model=ImportDetailOut)
def get_import(batch_id: uuid.UUID, auth: CurrentUser, engine: EngineDep) -> ImportDetailOut:
    return import_service.detail(engine, auth.user_id, batch_id)


@router.post("/file", response_model=ImportBatchOut, status_code=202)
async def upload_file(
    request: Request,
    auth: WriterUser,
    engine: EngineDep,
    settings: SettingsDep,
    limiter: LimiterDep,
    x_filename: Annotated[str | None, Header()] = None,
    x_source_name: Annotated[str | None, Header()] = None,
) -> ImportBatchOut:
    limiter.check("import_file_user", str(auth.user_id))
    data = await _read_capped(request)
    name = safe_display_filename(unquote(x_filename)) if x_filename else "spreadsheet"
    return await run_in_threadpool(
        import_service.start_file,
        engine,
        get_storage(request),
        user_id=auth.user_id,
        data=data,
        filename=name,
        source_name=unquote(x_source_name) if x_source_name else None,
        ip_hash=ip_hash_of(request, settings),
    )


@router.post("/url", response_model=ImportBatchOut, status_code=202)
def import_url(
    payload: ImportUrlIn,
    request: Request,
    auth: WriterUser,
    engine: EngineDep,
    settings: SettingsDep,
    limiter: LimiterDep,
) -> ImportBatchOut:
    limiter.check("import_url_user", str(auth.user_id))
    return import_service.start_url(
        engine,
        user_id=auth.user_id,
        payload=payload,
        ip_hash=ip_hash_of(request, settings),
        settings=settings,
    )
