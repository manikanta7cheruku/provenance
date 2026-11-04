"""Uploaded pictures: what is accepted, what is refused and why, and what is kept. Every file here is
hostile until it has been drawn again."""

import io
import struct
from typing import Any

import pytest
from PIL import Image

from pv_domain.resume_images import (
    IMAGE_MESSAGES,
    MAX_UPLOAD_BYTES,
    STORED_MAX_SIDE,
    ImageBlob,
    ImageErrorCode,
    clean_alt,
    data_uri,
    refusal_for_unknown,
    sniff_type,
)
from pv_files.images import ImageRejected, check_header, process_image


def photo(size: tuple[int, int] = (320, 240), fmt: str = "JPEG", **save: Any) -> bytes:
    image = Image.effect_mandelbrot(size, (-2, -1.5, 1, 1.5), 40).convert("RGB")
    out = io.BytesIO()
    image.save(out, format=fmt, **save)
    return out.getvalue()


def refused(data: bytes) -> ImageErrorCode:
    with pytest.raises(ImageRejected) as error:
        process_image(data)
    return error.value.code


def opened(data: bytes) -> Image.Image:
    image = Image.open(io.BytesIO(data))
    image.load()
    return image


# --------------------------------------------------------------------- what an upload is


def test_the_kind_comes_from_the_first_bytes() -> None:
    assert sniff_type(photo()[:16]) == "jpeg"
    assert sniff_type(photo(fmt="PNG")[:16]) == "png"
    assert sniff_type(photo(fmt="WEBP")[:16]) == "webp"
    assert sniff_type(b"GIF89a....") is None and sniff_type(b"") is None


@pytest.mark.parametrize(
    ("head", "code"),
    [
        (b"GIF89a\x01\x00\x01\x00", ImageErrorCode.UNSUPPORTED_TYPE),
        (b"GIF87a", ImageErrorCode.UNSUPPORTED_TYPE),
        (
            b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
            ImageErrorCode.UNSUPPORTED_TYPE,
        ),
        (b'<?xml version="1.0"?><svg></svg>', ImageErrorCode.UNSUPPORTED_TYPE),
        (b"\x00\x00\x00\x18ftypheic", ImageErrorCode.UNSUPPORTED_TYPE),
        (b"BM\x36\x00", ImageErrorCode.UNSUPPORTED_TYPE),
        (b"II*\x00\x08", ImageErrorCode.UNSUPPORTED_TYPE),
        (b"%PDF-1.7", ImageErrorCode.NOT_AN_IMAGE),
        (b"<html><script>x</script></html>", ImageErrorCode.NOT_AN_IMAGE),
        (b"MZ\x90\x00", ImageErrorCode.NOT_AN_IMAGE),
        (b"just some text", ImageErrorCode.NOT_AN_IMAGE),
    ],
)
def test_other_types_are_refused_with_the_right_reason(head: bytes, code: ImageErrorCode) -> None:
    assert refusal_for_unknown(head) is code
    assert refused(head + b"\x00" * 64) is code


def test_an_empty_file_and_an_oversized_one_are_refused_before_anything_is_decoded() -> None:
    assert refused(b"") is ImageErrorCode.NOT_AN_IMAGE
    assert (
        refused(b"\xff\xd8\xff" + b"\x00" * (MAX_UPLOAD_BYTES + 1)) is ImageErrorCode.TOO_BIG_FILE
    )
    with pytest.raises(ImageRejected):
        check_header(b"\xff\xd8\xff" + b"\x00" * (MAX_UPLOAD_BYTES + 1))


def test_every_refusal_has_a_sentence() -> None:
    assert set(IMAGE_MESSAGES) == {c.value for c in ImageErrorCode}
    assert all(IMAGE_MESSAGES.values())


# --------------------------------------------------------------------- what is kept


def test_a_photo_is_drawn_again_as_a_jpeg() -> None:
    result = process_image(photo((800, 600)))
    assert (result.kind, result.mime) == ("jpeg", "image/jpeg")
    assert (result.width, result.height) == (800, 600)
    assert opened(result.data).format == "JPEG"


