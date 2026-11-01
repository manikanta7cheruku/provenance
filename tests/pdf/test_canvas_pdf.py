"""Free canvas resumes through the real PDF engine. Runs where WeasyPrint's native libraries exist.

The canvas puts boxes at exact positions, so these tests check that the PDF puts the text where the
document says, in the order a reader will meet it, with the shipped fonts, on the right paper, over
as many pages as the document has. A fidelity spike on five layouts (recorded in ADR-0025) measured
the same thing against the browser canvas. These tests keep it true.
"""

import io
from typing import Any

import pytest
from canvas_helpers import canvas, rich, sample_canvas, shape_el, text_el
from pypdf import PdfReader

from pv_domain.resume_canvas import validate_canvas
from pv_domain.resume_doc import rich_to_text
from pv_domain.resume_render import render_html

try:
    from pv_files import fonts_dir, html_to_pdf

    html_to_pdf("<html><body>x</body></html>")
    AVAILABLE = True
except Exception:  # noqa: BLE001 - missing native libraries raise OSError, not ImportError
    AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not AVAILABLE, reason="WeasyPrint native libraries are not installed"
)

PT_MM = 25.4 / 72


def pdf_of(doc: dict[str, Any]) -> PdfReader:
    clean = validate_canvas(doc)
    result = html_to_pdf(render_html(clean, font_base=fonts_dir().as_uri() + "/"))
    assert result.data[:5] == b"%PDF-"
    return PdfReader(io.BytesIO(result.data))


def fragments(reader: PdfReader, page: int = 0) -> list[tuple[str, float, float]]:
    """Every piece of text with where it starts: millimetres across, millimetres down from the top."""
    height_pt = float(reader.pages[page].mediabox.height)
    found: list[tuple[str, float, float]] = []

    def visit(text: str, cm: list[float], tm: list[float], _font: Any, _size: float) -> None:
        if text.strip():
            x = tm[4] * cm[0] + cm[4]
            y = tm[5] * cm[3] + cm[5]
            found.append((text, x * PT_MM, (height_pt - y) * PT_MM))

    reader.pages[page].extract_text(visitor_text=visit)
    return found


def font_names(reader: PdfReader) -> set[str]:
    names: set[str] = set()
    for page in reader.pages:
        for font in page["/Resources"].get("/Font", {}).values():
            names.add(str(font.get_object().get("/BaseFont")))
    return names


def test_each_text_box_starts_where_the_document_says() -> None:
    doc = sample_canvas()
    found = fragments(pdf_of(doc))
    for el in doc["pages"][0]["elements"]:
        if (
            el["kind"] != "text"
            or el["align"] != "left"
            or el["body"]["content"][0]["type"] != "paragraph"
        ):
            continue  # a list starts with its bullet, which is checked on its own below
        word = rich_to_text(el["body"]).replace("- ", "").split()[0]
        candidates = [
            (x, y) for text, x, y in found if text.strip().upper().startswith(word[:5].upper())
        ]
        # Other boxes can start with the same word, so take the fragment closest to where this one is.
        match = min(candidates, key=lambda c: abs(c[1] - el["y"]), default=None)
        assert match is not None, el["id"]
        x, y = match
        assert abs(x - el["x"]) < 0.8, (el["id"], x, el["x"])
        assert el["y"] - 0.5 <= y <= el["y"] + el["size"] * 0.3528 * 1.8 + 1.5, (
            el["id"],
            y,
            el["y"],
        )


def test_a_right_aligned_box_ends_at_its_right_edge() -> None:
    doc = canvas(text_el("d", 150, 40, 44, 5, rich("2025-06 to 2025-08"), align="right", size=9.5))
    reader = pdf_of(doc)
    words = [(t, x) for t, x, _ in fragments(reader)]
    start = min(x for _, x in words)
    assert 160 < start < 190  # a 31 mm line in a box from 150 to 194 mm starts about 162 mm across


def test_two_columns_are_read_one_after_the_other_not_line_by_line() -> None:
    left = "LEFTSTART " + "alpha " * 40 + "LEFTEND"
    right = "RIGHTSTART " + "beta " * 40 + "RIGHTEND"
    doc = canvas(
        text_el("l", 16, 40, 85, 60, rich(left)), text_el("r", 109, 40, 85, 60, rich(right))
    )
    text = " ".join(" ".join(page.extract_text().split()) for page in pdf_of(doc).pages)
    assert (
        text.index("LEFTSTART")
        < text.index("LEFTEND")
        < text.index("RIGHTSTART")
        < text.index("RIGHTEND")
    )


def test_reading_order_is_top_to_bottom_whatever_the_stacking_order() -> None:
    doc = canvas(
        text_el("last", 16, 120, 100, 5, rich("THIRD")),
        text_el("first", 16, 20, 100, 5, rich("FIRST")),
        text_el("middle", 16, 70, 100, 5, rich("SECOND")),
    )
    text = " ".join(" ".join(page.extract_text().split()) for page in pdf_of(doc).pages)
    assert text.index("FIRST") < text.index("SECOND") < text.index("THIRD")


def test_the_shipped_fonts_are_embedded_for_both_roles_and_every_pair() -> None:
    for pair in ("plex-newsreader", "plex", "newsreader"):
        doc = sample_canvas()
        doc["style"]["font_pair"] = pair
        names = " ".join(font_names(pdf_of(doc)))
        assert "PV-Plex" in names or "PV-Serif" in names, pair
        assert "DejaVu" not in names and "Liberation" not in names, pair


def test_the_paper_is_the_one_chosen() -> None:
    for paper, size in (("a4", (595, 842)), ("letter", (612, 792))):
        doc = canvas(text_el("a", 10, 10, 50, 8, rich("x")), paper=paper)
        box = pdf_of(doc).pages[0].mediabox
        assert (round(float(box.width)), round(float(box.height))) == size


def test_every_page_of_the_document_is_a_page_of_the_pdf() -> None:
    doc = canvas(text_el("a", 10, 10, 50, 8, rich("PAGEONE")), pages=3)
    doc["pages"][1]["elements"] = [text_el("b", 10, 10, 50, 8, rich("PAGETWO"))]
    doc["pages"][2]["elements"] = [text_el("c", 10, 10, 50, 8, rich("PAGETHREE"))]
    reader = pdf_of(doc)
    assert len(reader.pages) == 3
    assert [p.extract_text().split()[0] for p in reader.pages] == [
        "PAGEONE",
        "PAGETWO",
        "PAGETHREE",
    ]


def test_a_page_with_only_shapes_is_still_a_page_and_shapes_add_no_text() -> None:
    doc = canvas(shape_el("s", 16, 20, 100, 30), text_el("t", 20, 25, 60, 6, rich("ON TOP")))
    reader = pdf_of(doc)
    assert len(reader.pages) == 1 and "ON TOP" in reader.pages[0].extract_text()


def test_the_title_and_language_are_in_the_file() -> None:
    reader = pdf_of(sample_canvas())
    assert reader.metadata is not None and reader.metadata.title == "Asha Rao - Resume"
    assert str(reader.trailer["/Root"].get("/Lang")) == "en"


def test_bullets_come_before_their_text() -> None:
    text = " ".join(pdf_of(sample_canvas()).pages[0].extract_text().split())
    assert "• Cleaned six CSV sources with pandas" in text
