"""Pictures for the resume studio. Every route is scoped to the signed-in user.

An upload is sent as the raw request body, as a resume is: no multipart parser, the type is decided
from the first bytes and never from the name or the Content-Type, and the original name travels
percent-encoded in X-Filename. The file is served only to its owner, with a type the server chose.
"""

import uuid
from typing import Annotated
from urllib.parse import unquote

from fastapi import APIRouter, Header, Request, Response
from starlette.concurrency import run_in_threadpool

from pv_api.deps import CurrentUser, EngineDep, LimiterDep, SettingsDep, WriterUser, ip_hash_of
from pv_api.errors import ApiError
from pv_api.schemas import ImageOut, ImagesOut
from pv_api.services import image_service
from pv_domain.failures import FailureClass
from pv_domain.resume_images import IMAGE_MESSAGES, MAX_UPLOAD_BYTES, ImageErrorCode
from pv_files import FileStorage

router = APIRouter(prefix="/studio/images", tags=["studio"])


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
                IMAGE_MESSAGES[ImageErrorCode.TOO_BIG_FILE],
                failure_class=FailureClass.VALIDATION_FAILED,
            )
        chunks.append(chunk)
    return b"".join(chunks)


@router.get("", response_model=ImagesOut)
def list_images(auth: CurrentUser, engine: EngineDep) -> ImagesOut:
    return image_service.list_all(engine, auth.user_id)


@router.post("", response_model=ImageOut, status_code=201)
async def upload(
    request: Request,
    auth: WriterUser,
    engine: EngineDep,
    settings: SettingsDep,
    limiter: LimiterDep,
    x_filename: Annotated[str | None, Header()] = None,
) -> ImageOut:
    limiter.check("image_upload_user", str(auth.user_id))
    data = await _read_capped(request)
    return await run_in_threadpool(
        image_service.upload,
        engine,
        get_storage(request),
        user_id=auth.user_id,
        data=data,
        filename=unquote(x_filename) if x_filename else "",
        ip_hash=ip_hash_of(request, settings),
    )


@router.get("/{image_id}/file")
def file(image_id: uuid.UUID, request: Request, auth: CurrentUser, engine: EngineDep) -> Response:
    data, mime = image_service.read_file(engine, get_storage(request), auth.user_id, image_id)
    return Response(
        content=data,
        media_type=mime,
        headers={
            "Cache-Control": "private, max-age=3600",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; sandbox",
        },
    )


@router.delete("/{image_id}", status_code=204)
def delete(
    image_id: uuid.UUID,
    request: Request,
    auth: WriterUser,
    engine: EngineDep,
    settings: SettingsDep,
    limiter: LimiterDep,
) -> None:
    limiter.check("image_delete_user", str(auth.user_id))
    image_service.remove(
        engine, get_storage(request), auth.user_id, image_id, ip_hash_of(request, settings)
    )
