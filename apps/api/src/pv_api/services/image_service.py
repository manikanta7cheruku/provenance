"""Pictures for the resume studio: upload, list, serve, delete.

Everything runs in one tenant session (Row Level Security) and filters by the signed-in owner. A
picture that belongs to someone else is "not found", never "forbidden". An upload is checked and drawn
again by pv_files.images, so what is stored is never what was sent. Only the owner can read the file,
and it is served with a type we chose, never one the upload claimed.
"""

import contextlib
import hashlib
import uuid

from sqlalchemy.engine import Engine

from pv_api.errors import ApiError
from pv_api.schemas import ImageOut, ImagesOut
from pv_domain.failures import FailureClass
from pv_domain.resume import safe_display_filename
from pv_domain.resume_images import (
    IMAGE_MESSAGES,
    MAX_IMAGES_PER_USER,
    MAX_USER_BYTES,
    ImageErrorCode,
)
from pv_files import FileStorage, ImageRejected, StorageError, new_image_key, process_image
from pv_persistence.audit import record_audit
from pv_persistence.images import (
    add_image,
    delete_image,
    find_by_hash,
    get_image,
    is_used,
    list_images,
    totals,
)
from pv_persistence.models import ResumeImage
from pv_persistence.tenancy import tenant_session

FILE_URL = "/api/v1/studio/images/{id}/file"
ACCEPTED = ["JPEG", "PNG", "WebP"]


def _not_found() -> ApiError:
    return ApiError(404, "NOT_FOUND", "Not found.", failure_class=FailureClass.PERMANENT)


def _refused(code: ImageErrorCode, status: int = 422) -> ApiError:
    return ApiError(
        status,
        "IMAGE_REJECTED"
        if status == 422
        else "PAYLOAD_TOO_LARGE"
        if status == 413
        else "IMAGE_LIMIT",
        IMAGE_MESSAGES[code],
        failure_class=FailureClass.VALIDATION_FAILED,
    )


def _out(row: ResumeImage, used: bool) -> ImageOut:
    return ImageOut(
        id=row.id,
        width=row.width,
        height=row.height,
        mime=row.mime,
        size_bytes=row.size_bytes,
        original_name=row.original_name,
        created_at=row.created_at,
        used=used,
        url=FILE_URL.format(id=row.id),
    )


def _listing(db, user_id: uuid.UUID) -> ImagesOut:  # type: ignore[no-untyped-def]
    rows = list_images(db, user_id)
    count, size = totals(db, user_id)
    return ImagesOut(
        images=[_out(r, is_used(db, user_id, r.id)) for r in rows],
        max_images=MAX_IMAGES_PER_USER,
        max_bytes=MAX_USER_BYTES,
        used_bytes=size,
        accepted=ACCEPTED,
        count=count,
    )


def list_all(engine: Engine, user_id: uuid.UUID) -> ImagesOut:
    with tenant_session(engine, user_id) as db:
        return _listing(db, user_id)


def upload(
    engine: Engine,
    storage: FileStorage,
    *,
    user_id: uuid.UUID,
    data: bytes,
    filename: str,
    ip_hash: str | None,
) -> ImageOut:
    try:
        processed = process_image(data)
    except ImageRejected as rejected:
        raise _refused(
            rejected.code, 413 if rejected.code == ImageErrorCode.TOO_BIG_FILE else 422
        ) from rejected
    digest = hashlib.sha256(processed.data).hexdigest()
    name = safe_display_filename(filename) if filename else ""
    key = new_image_key()
    stored = False
    try:
        with tenant_session(engine, user_id) as db:
            existing = find_by_hash(db, user_id, digest)
            if existing is not None:
                return _out(existing, is_used(db, user_id, existing.id))
            count, size = totals(db, user_id)
            if count >= MAX_IMAGES_PER_USER:
                raise _refused(ImageErrorCode.TOO_MANY_IMAGES, 409)
            if size + len(processed.data) > MAX_USER_BYTES:
                raise _refused(ImageErrorCode.STORAGE_FULL, 409)
            try:
                storage.put(key, processed.data)
                stored = True
            except StorageError as exc:
                raise ApiError(
                    503, "STORAGE_UNAVAILABLE", "The picture could not be saved. Try again.",
                    failure_class=FailureClass.TRANSIENT,
                ) from exc  # fmt: skip
            row = add_image(
                db,
                owner_id=user_id,
                storage_key=key,
                mime=processed.mime,
                width=processed.width,
                height=processed.height,
                size_bytes=len(processed.data),
                original_name=name,
                digest=digest,
            )
            if row is None:  # the same picture arrived twice at once
                found = find_by_hash(db, user_id, digest)
                if found is None:
                    raise _not_found()
                with contextlib.suppress(StorageError):
                    storage.delete(key)
                stored = False
                return _out(found, False)
            out = _out(row, False)
    except Exception:
        if stored:
            with contextlib.suppress(StorageError):
                storage.delete(key)
        raise
    record_audit(
        engine, category="audit", action="resume_image.uploaded", actor_user_id=user_id,
        target_type="resume_image", target_id=str(out.id), ip_hash=ip_hash,
        metadata={"kind": processed.kind, "bytes": len(processed.data)},
    )  # fmt: skip
    return out


def read_file(
    engine: Engine, storage: FileStorage, user_id: uuid.UUID, image_id: uuid.UUID
) -> tuple[bytes, str]:
    with tenant_session(engine, user_id) as db:
        row = get_image(db, user_id, image_id)
        if row is None:
            raise _not_found()
        key, mime = row.storage_key, row.mime
    try:
        return storage.get(key), mime
    except StorageError as exc:
        raise _not_found() from exc


def remove(
    engine: Engine,
    storage: FileStorage,
    user_id: uuid.UUID,
    image_id: uuid.UUID,
    ip_hash: str | None,
) -> None:
    with tenant_session(engine, user_id) as db:
        row = get_image(db, user_id, image_id)
        if row is None:
            raise _not_found()
        if is_used(db, user_id, image_id):
            raise _refused(ImageErrorCode.IN_USE, 409)
        key = delete_image(db, user_id, row)
    with contextlib.suppress(StorageError):
        storage.delete(key)
    record_audit(
        engine, category="audit", action="resume_image.deleted", actor_user_id=user_id,
        target_type="resume_image", target_id=str(image_id), ip_hash=ip_hash,
    )  # fmt: skip
