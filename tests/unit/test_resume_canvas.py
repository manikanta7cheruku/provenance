"""The free canvas document: validation, reading order, the HTML, and the CSS shared with the browser."""

import copy
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import pytest
from canvas_helpers import canvas, rich, sample_canvas, shape_el, text_el

from pv_domain.resume_canvas import (
    MAX_ELEMENTS,
    MAX_PAGES,
    blank_canvas,
    canvas_text,
    element_css,
    paint_order,
    reading_order,
    render_canvas_html,
    validate_canvas,
)
from pv_domain.resume_doc import ResumeDocError, document_text, validate_document
from pv_domain.resume_render import FONT_FILES, render_html

GOLDEN = Path(__file__).parent.parent / "fixtures" / "canvas_css_golden.json"


def problems_of(raw: Any) -> dict[str, str]:
    with pytest.raises(ResumeDocError) as raised:
        validate_canvas(raw)
    return raised.value.problems


class TestValidation:
    def test_a_blank_canvas_and_a_sample_are_valid_and_come_back_clean(self) -> None:
        assert validate_canvas(blank_canvas("Asha"))["pages"][0]["elements"][0]["body"] is not None
        clean = validate_canvas(sample_canvas())
        assert [e["id"] for e in clean["pages"][0]["elements"]][:2] == ["name", "headline"]

    def test_the_document_dispatch_sends_version_two_to_the_canvas(self) -> None:
        clean = validate_document(sample_canvas())
        assert clean["version"] == 2 and "pages" in clean
        assert "Asha Rao" in document_text(clean)

    def test_the_input_is_never_changed_and_unknown_keys_are_dropped(self) -> None:
        raw = sample_canvas()
        raw["evil"] = "<script>"
        raw["pages"][0]["elements"][0]["onclick"] = "x"
        before = copy.deepcopy(raw)
        clean = validate_canvas(raw)
        assert raw == before
        assert "evil" not in clean and "onclick" not in clean["pages"][0]["elements"][0]

    @pytest.mark.parametrize("bad", [None, [], "x", 4, {}, {"pages": []}, {"pages": "x"}])
    def test_a_canvas_needs_pages(self, bad: Any) -> None:
        with pytest.raises(ResumeDocError):
            validate_canvas(bad)

    def test_positions_are_rounded_and_must_stay_on_the_page(self) -> None:
        clean = validate_canvas(canvas(text_el("a", 10.123, 20.987, 50.04, 8.0, rich("x"))))
        el = clean["pages"][0]["elements"][0]
        assert (el["x"], el["y"], el["w"]) == (10.1, 21.0, 50.0)
        past_right = problems_of(canvas(text_el("a", 180, 10, 50, 8, rich("x"))))
        assert "right edge" in past_right["pages.0.elements.0.w"]
        past_bottom = problems_of(canvas(shape_el("a", 10, 290, 50, 20)))
        assert "bottom edge" in past_bottom["pages.0.elements.0.h"]
        trimmed = validate_canvas(canvas(text_el("a", 10, 290, 50, 20, rich("x"))))
        assert trimmed["pages"][0]["elements"][0]["h"] == 7.0
        assert problems_of(canvas(text_el("a", -5, 10, 50, 8)))["pages.0.elements.0.x"]
        assert problems_of(canvas(text_el("a", 10, 10, 0, 8)))["pages.0.elements.0.w"]

    def test_the_page_size_follows_the_paper(self) -> None:
        letter = canvas(text_el("a", 10, 270, 50, 9.0, rich("x")), paper="letter")
        assert validate_canvas(letter)
        a4 = canvas(text_el("a", 10, 280, 50, 10.0, rich("x")), paper="a4")
        assert validate_canvas(a4)
        assert problems_of(canvas(text_el("a", 10, 280, 50, 10.0, rich("x")), paper="letter"))

    @pytest.mark.parametrize("value", [float("nan"), "12", True, None])
    def test_numbers_must_be_numbers(self, value: Any) -> None:
        assert problems_of(canvas(text_el("a", value, 10, 50, 8)))

    def test_text_options_are_checked(self) -> None:
        assert problems_of(canvas(text_el("a", 10, 10, 50, 8, size=3)))["pages.0.elements.0.size"]
        assert problems_of(canvas(text_el("a", 10, 10, 50, 8, font="comic")))[
            "pages.0.elements.0.font"
        ]
        assert problems_of(canvas(text_el("a", 10, 10, 50, 8, align="start")))[
            "pages.0.elements.0.align"
        ]
        assert problems_of(canvas(text_el("a", 10, 10, 50, 8, color="red")))[
            "pages.0.elements.0.color"
        ]
        ok = validate_canvas(canvas(text_el("a", 10, 10, 50, 8, color="#AABBCC", caps=True)))
        assert ok["pages"][0]["elements"][0]["color"] == "#aabbcc"

    def test_shape_options_are_checked(self) -> None:
        assert problems_of(canvas(shape_el("s", 10, 10, 50, 5, fill="url(x)")))[
            "pages.0.elements.0.fill"
        ]
        assert problems_of(canvas(shape_el("s", 10, 10, 50, 5, radius=99)))[
            "pages.0.elements.0.radius"
        ]
        assert validate_canvas(
            canvas(shape_el("s", 10, 10, 50, 5, fill="none", stroke="ink", stroke_pt=1))
        )

    def test_rich_text_uses_the_same_whitelist_as_the_flowing_document(self) -> None:
        bad = {"type": "doc", "content": [{"type": "image", "attrs": {"src": "http://evil"}}]}
        assert "pages.0.elements.0.body.0" in problems_of(canvas(text_el("a", 10, 10, 50, 8, bad)))
        link = {
            "type": "doc",
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": "x", "marks": [{"type": "link"}]}],
                }
            ],
        }
        assert problems_of(canvas(text_el("a", 10, 10, 50, 8, link)))

    def test_an_unknown_element_kind_is_refused(self) -> None:
        raw = canvas(text_el("a", 10, 10, 50, 8))
        raw["pages"][0]["elements"].append(
            {"kind": "image", "x": 1, "y": 1, "w": 5, "h": 5, "src": "http://x"}
        )
        assert problems_of(raw)["pages.0.elements.1.kind"]

    def test_ids_are_made_unique_and_bad_ones_replaced(self) -> None:
        raw = canvas(
            text_el("same", 10, 10, 50, 8),
            text_el("same", 10, 30, 50, 8),
            text_el("<b>", 10, 50, 50, 8),
        )
        ids = [e["id"] for e in validate_canvas(raw)["pages"][0]["elements"]]
        assert len(set(ids)) == 3 and "<b>" not in ids

    def test_a_group_of_one_is_set_free_and_a_pair_is_kept(self) -> None:
        raw = canvas(
            text_el("a", 10, 10, 50, 8, group="g1"),
            text_el("b", 10, 30, 50, 8, group="g1"),
            text_el("c", 10, 50, 50, 8, group="lonely"),
        )
        groups = {e["id"]: e["group"] for e in validate_canvas(raw)["pages"][0]["elements"]}
        assert groups == {"a": "g1", "b": "g1", "c": None}

    def test_limits_on_pages_elements_and_text(self) -> None:
        assert problems_of(canvas(pages=MAX_PAGES + 1))["pages"]
        many = canvas(*[text_el(f"e{i}", 10, 10, 20, 5) for i in range(MAX_ELEMENTS + 1)])
        assert "at most" in problems_of(many)["pages"]
        long = canvas(
            *[text_el(f"e{i}", 10, 10 + i * 10, 150, 9, rich("w" * 5000)) for i in range(7)]
        )
        assert "document" in problems_of(long)

    def test_the_style_is_checked(self) -> None:
        raw = canvas(text_el("a", 10, 10, 50, 8))
        raw["style"].update(paper="legal", accent="blue", font_pair="x", margin_mm=99)
        assert set(problems_of(raw)) >= {
            "style.paper",
            "style.accent",
            "style.font_pair",
            "style.margin_mm",
        }


