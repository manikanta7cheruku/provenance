"""Read an uploaded picture and draw it again. Everything in the file is untrusted.

This is the one place that decodes an uploaded image, so the limits live here and every caller gets
them:

  - the kind comes from the first bytes only (JPEG, PNG or WebP). SVG, GIF, HEIC and the rest are
    refused by name, so a person is told why
  - the size is read from the header before any pixel is decoded, and a picture over the pixel or
    side limit is refused without being decoded (a small file can claim to be enormous)
  - a JPEG is decoded at a reduced size when it is large, so a big photo never fills memory
  - an animated picture is refused, and a file whose parts disagree with its type is refused
  - what is kept is never what was uploaded. The picture is turned the right way up from its
    orientation tag, drawn again as a new JPEG (photos) or PNG (pictures with transparency or only a
    few flat colors) with no metadata at all (no camera, place, time or color profile), and cut down to
    a size a resume needs. Anything hidden in the file, after the picture or inside a tag, is gone

A decoder is a large library fed hostile input. Its failures are all caught and become "damaged
picture". Running it in a separate process is carryover for production (C-95).
"""

import io
import warnings
from dataclasses import dataclass

from PIL import Image, ImageOps, UnidentifiedImageError

from pv_domain.resume_images import (
    JPEG_QUALITY,
    MAX_SOURCE_PIXELS,
    MAX_SOURCE_SIDE,
    MAX_UPLOAD_BYTES,
    MIME,
    MIN_SIDE,
    STORED_MAX_SIDE,
    UPLOAD_TYPES,
    ImageErrorCode,
    refusal_for_unknown,
    sniff_type,
)

# Pillow warns at its own limit and refuses at twice that. Ours is checked first, and a warning from
# a decoder is treated as a refusal, never as something to ignore.
Image.MAX_IMAGE_PIXELS = MAX_SOURCE_PIXELS * 2
_FORMATS = {"jpeg": "JPEG", "png": "PNG", "webp": "WEBP"}


class ImageRejected(Exception):
    """The picture cannot be used. code is a member of ImageErrorCode."""

    def __init__(self, code: ImageErrorCode) -> None:
        super().__init__(code.value)
        self.code = code


@dataclass(frozen=True)
class ProcessedImage:
    data: bytes
    kind: str  # "jpeg" or "png"
    width: int
    height: int

    @property
    def mime(self) -> str:
        return MIME[self.kind]


def check_header(data: bytes) -> str:
    """The kind of an upload ("jpeg", "png" or "webp"), from its size and first bytes, or
    ImageRejected. Cheap: no pixel is decoded."""
    if not data:
        raise ImageRejected(ImageErrorCode.NOT_AN_IMAGE)
    if len(data) > MAX_UPLOAD_BYTES:
        raise ImageRejected(ImageErrorCode.TOO_BIG_FILE)
    kind = sniff_type(data[:16])
    if kind is None or kind not in UPLOAD_TYPES:
        raise ImageRejected(refusal_for_unknown(data[:512]))
    return kind


def _open(data: bytes, kind: str) -> Image.Image:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error")  # a decoder warning is a refusal
            image = Image.open(io.BytesIO(data), formats=[_FORMATS[kind]])
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ImageRejected(ImageErrorCode.TOO_MANY_PIXELS) from exc
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError, Warning) as exc:
        raise ImageRejected(ImageErrorCode.CORRUPT) from exc
    return image


def _has_alpha(image: Image.Image) -> bool:
    if image.mode in ("RGBA", "LA", "PA"):
        low = image.getchannel("A").getextrema()[0]
        return not isinstance(low, tuple) and low < 255
    return "transparency" in image.info


def process_image(data: bytes) -> ProcessedImage:
    """Check an uploaded picture and draw it again, or raise ImageRejected."""
    kind = check_header(data)
    image = _open(data, kind)
    try:
        width, height = image.size
        if width < MIN_SIDE or height < MIN_SIDE:
            raise ImageRejected(ImageErrorCode.TOO_SMALL)
        if width * height > MAX_SOURCE_PIXELS or max(width, height) > MAX_SOURCE_SIDE:
            raise ImageRejected(ImageErrorCode.TOO_MANY_PIXELS)
        if getattr(image, "is_animated", False) or getattr(image, "n_frames", 1) > 1:
            raise ImageRejected(ImageErrorCode.ANIMATED)
        if image.format != _FORMATS[kind]:
            raise ImageRejected(ImageErrorCode.CORRUPT)
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error")
                if kind == "jpeg":
                    # Ask the decoder for a smaller picture when the original is large.
                    image.draft("RGB", (STORED_MAX_SIDE * 2, STORED_MAX_SIDE * 2))
                image.load()
                oriented = ImageOps.exif_transpose(image)
        except (
            OSError,
            SyntaxError,
            ValueError,
            MemoryError,
            Warning,
            Image.DecompressionBombError,
        ) as exc:
            raise ImageRejected(ImageErrorCode.CORRUPT) from exc
        return _encode(oriented if oriented is not None else image, kind)
    finally:
        image.close()


def _encode(image: Image.Image, source_kind: str) -> ProcessedImage:
    transparent = _has_alpha(image)
    if transparent:
        flat: Image.Image = image.convert("RGBA")
    else:
        flat = image.convert("RGB")
    flat.thumbnail((STORED_MAX_SIDE, STORED_MAX_SIDE), Image.Resampling.LANCZOS)
    # Nothing the upload carried is kept: no camera or place (EXIF), no comment, no color profile, no
    # text chunk. The encoders write whatever is left in `info`, so it is emptied.
    flat.info = {}
    # Flat graphics (a logo) stay sharp as PNG. Photos become JPEG.
    few_colors = (
        not transparent and source_kind == "png" and flat.getcolors(maxcolors=256) is not None
    )
    out = io.BytesIO()
    if transparent or few_colors:
        flat.save(out, format="PNG", optimize=True)
        kind = "png"
    else:
        flat.save(out, format="JPEG", quality=JPEG_QUALITY, optimize=True, progressive=False)
        kind = "jpeg"
    width, height = flat.size
    return ProcessedImage(data=out.getvalue(), kind=kind, width=width, height=height)
