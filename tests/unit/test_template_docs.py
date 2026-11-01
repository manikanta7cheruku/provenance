"""Every template the browser can lay out must be accepted by the server and drawn as HTML.

tests/fixtures/template_docs.json is written by the web tests (WRITE_TEMPLATE_FIXTURES=1) from the
real layout code, one document per template, so a layout the validator would refuse fails here."""

import json
from pathlib import Path
from typing import Any

import pytest

from pv_domain.resume_canvas import canvas_text, validate_canvas
from pv_domain.resume_render import render_html

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "template_docs.json"
DOCS: list[dict[str, Any]] = json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_there_are_at_least_twenty_templates() -> None:
    assert len(DOCS) >= 20
    assert len({d["style"]["template"] for d in DOCS}) == len(DOCS)


@pytest.mark.parametrize("doc", DOCS, ids=[d["style"]["template"] for d in DOCS])
def test_the_server_accepts_the_template_and_draws_it(doc: dict[str, Any]) -> None:
    clean = validate_canvas(doc)
    assert clean["style"]["template"] == doc["style"]["template"]
    assert len(clean["pages"]) == len(doc["pages"])
    for before, after in zip(doc["pages"], clean["pages"], strict=True):
        assert len(before["elements"]) == len(after["elements"])
    text = canvas_text(clean)
    assert "Asha Rao" in text and "Cut weekly reporting" in text
    html = render_html(clean, font_base="/f/")
    assert html.count('<section class="page">') == len(doc["pages"])
    assert "<script" not in html


def test_contacts_are_links_in_the_html() -> None:
    html = render_html(validate_canvas(DOCS[0]), font_base="/f/")
    assert 'href="mailto:asha.rao@example.com"' in html
    assert 'href="tel:+919876543210"' in html
    assert 'href="https://linkedin.com/in/asharao"' in html