def test_a_png_and_a_webp_photo_become_a_jpeg() -> None:
    for fmt in ("PNG", "WEBP"):
        result = process_image(photo((400, 300), fmt))
        assert opened(result.data).format == ("JPEG" if fmt == "WEBP" else result.kind.upper())


def test_a_picture_with_transparency_stays_a_png_with_its_transparency() -> None:
    image = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
    image.paste((200, 30, 30, 255), (50, 50, 150, 150))
    out = io.BytesIO()
    image.save(out, format="PNG")
    result = process_image(out.getvalue())
    assert result.kind == "png"
    corner = opened(result.data).convert("RGBA").getpixel((2, 2))
    assert isinstance(corner, tuple) and corner[3] == 0


def test_a_flat_graphic_stays_a_sharp_png() -> None:
    image = Image.new("RGB", (240, 80), (255, 255, 255))
    image.paste((20, 60, 140), (10, 10, 120, 70))
    out = io.BytesIO()
    image.save(out, format="PNG")
    assert process_image(out.getvalue()).kind == "png"


def test_a_large_picture_is_cut_down_to_a_size_a_resume_needs() -> None:
    result = process_image(photo((4000, 3000)))
    assert max(result.width, result.height) == STORED_MAX_SIDE
    assert (result.width, result.height) == (1600, 1200)
    assert len(result.data) < MAX_UPLOAD_BYTES


def test_the_picture_is_turned_the_right_way_up_from_its_orientation_tag() -> None:
    image = Image.effect_mandelbrot((300, 200), (-2, -1.5, 1, 1.5), 30).convert("RGB")
    exif = Image.Exif()
    exif[0x0112] = 6  # rotate 90 degrees
    out = io.BytesIO()
    image.save(out, format="JPEG", exif=exif)
    result = process_image(out.getvalue())
    assert (result.width, result.height) == (200, 300)


# --------------------------------------------------------------------- what is thrown away


def test_camera_place_and_time_are_gone() -> None:
    image = Image.effect_mandelbrot((300, 200), (-2, -1.5, 1, 1.5), 30).convert("RGB")
    exif = Image.Exif()
    exif[0x010F] = "Acme Camera"  # make
    exif[0x0132] = "2026:11:04 10:00:00"  # time
    exif[0x8825] = {1: "N", 2: (18.0, 31.0, 0.0), 3: "E", 4: (73.0, 51.0, 0.0)}  # a place
    out = io.BytesIO()
    image.save(out, format="JPEG", exif=exif)
    assert b"Acme Camera" in out.getvalue()  # it really was in the file
    result = process_image(out.getvalue())
    assert b"Acme Camera" not in result.data and b"2026:11:04" not in result.data
    kept = opened(result.data)
    assert len(kept.getexif()) == 0 and "exif" not in kept.info


def test_png_text_chunks_and_profiles_are_gone() -> None:
    from PIL import PngImagePlugin

    meta = PngImagePlugin.PngInfo()
    meta.add_text("Comment", "secret note about the applicant")
    meta.add_text("Author", "Asha Rao")
    out = io.BytesIO()
    Image.new("RGBA", (64, 64), (1, 2, 3, 128)).save(
        out, format="PNG", pnginfo=meta, icc_profile=b"profile-bytes"
    )
    assert b"secret note" in out.getvalue()
    result = process_image(out.getvalue())
    assert b"secret note" not in result.data and b"Asha Rao" not in result.data
    kept = opened(result.data)
    assert kept.info.get("icc_profile") is None and "Comment" not in kept.info


def test_anything_hidden_after_the_picture_is_gone() -> None:
    payload = b"<?php system($_GET['c']); ?><script>alert(1)</script>PK\x03\x04hidden-archive"
    data = photo() + payload
    assert payload in data
    result = process_image(data)
    assert (
        b"<script>" not in result.data
        and b"<?php" not in result.data
        and b"hidden-archive" not in result.data
    )
    assert opened(result.data).format == "JPEG"


