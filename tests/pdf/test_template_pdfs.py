"""All the templates through the real PDF engine: the right number of pages, the person's words,
real links, and the shipped fonts rather than a fallback. Runs where WeasyPrint's libraries exist."""

import io
import json
from pathlib import Path
from typing import Any

import pytest
from pypdf import PdfReader

from pv_domain.resume_canvas import validate_canvas
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

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "template_docs.json"
DOCS: list[dict[str, Any]] = json.loads(FIXTURE.read_text(encoding="utf-8"))


def pdf_of(doc: dict[str, Any]) -> PdfReader:
    html = render_html(validate_canvas(doc), font_base=fonts_dir().as_uri() + "/")
    return PdfReader(io.BytesIO(html_to_pdf(html).data))


def fonts(reader: PdfReader) -> str:
    names: set[str] = set()
    for page in reader.pages:
        for font in page["/Resources"].get("/Font", {}).values():
            names.add(str(font.get_object().get("/BaseFont")))
    return " ".join(sorted(names))


@pytest.mark.parametrize("doc", DOCS, ids=[d["style"]["template"] for d in DOCS])
def test_the_template_prints(doc: dict[str, Any]) -> None:
    reader = pdf_of(doc)
    assert len(reader.pages) == len(doc["pages"])
    text = " ".join(" ".join(p.extract_text().split()) for p in reader.pages)
    assert "Asha Rao" in text.replace("ASHA RAO", "Asha Rao")
    assert "Cut weekly reporting" in text
    names = fonts(reader)
    assert "DejaVu" not in names and "Liberation" not in names, names
    assert "PV-" in names, names


def test_a_contact_link_is_a_real_link_in_the_file() -> None:
    reader = pdf_of(DOCS[0])
    targets = []
    for annotation in reader.pages[0].get("/Annots", []):
        action = annotation.get_object().get("/A")
        if action is not None:
            targets.append(str(action.get_object().get("/URI")))
    assert "mailto:asha.rao@example.com" in targets
    assert "https://linkedin.com/in/asharao" in targets
