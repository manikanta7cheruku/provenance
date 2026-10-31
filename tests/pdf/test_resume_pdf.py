"""The PDF engine on real resumes. Runs only where WeasyPrint's native libraries exist.

That is the Docker image and CI, not a plain Windows checkout. Run it with `.\\scripts\\pv.ps1 pdftest`.
These tests check what a person and an applicant tracking system would experience: the text is
selectable and in reading order, the shipped fonts are really embedded (not a silent fallback), the
paper size is right, and the engine cannot be made to fetch anything but the shipped fonts.
"""

import io
import re
from pathlib import Path
from typing import Any

import pytest
from pypdf import PdfReader
from resume_helpers import bullets, sample_document

from pv_domain.resume_doc import blank_document, validate_document
from pv_domain.resume_render import render_html

try:
    from pv_files import RenderError, fonts_dir, html_to_pdf
    from pv_files.render import _only_local_fonts

    html_to_pdf("<html><body>x</body></html>")
    AVAILABLE = True
except Exception:  # noqa: BLE001 - missing native libraries raise OSError, not ImportError
    AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not AVAILABLE, reason="WeasyPrint native libraries are not installed"
)


def pdf_of(doc: dict[str, Any]) -> tuple[PdfReader, int]:
    result = html_to_pdf(render_html(doc, font_base=fonts_dir().as_uri() + "/"))
    assert result.data[:5] == b"%PDF-"
    return PdfReader(io.BytesIO(result.data)), result.page_count


def font_names(reader: PdfReader) -> set[str]:
    names: set[str] = set()
    for page in reader.pages:
        for font in page["/Resources"].get("/Font", {}).values():
            names.add(str(font.get_object().get("/BaseFont")))
    return names


def text_of(reader: PdfReader) -> str:
    return "\n".join(page.extract_text() for page in reader.pages)


def styled(**style: str) -> dict[str, Any]:
    doc = sample_document()
    doc["style"].update(style)
    return validate_document(doc)


