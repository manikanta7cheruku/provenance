"""The resume HTML: escaping, whitelisted tags, reading order, and the style tokens."""

import re
from html.parser import HTMLParser
from typing import Any

import pytest
from resume_helpers import ENTRIES_FOR_RENDER, para, text_node

from pv_domain.resume_doc import blank_document, document_from_entries, validate_document
from pv_domain.resume_render import FONT_FILES, render_html

ALLOWED_TAGS = {
    "html", "head", "meta", "title", "style", "body", "main", "h1", "h2", "section", "div", "span",
    "p", "ul", "ol", "li", "strong", "em", "u", "mark", "br",
}  # fmt: skip


class Tags(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tags: list[str] = []
        self.attrs: list[tuple[str, str | None]] = []
        self.text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append(tag)
        self.attrs += attrs

    def handle_data(self, data: str) -> None:
        self.text.append(data)


def parse(html: str) -> Tags:
    parser = Tags()
    parser.feed(html)
    return parser


def hostile() -> dict[str, Any]:
    doc = document_from_entries(ENTRIES_FOR_RENDER, name="<script>alert(1)</script>")
    doc["header"]["headline"] = '"><img src=x onerror=alert(1)>'
    doc["header"]["contacts"] = ["a@b.co", "<b>bold</b>"]
    doc["sections"][0]["blocks"][0]["heading"] = "</style><script>x</script>"
    doc["sections"][0]["blocks"][0]["body"] = {
        "type": "doc",
        "content": [para(text_node("<iframe src=//evil></iframe>", "bold", "highlight"))],
    }
    return validate_document(doc)


class TestSafety:
    def test_text_is_escaped_and_only_known_tags_appear(self) -> None:
        html = render_html(hostile(), font_base="/f/")
        assert "<script" not in html and "<img" not in html and "<iframe" not in html
        parsed = parse(html)
        assert set(parsed.tags) <= ALLOWED_TAGS
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html

    def test_no_attribute_can_carry_a_script_or_an_address(self) -> None:
        parsed = parse(render_html(hostile(), font_base="/f/"))
        names = {name for name, _ in parsed.attrs}
        assert names <= {"lang", "charset", "class"}

    def test_the_only_addresses_are_the_shipped_fonts(self) -> None:
        html = render_html(hostile(), font_base="/api/v1/studio/fonts/")
        urls = re.findall(r'url\("([^"]+)"\)', html)
        assert urls and all(u.startswith("/api/v1/studio/fonts/") for u in urls)
        assert {u.rsplit("/", 1)[1] for u in urls} == set(FONT_FILES.values())
        assert "http://" not in html and "https://" not in html and "@import" not in html


class TestContent:
    def test_the_title_and_language_are_set(self) -> None:
        doc = validate_document(blank_document("classic", "Asha Rao"))
        html = render_html(doc, font_base="/f/")
        assert '<html lang="en">' in html and "<title>Asha Rao - Resume</title>" in html
        assert "<title>Resume</title>" in render_html(
            validate_document(blank_document()), font_base="/f/"
        )

    def test_marks_and_lists_become_the_matching_tags(self) -> None:
        doc = document_from_entries(ENTRIES_FOR_RENDER)
        doc["sections"][0]["blocks"][0]["body"] = {
            "type": "doc",
            "content": [
                para(
                    text_node("a", "bold"),
                    text_node("b", "italic"),
                    text_node("c", "underline"),
                    text_node("d", "highlight"),
                    text_node("e", "bold", "italic"),
                ),
                {
                    "type": "orderedList",
                    "content": [{"type": "listItem", "content": [para(text_node("x"))]}],
                },
            ],
        }
        html = render_html(validate_document(doc), font_base="/f/")
        for fragment in (
            "<strong>a</strong>",
            "<em>b</em>",
            "<u>c</u>",
            "<mark>d</mark>",
            "<em><strong>e</strong></em>",
            "<ol><li><p>x</p></li></ol>",
        ):
            assert fragment in html

    def test_reading_order_is_document_order(self) -> None:
        doc = validate_document(document_from_entries(ENTRIES_FOR_RENDER, name="Asha Rao"))
        text = " ".join(" ".join(parse(render_html(doc, font_base="/f/")).text).split())
        body = text[text.index("Asha Rao") :]
        order = ["Asha Rao", "Experience", "Data Intern", "Education", "BMS College",
                 "Projects", "Churn model", "Skills", "Languages"]  # fmt: skip
        positions = [body.index(word) for word in order]
        assert positions == sorted(positions)

    def test_empty_sections_do_not_leave_a_heading(self) -> None:
        doc = blank_document()
        doc["sections"] = [{"kind": "custom", "title": "", "blocks": []}]
        assert "<section" not in render_html(validate_document(doc), font_base="/f/")


class TestStyle:
    @pytest.mark.parametrize(
        ("key", "value", "css"),
        [
            ("paper", "letter", "size:8.5in 11in"),
            ("paper", "a4", "size:210mm 297mm"),
            ("margins", "wide", "margin:22mm"),
            ("size", "large", "font-size:11.5pt"),
            ("divider", "dotted", "0.9pt dotted"),
            ("accent", "#7a1f3d", "#7a1f3d"),
            ("font_pair", "newsreader", '"PV Serif", Georgia, serif'),
        ],
    )
    def test_each_choice_reaches_the_css(self, key: str, value: str, css: str) -> None:
        doc = blank_document("classic", "A")
        doc["style"][key] = value
        assert css in render_html(validate_document(doc), font_base="/f/")

    def test_preview_draws_a_sheet_and_print_sets_the_page(self) -> None:
        doc = validate_document(blank_document("classic", "A"))
        preview = render_html(doc, font_base="/f/", preview=True)
        printed = render_html(doc, font_base="/f/")
        assert "box-shadow" in preview and "@page" not in preview
        assert "@page{size:210mm 297mm" in printed and "box-shadow" not in printed

    def test_the_three_templates_differ(self) -> None:
        css = {
            t: render_html(validate_document(blank_document(t, "A")), font_base="/f/")
            for t in ("classic", "modern", "compact")
        }
        assert len(set(css.values())) == 3
