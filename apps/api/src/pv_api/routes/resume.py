"""The signed-in person's resume. One per user; all routes are scoped to that user.

Upload sends the file as the raw request body (Content-Type is ignored: the type is decided
from the first bytes) with the original name in the X-Filename header, percent-encoded.
No multipart parser is involved, which keeps the attack surface small.
"""

from typing import Annotated
from urllib.parse import quote, unquote

from fastapi import APIRouter, Header, Request, Response
from starlette.concurrency import run_in_threadpool

from pv_api.deps import CurrentUser, EngineDep, LimiterDep, SettingsDep, WriterUser, ip_hash_of
from pv_api.errors import ApiError
from pv_api.schemas import ResumeOut
from pv_api.services import resume_service
from pv_domain.failures import FailureClass
from pv_domain.resume import MAX_UPLOAD_BYTES, MEDIA_TYPES, safe_display_filename
from pv_files import FileStorage

router = APIRouter(prefix="/resume", tags=["resume"])


def get_storage(request: Request) -> FileStorage:
    storage: FileStorage = request.app.state.storage
    return storage


async def _read_capped(request: Request) -> bytes:
    """Read the body but stop as soon as it passes the limit, whatever Content-Length said."""
    chunks: list[bytes] = []
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > MAX_UPLOAD_BYTES:
            raise ApiError(
                413,
                "PAYLOAD_TOO_LARGE",
                "This file is over the 5 MB limit. Choose a smaller file.",
                failure_class=FailureClass.VALIDATION_FAILED,
            )
        chunks.append(chunk)
    return b"".join(chunks)


@router.get("", response_model=ResumeOut | None)
def get_current(auth: CurrentUser, engine: EngineDep) -> ResumeOut | None:
    return resume_service.current(engine, auth.user_id)


@router.post("", response_model=ResumeOut, status_code=201)
async def upload(
    request: Request,
    auth: WriterUser,
    engine: EngineDep,
    settings: SettingsDep,
    limiter: LimiterDep,
    x_filename: Annotated[str | None, Header()] = None,
) -> ResumeOut:
    limiter.check("resume_upload_user", str(auth.user_id))
    data = await _read_capped(request)
    name = safe_display_filename(unquote(x_filename)) if x_filename else "resume"
    return await run_in_threadpool(
        resume_service.upload,
        engine,
        get_storage(request),
        user_id=auth.user_id,
        data=data,
        filename=name,
        ip_hash=ip_hash_of(request, settings),
    )


@router.get("/file")
def download(request: Request, auth: CurrentUser, engine: EngineDep) -> Response:
    data, kind, name = resume_service.download(engine, get_storage(request), auth.user_id)
    ascii_name = name.encode("ascii", "ignore").decode() or "resume"
    disposition = f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(name)}"
    return Response(
        content=data,
        media_type=MEDIA_TYPES[kind],
        headers={"Content-Disposition": disposition, "Cache-Control": "private, no-store"},
    )


@router.delete("", status_code=204)
def delete(request: Request, auth: WriterUser, engine: EngineDep, settings: SettingsDep) -> None:
    resume_service.delete(
        engine, get_storage(request), user_id=auth.user_id, ip_hash=ip_hash_of(request, settings)
    )


@router.post("/reparse", response_model=ResumeOut)
def reparse(auth: WriterUser, engine: EngineDep, limiter: LimiterDep) -> ResumeOut:
    limiter.check("resume_reparse_user", str(auth.user_id))
    return resume_service.reparse(engine, user_id=auth.user_id)


@router.post("/confirm", response_model=ResumeOut)
def confirm(auth: WriterUser, engine: EngineDep) -> ResumeOut:
    return resume_service.confirm(engine, user_id=auth.user_id)
