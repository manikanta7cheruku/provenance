"""Pictures on a resume: what may be uploaded, what is refused and why, and how one is described.

Pure code. The reading of an image file (Pillow) is in pv_files.images, because an uploaded image is
untrusted input and the code that decodes it must stay behind one narrow door. This module holds the
rules both sides share: the limits, the sentence for every refusal, and how a stored picture is
named and embedded in the page that becomes the PDF.

What the product stores is never what was uploaded. The upload is decoded, drawn again as a fresh
JPEG or PNG without any metadata (camera, place, time), cut down to a size a resume needs, and only
that is kept. SVG is never accepted: it can carry script and links.
"""

import base64
from dataclasses import dataclass
from enum import StrEnum

# What a person may upload. What is stored is always one of STORED_TYPES.
UPLOAD_TYPES = ("jpeg", "png", "webp")
STORED_TYPES = ("jpeg", "png")
MIME = {"jpeg": "image/jpeg", "png": "image/png"}

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_SOURCE_PIXELS = 24_000_000  # a 6000 by 4000 photo
MAX_SOURCE_SIDE = 12_000
MIN_SIDE = 16
STORED_MAX_SIDE = 1600
JPEG_QUALITY = 85

MAX_IMAGES_PER_USER = 20
MAX_USER_BYTES = 12 * 1024 * 1024
MAX_IMAGES_PER_DOCUMENT = 5
MAX_ALT_CHARS = 200


class ImageErrorCode(StrEnum):
    NOT_AN_IMAGE = "not_an_image"
    UNSUPPORTED_TYPE = "unsupported_type"
    TOO_BIG_FILE = "too_big_file"
    TOO_MANY_PIXELS = "too_many_pixels"
    TOO_SMALL = "too_small"
    CORRUPT = "corrupt"
    ANIMATED = "animated"
    TOO_MANY_IMAGES = "too_many_images"
    STORAGE_FULL = "storage_full"
    IN_USE = "in_use"


IMAGE_MESSAGES: dict[str, str] = {
    ImageErrorCode.NOT_AN_IMAGE: "This file is not a picture we can read. Choose a JPEG, PNG or WebP image.",
    ImageErrorCode.UNSUPPORTED_TYPE: (
        "This kind of picture is not accepted. Choose a JPEG, PNG or WebP image. SVG, GIF, HEIC "
        "and other types are not used, because they can carry more than a picture."
    ),
    ImageErrorCode.TOO_BIG_FILE: "This file is over the 5 MB limit. Choose a smaller picture.",
    ImageErrorCode.TOO_MANY_PIXELS: (
        "This picture is much larger than a resume needs. Choose one under 24 megapixels, "
        "or resize it first."
    ),
    ImageErrorCode.TOO_SMALL: "This picture is too small to use. Choose one at least 16 pixels wide and tall.",
    ImageErrorCode.CORRUPT: "This picture is damaged or could not be read. Save it again and try again.",
    ImageErrorCode.ANIMATED: "Animated pictures are not used. Choose a still picture.",
    ImageErrorCode.TOO_MANY_IMAGES: (
        f"You can keep up to {MAX_IMAGES_PER_USER} pictures. Delete one you no longer use to add another."
    ),
    ImageErrorCode.STORAGE_FULL: "Your pictures take up the space allowed. Delete one to add another.",
    ImageErrorCode.IN_USE: (
        "This picture is used in one of your resumes, or in a saved version of one. "
        "Remove it from there first, or delete that resume."
    ),
}


@dataclass(frozen=True)
class ImageInfo:
    """What the canvas needs to know about a stored picture to accept it on a page."""

    id: str
    width: int
    height: int
    mime: str


@dataclass(frozen=True)
class ImageBlob:
    mime: str
    data: bytes


def data_uri(blob: ImageBlob) -> str:
    """The picture as a data address, so the page that becomes a PDF needs no other file."""
    return f"data:{blob.mime};base64,{base64.b64encode(blob.data).decode('ascii')}"


def sniff_type(head: bytes) -> str | None:
    """ "jpeg", "png" or "webp" from the first bytes, or None. The file name and the type a browser
    claims are never used."""
    if head.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    return None


def refusal_for_unknown(head: bytes) -> ImageErrorCode:
    """Why a file that is not JPEG, PNG or WebP is refused: a type we recognise but will not accept,
    or not a picture at all."""
    start = head[:512].lstrip()
    lowered = start[:256].lower()
    if head.startswith((b"GIF87a", b"GIF89a")):
        return ImageErrorCode.UNSUPPORTED_TYPE
    if lowered.startswith((b"<svg", b"<?xml", b"<!doctype svg")) or b"<svg" in lowered:
        return ImageErrorCode.UNSUPPORTED_TYPE
    if head[4:8] == b"ftyp" or head.startswith((b"BM", b"II*\x00", b"MM\x00*")):
        return ImageErrorCode.UNSUPPORTED_TYPE  # HEIC, AVIF, BMP, TIFF
    return ImageErrorCode.NOT_AN_IMAGE


def clean_alt(value: object) -> str:
    """Alternative text as one tidy line, cut to length."""
    if not isinstance(value, str):
        return ""
    text = "".join(ch if ch >= " " and ch != "\x7f" else " " for ch in value)
    return " ".join(text.split())[:MAX_ALT_CHARS]