def test_a_picture_that_is_also_a_script_does_not_survive_as_one() -> None:
    sneaky = b"\xff\xd8\xff\xfe\x00\x20<script>alert(1)</script>" + photo()[2:]
    try:
        result = process_image(sneaky)
    except ImageRejected:
        return  # refusing it is as good
    assert b"<script>" not in result.data


# --------------------------------------------------------------------- hostile files


def test_a_picture_that_is_too_small_is_refused() -> None:
    assert refused(photo((10, 10))) is ImageErrorCode.TOO_SMALL
    assert refused(photo((15, 400))) is ImageErrorCode.TOO_SMALL


def test_a_small_file_that_claims_to_be_enormous_is_refused_without_being_decoded() -> None:
    out = io.BytesIO()
    Image.new("1", (20_000, 20_000)).save(out, format="PNG")  # a few hundred KB, 400 million pixels
    assert len(out.getvalue()) < MAX_UPLOAD_BYTES
    assert refused(out.getvalue()) is ImageErrorCode.TOO_MANY_PIXELS


def test_a_picture_with_one_huge_side_is_refused() -> None:
    out = io.BytesIO()
    Image.new("1", (13_000, 20)).save(out, format="PNG")
    assert refused(out.getvalue()) is ImageErrorCode.TOO_MANY_PIXELS


def test_animated_pictures_are_refused() -> None:
    frames = [Image.new("RGB", (64, 64), (i * 40, 0, 0)) for i in range(3)]
    for fmt in ("WEBP", "PNG"):
        out = io.BytesIO()
        frames[0].save(
            out, format=fmt, save_all=True, append_images=frames[1:], duration=100, loop=0
        )
        assert refused(out.getvalue()) is ImageErrorCode.ANIMATED, fmt


def test_a_gif_is_refused_even_a_still_one() -> None:
    out = io.BytesIO()
    Image.new("P", (64, 64)).save(out, format="GIF")
    assert refused(out.getvalue()) is ImageErrorCode.UNSUPPORTED_TYPE


def test_damaged_pictures_are_refused_as_damaged() -> None:
    good = photo((400, 300))
    for broken in (
        good[: len(good) // 3],
        good[:20],
        b"\xff\xd8\xff" + b"\x00" * 200,
        good[:100] + b"\x00" * 500,
    ):
        assert refused(broken) is ImageErrorCode.CORRUPT
    png = photo((200, 200), "PNG")
    assert refused(png[: len(png) // 2]) is ImageErrorCode.CORRUPT
    assert refused(png[:30]) is ImageErrorCode.CORRUPT


def test_a_png_header_with_a_crc_that_lies_is_refused() -> None:
    png = bytearray(photo((100, 100), "PNG"))
    # Break the checksum of the first chunk (the header). A decoder that ignores it is a risk.
    png[29] ^= 0xFF
    assert refused(bytes(png)) is ImageErrorCode.CORRUPT


def test_a_header_that_claims_a_huge_size_with_no_data_is_refused() -> None:
    header = (
        b"\x89PNG\r\n\x1a\n"
        + struct.pack(">I", 13)
        + b"IHDR"
        + struct.pack(">IIBBBBB", 40_000, 40_000, 8, 2, 0, 0, 0)
    )
    assert refused(header + b"\x00" * 64) in {
        ImageErrorCode.TOO_MANY_PIXELS,
        ImageErrorCode.CORRUPT,
    }


def test_processing_the_same_picture_twice_gives_the_same_bytes() -> None:
    data = photo((500, 400))
    assert process_image(data).data == process_image(data).data


# --------------------------------------------------------------------- the small helpers


def test_alt_text_is_one_tidy_short_line() -> None:
    assert clean_alt("  A   photo\nof\tAsha\x00 ") == "A photo of Asha"
    assert len(clean_alt("x" * 500)) == 200
    assert clean_alt(None) == "" and clean_alt(5) == ""


def test_a_picture_is_embedded_as_a_data_address() -> None:
    uri = data_uri(ImageBlob("image/png", b"\x89PNG"))
    assert uri == "data:image/png;base64,iVBORw=="