class TestRealOutput:
    @pytest.mark.parametrize("template", ["classic", "modern", "compact"])
    def test_text_is_selectable_and_in_reading_order(self, template: str) -> None:
        reader, _ = pdf_of(sample_document(template=template))
        text = " ".join(text_of(reader).split()).lower()
        order = ["Asha Rao", "Data analyst", "asha@example.com", "Experience", "Data Intern",
                 "Cleaned six CSV sources with pandas", "Education", "B.E. Computer Science",
                 "Projects", "Churn model", "Skills", "Python, SQL"]  # fmt: skip
        positions = [text.find(word.lower()) for word in order]
        assert min(positions) >= 0 and positions == sorted(positions)

    @pytest.mark.parametrize(
        "style",
        [
            {"font_pair": "plex-newsreader"},
            {"font_pair": "plex"},
            {"font_pair": "newsreader"},
        ],
    )
    def test_the_shipped_fonts_are_embedded_not_a_fallback(self, style: dict[str, str]) -> None:
        names = " ".join(font_names(pdf_of(styled(**style))[0]))
        assert "PV-Plex" in names or "PV-Serif" in names
        assert "DejaVu" not in names and "Liberation" not in names and "Arial" not in names

    def test_a_bullet_comes_before_its_text_in_the_file(self) -> None:
        text = " ".join(text_of(pdf_of(sample_document())[0]).split())
        assert "\u2022 Cleaned six CSV sources with pandas" in text
        assert "\u2022 Wrote SQL joins" in text
        assert not text.rstrip().endswith("\u2022")

    def test_the_title_and_language_are_in_the_file(self) -> None:
        reader, _ = pdf_of(sample_document())
        assert reader.metadata is not None and reader.metadata.title == "Asha Rao - Resume"
        assert str(reader.trailer["/Root"].get("/Lang")) == "en"

    @pytest.mark.parametrize(("paper", "size"), [("a4", (595, 842)), ("letter", (612, 792))])
    def test_the_paper_size_is_the_one_chosen(self, paper: str, size: tuple[int, int]) -> None:
        reader, _ = pdf_of(styled(paper=paper))
        box = reader.pages[0].mediabox
        assert (round(float(box.width)), round(float(box.height))) == size

    def test_a_long_resume_flows_onto_more_pages_without_losing_text(self) -> None:
        doc = sample_document()
        doc["sections"][0]["blocks"] = [
            {
                "id": f"b{i}", "heading": f"Role {i}", "subheading": "Company", "dates": "2020",
                "location": "", "body": bullets(*[f"Achievement {i}.{j} with a clear result" for j in range(6)]),
            }
            for i in range(14)
        ]  # fmt: skip
        reader, pages = pdf_of(validate_document(doc))
        assert pages >= 2 and len(reader.pages) == pages
        text = text_of(reader)
        assert "Achievement 0.0" in text and "Achievement 13.5" in text

    def test_a_heading_is_not_left_alone_at_the_bottom_of_a_page(self) -> None:
        doc = sample_document()
        doc["sections"][0]["blocks"] = [
            {"id": f"b{i}", "heading": f"Role {i}", "subheading": "Co", "dates": "", "location": "",
             "body": bullets(*[f"Line {i}.{j}" for j in range(5)])}
            for i in range(10)
        ]  # fmt: skip
        reader, _ = pdf_of(validate_document(doc))
        for page in reader.pages:
            lines = [ln for ln in (page.extract_text() or "").splitlines() if ln.strip()]
            assert not re.fullmatch(
                r"(EXPERIENCE|Experience|PROJECTS|EDUCATION|SKILLS)", lines[-1].strip()
            )

    def test_marks_and_empty_documents_still_make_a_valid_pdf(self) -> None:
        reader, pages = pdf_of(validate_document(blank_document("classic", "")))
        assert pages == 1 and len(reader.pages) == 1

    def test_the_same_document_gives_the_same_text_every_time(self) -> None:
        doc = sample_document()
        assert text_of(pdf_of(doc)[0]) == text_of(pdf_of(doc)[0])

    def test_every_template_is_one_page_for_the_sample(self) -> None:
        for template in ("classic", "modern", "compact"):
            assert pdf_of(sample_document(template=template))[1] == 1, template


class TestTheEngineCannotFetch:
    @pytest.mark.parametrize(
        "url",
        [
            "http://127.0.0.1:9/secret.woff",
            "https://example.com/x.woff",
            "file:///etc/passwd",
            "file:///app/.env",
            "ftp://example.com/x",
            "data:text/plain;base64,AAAA",
        ],
    )
    def test_only_the_shipped_fonts_can_be_read(self, url: str) -> None:
        with pytest.raises(ValueError):
            _only_local_fonts(url)

    def test_a_path_that_climbs_out_of_the_font_folder_is_refused(self) -> None:
        with pytest.raises(ValueError):
            _only_local_fonts(fonts_dir().as_uri() + "/../../../../etc/passwd")
        with pytest.raises(ValueError):
            _only_local_fonts(fonts_dir().as_uri() + "/LICENSE-newsreader.txt")

    def test_html_that_asks_for_other_files_is_refused_not_fetched(self) -> None:
        hostile = (
            '<html><body><img src="http://127.0.0.1:9/x.png"><img src="file:///etc/passwd">'
            "<p>Still here</p></body></html>"
        )
        with pytest.raises(RenderError):
            html_to_pdf(hostile)

    def test_a_broken_page_is_an_error_with_no_content_in_the_message(self) -> None:
        with pytest.raises(RenderError) as raised:
            html_to_pdf(None)  # type: ignore[arg-type]
        assert "None" not in str(raised.value)


def test_fonts_are_present_with_their_licences() -> None:
    names = {p.name for p in Path(fonts_dir()).iterdir()}
    assert {"LICENSE-ibm-plex-sans.txt", "LICENSE-newsreader.txt"} <= names
    assert len([n for n in names if n.endswith(".woff")]) == 8