class TestReadingOrder:
    def test_top_to_bottom_then_left_to_right_within_a_row(self) -> None:
        els = [
            text_el("date", 150, 20.5, 40, 5),
            text_el("below", 16, 40, 100, 5),
            text_el("role", 16, 20, 100, 5),
            text_el("top", 16, 5, 100, 5),
        ]
        assert [e["id"] for e in reading_order(els)] == ["top", "role", "date", "below"]

    def test_the_text_of_a_canvas_follows_that_order(self) -> None:
        raw = canvas(
            text_el("b", 16, 60, 100, 5, rich("Second")),
            text_el("a", 16, 20, 100, 5, rich("First")),
            shape_el("rule", 16, 40, 100, 0.4),
        )
        assert canvas_text(validate_canvas(raw)) == "First\nSecond"


class Tags(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tags: list[str] = []
        self.attrs: list[tuple[str, str | None]] = []
        self.ids: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append(tag)
        self.attrs += attrs


class TestHtml:
    def doc(self) -> dict[str, Any]:
        return validate_canvas(sample_canvas())

    def test_a_box_added_last_is_still_read_in_page_order_when_nothing_overlaps(self) -> None:
        raw = canvas(
            text_el("last", 16, 120, 100, 5, rich("THIRD")),
            text_el("first", 16, 20, 100, 5, rich("FIRST")),
            text_el("middle", 16, 70, 100, 5, rich("SECOND")),
        )
        html = render_canvas_html(validate_canvas(raw), font_base="/f/")
        assert html.index("<p>FIRST</p>") < html.index("<p>SECOND</p>") < html.index("<p>THIRD</p>")
        zs = [int(z) for z in re.findall(r"z-index:(\d+)", html)]
        assert zs == sorted(zs) == [1, 2, 3]

    def test_overlapping_boxes_keep_their_stacking(self) -> None:
        # The shape is added after the text, so it is on top of it, although the text reads first.
        raw = canvas(
            text_el("t", 20, 20, 60, 6, rich("COVERED")),
            shape_el("s", 16, 18, 100, 20, fill="white"),
        )
        html = render_canvas_html(validate_canvas(raw), font_base="/f/")
        assert html.index("COVERED") < html.index('class="el" style=')
        order = [e["id"] for e in paint_order(validate_canvas(raw)["pages"][0]["elements"])]
        assert order == ["t", "s"]
        flipped = canvas(
            shape_el("s", 16, 18, 100, 20), text_el("t", 20, 20, 60, 6, rich("ON TOP"))
        )
        assert [e["id"] for e in paint_order(validate_canvas(flipped)["pages"][0]["elements"])] == [
            "s",
            "t",
        ]

    def test_the_paint_order_is_stable_and_complete(self) -> None:
        els = validate_canvas(sample_canvas())["pages"][0]["elements"]
        assert sorted(e["id"] for e in paint_order(els)) == sorted(e["id"] for e in els)
        assert [e["id"] for e in paint_order(els)] == [e["id"] for e in paint_order(els)]

    def test_hostile_text_is_escaped_and_only_known_tags_and_attributes_appear(self) -> None:
        raw = canvas(
            text_el("a", 10, 10, 100, 8, rich("<script>alert(1)</script><img src=x onerror=1>"))
        )
        raw["pages"][0]["elements"][0]["name"] = '"><svg onload=1>'
        html = render_canvas_html(validate_canvas(raw), font_base="/f/")
        parser = Tags()
        parser.feed(html)
        assert "<script" not in html and "<img" not in html and "<svg" not in html
        assert set(parser.tags) <= {
            "html",
            "head",
            "meta",
            "title",
            "style",
            "body",
            "section",
            "div",
            "p",
            "ul",
            "ol",
            "li",
            "strong",
            "em",
            "u",
            "mark",
            "br",
        }
        assert {name for name, _ in parser.attrs} <= {"lang", "charset", "class", "style"}

    def test_the_only_addresses_are_the_shipped_fonts(self) -> None:
        html = render_canvas_html(self.doc(), font_base="/api/v1/studio/fonts/")
        import re

        urls = re.findall(r'url\("([^"]+)"\)', html)
        assert {u.rsplit("/", 1)[1] for u in urls} == set(FONT_FILES.values())
        assert "http://" not in html and "https://" not in html

    def test_print_sets_the_page_and_preview_draws_sheets(self) -> None:
        doc = self.doc()
        printed = render_canvas_html(doc, font_base="/f/")
        preview = render_canvas_html(doc, font_base="/f/", preview=True)
        assert "@page{size:210mm 297mm;margin:0}" in printed and "box-shadow" not in printed
        assert "box-shadow" in preview and "@page" not in preview

    def test_every_page_is_a_section_and_the_paper_is_used(self) -> None:
        doc = validate_canvas(
            canvas(text_el("a", 10, 10, 50, 8, rich("x")), pages=2, paper="letter")
        )
        html = render_canvas_html(doc, font_base="/f/")
        assert html.count('<section class="page">') == 2 and "size:215.9mm 279.4mm" in html

    def test_the_title_comes_from_the_first_text(self) -> None:
        assert "<title>Asha Rao - Resume</title>" in render_canvas_html(self.doc(), font_base="/f/")

    def test_render_html_dispatches_by_version(self) -> None:
        assert 'class="page"' in render_html(self.doc(), font_base="/f/")


class TestSharedCss:
    """The browser must draw each element with exactly these declarations (css.ts checks the same file)."""

    CASES = [
        ("text, body", text_el("t1", 16, 55, 140, 16, rich("x"))),
        (
            "text, heading caps accent",
            text_el(
                "t2", 16, 46, 178, 5, rich("x"), font="heading", size=11, color="accent", caps=True
            ),
        ),
        (
            "text, right aligned hex",
            text_el(
                "t3",
                158.55,
                55.25,
                36,
                5,
                rich("x"),
                align="right",
                size=9.5,
                color="#7a1f3d",
                line_height=1.5,
            ),
        ),
        ("shape, rule", shape_el("s1", 16, 52, 178, 0.4)),
        (
            "shape, outline and radius",
            shape_el("s2", 20, 100, 60, 30, fill="none", stroke="ink", stroke_pt=1.5, radius=3),
        ),
    ]

    # The same element drawn with another palette and another font pair.
    PALETTE = {
        "font_pair": "playfair-source",
        "accent": "#7a1f3d",
        "ink": "#222a35",
        "muted": "#555b66",
        "tint": "#f3ede4",
    }
    STYLED = [
        (
            "palette, heading in accent",
            text_el("p1", 16, 20, 100, 8, rich("x"), font="heading", color="accent"),
        ),
        ("palette, grey text", text_el("p2", 16, 30, 100, 8, rich("x"), color="muted")),
        ("palette, tint shape", shape_el("p3", 0, 0, 70, 297, fill="tint")),
    ]

    def build(self) -> list[dict[str, Any]]:
        style = validate_canvas(canvas(text_el("a", 1, 1, 5, 5)))["style"]
        styled = validate_canvas(canvas(text_el("a", 1, 1, 5, 5), **self.PALETTE))["style"]
        cases = [(n, e, style) for n, e in self.CASES] + [(n, e, styled) for n, e in self.STYLED]
        out = []
        for index, (name, el, style) in enumerate(cases, start=1):
            cleaned = validate_canvas(
                canvas(el, **{k: style[k] for k in style if k != "template"})
            )["pages"][0]["elements"][0]
            out.append(
                {
                    "name": name,
                    "style": style,
                    "element": cleaned,
                    "z": index,
                    "css": element_css(cleaned, style, index),
                }
            )
        return out

    def test_the_golden_file_matches_what_the_server_produces(self) -> None:
        assert json.loads(GOLDEN.read_text(encoding="utf-8")) == self.build(), (
            "css.ts and the server must agree. If this change is intended, regenerate "
            "tests/fixtures/canvas_css_golden.json with scripts/write_canvas_golden.py and update css.ts."
        )
