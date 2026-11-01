"""Checkpoint 2.3: links in rich text, the font library, palettes and template labels."""

from pathlib import Path
from typing import Any

import pytest
from canvas_helpers import canvas, shape_el, text_el

from pv_domain.resume_canvas import ROLES, validate_canvas
from pv_domain.resume_doc import (
    FONT_PAIRS,
    ResumeDocError,
    blank_document,
    clean_href,
    contrast_ratio,
    validate_document,
)
from pv_domain.resume_render import FAMILIES, FONT_FILES, render_html
from pv_domain.resume_render import FONT_PAIRS as STACKS

FONT_DIR = Path(__file__).resolve().parents[2] / "packages/files/src/pv_files/assets/fonts"


def linked(text: str, href: object) -> dict[str, Any]:
    return {
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "content": [
                    {
                        "type": "text",
                        "text": text,
                        "marks": [{"type": "link", "attrs": {"href": href}}],
                    }
                ],
            }
        ],
    }


class TestHref:
    @pytest.mark.parametrize(
        "href",
        [
            "https://example.com",
            "http://example.com/a?b=c#d",
            "HTTPS://Example.com",
            "mailto:asha@example.com",
            "tel:+919876543210",
            "https://github.com/asha-rao",
        ],
    )
    def test_safe_addresses_are_kept(self, href: str) -> None:
        assert clean_href(href) == href

    @pytest.mark.parametrize(
        "href",
        [
            "javascript:alert(1)",
            "JaVaScRiPt:alert(1)",
            "data:text/html,<script>1</script>",
            "file:///etc/passwd",
            "ftp://example.com",
            "//example.com",
            "example.com",
            "https://",
            "mailto:",
            "https:///nohost",
            "https://exa mple.com",
            'https://example.com/"onclick="x',
            "https://example.com/<b>",
            "https://example.com/\nx",
            "https://" + "a" * 2100,
            "",
            None,
            5,
        ],
    )
    def test_everything_else_is_refused(self, href: object) -> None:
        assert clean_href(href) is None


class TestLinksInDocuments:
    def test_a_guided_document_keeps_a_link_and_draws_it_as_an_anchor(self) -> None:
        doc = blank_document()
        doc["sections"] = [
            {
                "id": "s",
                "kind": "custom",
                "title": "Links",
                "blocks": [
                    {
                        "id": "b",
                        "heading": "",
                        "subheading": "",
                        "dates": "",
                        "location": "",
                        "body": linked("My site", "https://example.com/a?x=1&y=2"),
                    }
                ],
            }
        ]
        clean = validate_document(doc)
        html = render_html(clean, font_base="/f/")
        assert (
            '<a href="https://example.com/a?x=1&amp;y=2" rel="noopener noreferrer">My site</a>'
            in html
        )

    def test_a_bad_link_is_refused_next_to_the_text(self) -> None:
        doc = canvas(text_el("a", 10, 10, 50, 8, linked("Click", "javascript:alert(1)")))
        with pytest.raises(ResumeDocError) as caught:
            validate_canvas(doc)
        assert "pages.0.elements.0.body" in caught.value.problems[
            next(iter(caught.value.problems))
        ] or any("link is not valid" in v for v in caught.value.problems.values())

    def test_a_canvas_link_is_written_as_an_anchor_with_no_script(self) -> None:
        clean = validate_canvas(
            canvas(text_el("a", 10, 10, 80, 8, linked("Mail me", "mailto:a@b.co")))
        )
        html = render_html(clean, font_base="/f/")
        assert 'href="mailto:a@b.co"' in html and "<script" not in html


class TestFonts:
    def test_every_font_file_exists_and_every_pair_uses_known_families(self) -> None:
        for name in FONT_FILES.values():
            assert (FONT_DIR / name).is_file(), name
        for key in FONT_PAIRS:
            heading, body = STACKS[key]
            for stack in (heading, body):
                family = stack.split('"')[1]
                assert family in FAMILIES, (key, family)

    def test_every_family_has_a_licence_next_to_its_files(self) -> None:
        for prefix in set(FAMILIES.values()):
            assert (FONT_DIR / f"LICENSE-{prefix}.txt").is_file(), prefix

    def test_the_validator_accepts_each_pair_and_refuses_others(self) -> None:
        for key in FONT_PAIRS:
            assert (
                validate_canvas(canvas(text_el("a", 1, 1, 5, 5), font_pair=key))["style"][
                    "font_pair"
                ]
                == key
            )
        with pytest.raises(ResumeDocError):
            validate_canvas(canvas(text_el("a", 1, 1, 5, 5), font_pair="comic"))


class TestPalettes:
    def test_ink_muted_and_tint_default_and_can_be_changed(self) -> None:
        style = validate_canvas(canvas(text_el("a", 1, 1, 5, 5)))["style"]
        assert (style["ink"], style["muted"], style["tint"]) == ("#1b1b1b", "#4a4a4a", "#eef1f6")
        custom = validate_canvas(
            canvas(text_el("a", 1, 1, 5, 5), ink="#222a35", muted="#555b66", tint="#f3ede4")
        )
        assert custom["style"]["tint"] == "#f3ede4"

    def test_text_colors_must_be_readable_on_white(self) -> None:
        with pytest.raises(ResumeDocError) as caught:
            validate_canvas(canvas(text_el("a", 1, 1, 5, 5), ink="#bbbbbb"))
        assert "style.ink" in caught.value.problems
        with pytest.raises(ResumeDocError) as caught:
            validate_canvas(canvas(text_el("a", 1, 1, 5, 5), muted="#cccccc"))
        assert "style.muted" in caught.value.problems

    def test_the_tint_must_leave_the_text_readable(self) -> None:
        with pytest.raises(ResumeDocError) as caught:
            validate_canvas(canvas(text_el("a", 1, 1, 5, 5), tint="#444444"))
        assert "style.tint" in caught.value.problems

    def test_a_tint_shape_is_drawn_in_the_tint_color(self) -> None:
        clean = validate_canvas(canvas(shape_el("s", 0, 0, 60, 200, fill="tint"), tint="#f3ede4"))
        assert "background:#f3ede4" in render_html(clean, font_base="/f/")

    def test_contrast_ratio_is_the_wcag_one(self) -> None:
        assert contrast_ratio("#000000", "#ffffff") == pytest.approx(21.0, rel=0.01)
        assert contrast_ratio("#777777", "#777777") == pytest.approx(1.0)


class TestMeta:
    def test_a_label_is_kept_and_a_bad_one_refused(self) -> None:
        good = text_el(
            "a",
            10,
            10,
            50,
            8,
            None,
            meta={"role": "item", "sec": 1, "idx": 2, "kind": "experience"},
        )
        kept = validate_canvas(canvas(good))["pages"][0]["elements"][0]["meta"]
        assert kept == {"role": "item", "sec": 1, "idx": 2, "kind": "experience"}
        for bad in ({"role": "script"}, {"role": "item", "kind": "x"}, "item"):
            with pytest.raises(ResumeDocError):
                validate_canvas(canvas(text_el("a", 10, 10, 50, 8, None, meta=bad)))

    def test_roles_are_the_ones_a_template_writes(self) -> None:
        assert set(ROLES) == {"name", "headline", "contacts", "title", "item", "dates", "decor"}
