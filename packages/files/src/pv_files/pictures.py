"""The pictures a resume document uses: which ones the person owns, and their bytes.

Shared by the API (saving and previewing) and the worker (making the PDF), so a resume can only ever
draw pictures that belong to its own owner. Call inside tenant_session.
"""

import contextlib
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from pv_domain.resume_canvas import raw_image_ids
from pv_domain.resume_images import ImageBlob, ImageInfo
from pv_files.storage import FileStorage, StorageError
from pv_persistence.images import owned_info
from pv_persistence.models import ResumeImage


@dataclass
class Pictures:
    infos: Mapping[str, ImageInfo] = field(default_factory=dict)
    blobs: Mapping[str, ImageBlob] = field(default_factory=dict)


def load_pictures(
    db: Session, owner_id: uuid.UUID, content: Any, storage: FileStorage | None = None
) -> Pictures:
    """The owner's pictures that `content` refers to. With `storage` the bytes are read too. A
    picture whose file is missing is left out of the bytes, never an error: the box draws empty."""
    ids = raw_image_ids(content)
    infos = owned_info(db, owner_id, ids)
    blobs: dict[str, ImageBlob] = {}
    if storage is not None and infos:
        rows = {
            str(r.id): r
            for r in db.query(ResumeImage)
            .filter(
                ResumeImage.owner_user_id == owner_id,
                ResumeImage.id.in_([uuid.UUID(i) for i in infos]),
            )
            .all()
        }
        for image_id, row in rows.items():
            with contextlib.suppress(StorageError):
                blobs[image_id] = ImageBlob(mime=row.mime, data=storage.get(row.storage_key))
    return Pictures(infos=infos, blobs=blobs)
