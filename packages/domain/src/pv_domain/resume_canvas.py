"""The free canvas resume: pages of positioned boxes, validated and drawn on the server.

Version 2 of the resume document (version 1 is the flowing, structured one in resume_doc). A page is
a list of elements. An element is a box in millimetres (x, y, w, h) with a kind:
  text   rich text (the same rules as version 1), a font role, a size, a color, an alignment
  shape  a filled or outlined rectangle. A rule is just a shape that is thin.

The browser draws the page from the same data, so typing and dragging need no server round trip.
This module is what the server trusts: every save passes validate_canvas, which returns a clean
copy or refuses with a sentence for each problem. Nothing here stores markup. The PDF is drawn from
render_canvas_html, which positions each box with absolute CSS in millimetres and writes the boxes
in reading order (top to bottom, then left to right) whatever their stacking order is.

The CSS for one element is produced by element_css and mirrored in the browser by css.ts. A shared
golden file (tests/fixtures/canvas_css_golden.json) is checked by both, so the two cannot drift.
"""

import re
from html import escape
from typing import Any

from pv_domain.resume_doc import (
    FONT_PAIRS,
    MAX_TEXT_CHARS,
    PAPERS,
    ResumeDocError,
    clean_rich,
    new_id,
    rich_to_text,
)
from pv_domain.resume_render import FONT_PAIRS as FONT_FAMILIES
from pv_domain.resume_render import font_faces, render_rich_nodes

CANVAS_VERSION = 2

PAGE_MM = {"a4": (210.0, 297.0), "letter": (215.9, 279.4)}
MAX_PAGES = 3
MAX_ELEMENTS = 150
MAX_ELEMENT_NAME = 60
MIN_SIZE_MM = 0.2
EDGE_TOLERANCE_MM = 0.05
# Two elements whose tops differ by less than this are read as being on the same row.
ROW_BAND_MM = 3.0

KINDS = ("text", "shape")
FONT_ROLES = ("heading", "body")
ALIGNS = ("left", "center", "right", "justify")
COLOR_TOKENS = ("ink", "muted", "accent", "white", "none")
INK = "#1b1b1b"
MUTED = "#4a4a4a"
_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
_ID = re.compile(r"^[A-Za-z0-9_-]{1,40}$")

SIZE_PT = (5.0, 72.0)
LINE_HEIGHT = (0.9, 2.5)
STROKE_PT = (0.0, 12.0)
RADIUS_MM = (0.0, 30.0)
MARGIN_MM = (0.0, 40.0)
COORD_DECIMALS = 1


def page_size(style: dict[str, Any]) -> tuple[float, float]:
    return PAGE_MM[style["paper"]]


def default_canvas_style(template: str = "free") -> dict[str, Any]:
    return {
        "template": template,
        "font_pair": "plex-newsreader",
        "accent": "#1f3d7a",
        "paper": "a4",
        "margin_mm": 16.0,
    }


def blank_canvas(name: str = "") -> dict[str, Any]:
    """A first page with a name, a headline line and a rule, so the page is never empty."""
    style = default_canvas_style()
    width = PAGE_MM[style["paper"]][0] - 2 * style["margin_mm"]

    def text(
        el_id: str, y: float, h: float, label: str, content: str, size: float, font: str, color: str
    ) -> dict[str, Any]:
        body = (
            {
                "type": "doc",
                "content": [{"type": "paragraph", "content": [{"type": "text", "text": content}]}],
            }
            if content
            else None
        )
        return {
            "id": el_id, "kind": "text", "name": label, "x": style["margin_mm"], "y": y, "w": width, "h": h,
            "locked": False, "group": None, "body": body, "font": font, "size": size, "color": color,
            "align": "left", "line_height": 1.25, "caps": False,
        }  # fmt: skip

    return {
        "version": CANVAS_VERSION,
        "style": style,
        "pages": [
            {
                "id": new_id(),
                "elements": [
                    text(new_id(), 16.0, 12.0, "Name", name, 26.0, "heading", "accent"),
                    text(new_id(), 29.0, 6.0, "Headline", "", 11.0, "body", "ink"),
                    {
                        "id": new_id(), "kind": "shape", "name": "Rule", "x": style["margin_mm"], "y": 37.0,
                        "w": width, "h": 0.4, "locked": False, "group": None, "fill": "accent",
                        "stroke": "none", "stroke_pt": 0.0, "radius": 0.0,
                    },
                ],
            }
        ],
    }  # fmt: skip


# ---- validation


def _number(
    value: Any, low: float, high: float, path: str, problems: dict[str, str], what: str
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value != value:
        problems[path] = f"{what} must be a number."
        return low
    if value < low or value > high:
        problems[path] = f"{what} must be between {low:g} and {high:g}."
        return min(max(float(value), low), high)
    return float(value)


def _color(value: Any, path: str, problems: dict[str, str], allow_none: bool) -> str:
    allowed = COLOR_TOKENS if allow_none else tuple(t for t in COLOR_TOKENS if t != "none")
    if isinstance(value, str) and (value in allowed or _HEX.match(value)):
        return value.lower() if value.startswith("#") else value
    problems[path] = "Choose a color from the list or use a code like #1f3d7a."
    return "ink" if not allow_none else "none"


def _string(value: Any, limit: int, path: str, problems: dict[str, str]) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        problems[path] = "This should be text."
        return ""
    cleaned = "".join(ch for ch in value if ch >= " " and ch != "\x7f").strip()
    if len(cleaned) > limit:
        problems[path] = f"This is too long. Keep it under {limit} characters."
        return cleaned[:limit]
    return cleaned


def _clean_style(raw: Any, problems: dict[str, str]) -> dict[str, Any]:
    style = default_canvas_style()
    if raw is None:
        return style
    if not isinstance(raw, dict):
        problems["style"] = "The style is not valid."
        return style
    if "template" in raw:
        style["template"] = _string(raw["template"], 40, "style.template", problems) or "free"
    if "font_pair" in raw:
        if raw["font_pair"] in FONT_PAIRS:
            style["font_pair"] = raw["font_pair"]
        else:
            problems["style.font_pair"] = "Choose one of the options shown."
    if "paper" in raw:
        if raw["paper"] in PAPERS:
            style["paper"] = raw["paper"]
        else:
            problems["style.paper"] = "Choose one of the options shown."
    if "accent" in raw:
        if isinstance(raw["accent"], str) and _HEX.match(raw["accent"]):
            style["accent"] = raw["accent"].lower()
        else:
            problems["style.accent"] = "Use a color like #1f3d7a."
    if "margin_mm" in raw:
        style["margin_mm"] = round(
            _number(raw["margin_mm"], *MARGIN_MM, "style.margin_mm", problems, "The margin"), 1
        )
    return style


def _clean_element(
    raw: Any, path: str, problems: dict[str, str], page_w: float, page_h: float, used: set[str]
) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        problems[path] = "This element is not valid."
        return None
    kind = raw.get("kind")
    if kind not in KINDS:
        problems[f"{path}.kind"] = "That kind of element is not available."
        return None
    raw_id = raw.get("id")
    el_id = (
        raw_id if isinstance(raw_id, str) and _ID.match(raw_id) and raw_id not in used else new_id()
    )
    used.add(el_id)
    raw_group = raw.get("group")
    group = raw_group if isinstance(raw_group, str) and _ID.match(raw_group) else None

    x = _number(raw.get("x"), 0.0, page_w, f"{path}.x", problems, "The left position")
    y = _number(raw.get("y"), 0.0, page_h, f"{path}.y", problems, "The top position")
    w = _number(raw.get("w"), MIN_SIZE_MM, page_w, f"{path}.w", problems, "The width")
    h = _number(raw.get("h"), MIN_SIZE_MM, page_h, f"{path}.h", problems, "The height")
    if x + w > page_w + EDGE_TOLERANCE_MM:
        problems[f"{path}.w"] = "This box goes past the right edge of the page."
    if kind == "shape" and y + h > page_h + EDGE_TOLERANCE_MM:
        problems[f"{path}.h"] = "This box goes past the bottom edge of the page."
    if kind == "text":
        # A text box is as tall as its text. The browser measures that, so a long text may reach
        # past the page. The height is a minimum, so it is trimmed to the page instead of refused.
        h = min(h, max(page_h - y, MIN_SIZE_MM))

    out: dict[str, Any] = {
        "id": el_id,
        "kind": kind,
        "name": _string(raw.get("name"), MAX_ELEMENT_NAME, f"{path}.name", problems),
        "x": round(x, COORD_DECIMALS),
        "y": round(y, COORD_DECIMALS),
        "w": round(w, COORD_DECIMALS),
        "h": round(h, COORD_DECIMALS),
        "locked": raw.get("locked") is True,
        "group": group,
    }
    if kind == "text":
        font = raw.get("font", "body")
        align = raw.get("align", "left")
        if font not in FONT_ROLES:
            problems[f"{path}.font"] = "Choose one of the options shown."
            font = "body"
        if align not in ALIGNS:
            problems[f"{path}.align"] = "Choose one of the options shown."
            align = "left"
        out.update(
            body=clean_rich(raw.get("body"), f"{path}.body", problems),
            font=font,
            size=round(
                _number(raw.get("size", 10.5), *SIZE_PT, f"{path}.size", problems, "The text size"),
                1,
            ),
            color=_color(raw.get("color", "ink"), f"{path}.color", problems, allow_none=False),
            align=align,
            line_height=round(
                _number(
                    raw.get("line_height", 1.3),
                    *LINE_HEIGHT,
                    f"{path}.line_height",
                    problems,
                    "The line height",
                ),
                2,
            ),
            caps=raw.get("caps") is True,
        )
    else:
        out.update(
            fill=_color(raw.get("fill", "none"), f"{path}.fill", problems, allow_none=True),
            stroke=_color(raw.get("stroke", "none"), f"{path}.stroke", problems, allow_none=True),
            stroke_pt=round(
                _number(
                    raw.get("stroke_pt", 0.0),
                    *STROKE_PT,
                    f"{path}.stroke_pt",
                    problems,
                    "The outline width",
                ),
                2,
            ),
            radius=round(
                _number(
                    raw.get("radius", 0.0),
                    *RADIUS_MM,
                    f"{path}.radius",
                    problems,
                    "The corner radius",
                ),
                1,
            ),
        )
    return out


def validate_canvas(raw: Any) -> dict[str, Any]:
    """A clean copy of a canvas document, or ResumeDocError saying what is wrong and where."""
    problems: dict[str, str] = {}
    if not isinstance(raw, dict):
        raise ResumeDocError({"document": "The resume is not valid."})
    style = _clean_style(raw.get("style"), problems)
    page_w, page_h = PAGE_MM[style["paper"]]

    pages_raw = raw.get("pages")
    if not isinstance(pages_raw, list) or not pages_raw:
        raise ResumeDocError({"pages": "A resume needs at least one page."})
    if len(pages_raw) > MAX_PAGES:
        problems["pages"] = f"Use at most {MAX_PAGES} pages."
    used: set[str] = set()
    pages: list[dict[str, Any]] = []
    total = 0
    for pi, page in enumerate(pages_raw[:MAX_PAGES]):
        path = f"pages.{pi}"
        if not isinstance(page, dict):
            problems[path] = "This page is not valid."
            continue
        raw_id = page.get("id")
        page_id = (
            raw_id
            if isinstance(raw_id, str) and _ID.match(raw_id) and raw_id not in used
            else new_id()
        )
        used.add(page_id)
        elements_raw = page.get("elements") or []
        if not isinstance(elements_raw, list):
            problems[f"{path}.elements"] = "The elements are not valid."
            elements_raw = []
        elements: list[dict[str, Any]] = []
        for ei, el in enumerate(elements_raw):
            cleaned = _clean_element(el, f"{path}.elements.{ei}", problems, page_w, page_h, used)
            if cleaned is not None:
                elements.append(cleaned)
        total += len(elements)
        # A group needs two members. A lone member is set free.
        counts: dict[str, int] = {}
        for el in elements:
            if el["group"]:
                counts[el["group"]] = counts.get(el["group"], 0) + 1
        for el in elements:
            if el["group"] and counts[el["group"]] < 2:
                el["group"] = None
        pages.append({"id": page_id, "elements": elements})
    if total > MAX_ELEMENTS:
        problems["pages"] = f"Use at most {MAX_ELEMENTS} elements in total."

    document = {"version": CANVAS_VERSION, "style": style, "pages": pages}
    if len(canvas_text(document)) > MAX_TEXT_CHARS:
        problems["document"] = (
            f"The resume is too long. Keep it under {MAX_TEXT_CHARS:,} characters."
        )
    if problems:
        raise ResumeDocError(problems)
    return document


# ---- reading order and text


def _overlap(a: dict[str, Any], b: dict[str, Any]) -> bool:
    across = a["x"] < b["x"] + b["w"] and b["x"] < a["x"] + a["w"]
    down = a["y"] < b["y"] + b["h"] and b["y"] < a["y"] + a["h"]
    return bool(across and down)


def paint_order(elements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The order to draw the elements in, which is also the order a PDF reader meets their text.

    A PDF keeps text in the order it was drawn, so drawing in stacking order would make a box that
    was added last read last, wherever it sits on the page. Stacking only changes what is seen where
    two boxes overlap, so only those pairs are held to the stored order (the one added later goes on
    top). Every other pair follows reading order. The picture is identical and the text order is the
    one a person reads.
    """
    key = {e["id"]: i for i, e in enumerate(reading_order(elements))}
    below: dict[str, set[str]] = {
        e["id"]: set() for e in elements
    }  # id -> ids that must be drawn first
    for i, low in enumerate(elements):
        for high in elements[i + 1 :]:
            if _overlap(low, high):
                below[high["id"]].add(low["id"])
    done: list[dict[str, Any]] = []
    placed: set[str] = set()
    remaining = sorted(elements, key=lambda e: key[e["id"]])
    while remaining:
        pick = next(e for e in remaining if below[e["id"]] <= placed)
        remaining.remove(pick)
        placed.add(pick["id"])
        done.append(pick)
    return done


def reading_order(elements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Top to bottom, then left to right. Elements within a few millimetres of each other in height
    count as one row. This is the order a PDF reader or an applicant tracking system will meet them."""
    return sorted(elements, key=lambda e: (int(e["y"] // ROW_BAND_MM), e["x"], e["y"]))


def canvas_text(doc: dict[str, Any]) -> str:
    parts: list[str] = []
    for page in doc["pages"]:
        for el in reading_order(page["elements"]):
            if el["kind"] == "text":
                text = rich_to_text(el["body"])
                if text:
                    parts.append(text)
    return "\n".join(parts)


# ---- drawing


def resolve_color(value: str, style: dict[str, Any]) -> str:
    if value == "ink":
        return INK
    if value == "muted":
        return MUTED
    if value == "accent":
        return str(style["accent"])
    if value == "white":
        return "#ffffff"
    if value == "none":
        return "transparent"
    return value


def _mm(value: float) -> str:
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return f"{text or '0'}mm"


def element_css(el: dict[str, Any], style: dict[str, Any], z: int) -> dict[str, str]:
    """The CSS declarations of one element, as a dict. css.ts must return the same."""
    css: dict[str, str] = {
        "position": "absolute",
        "left": _mm(el["x"]),
        "top": _mm(el["y"]),
        "width": _mm(el["w"]),
        "z-index": str(z),
    }
    if el["kind"] == "text":
        heading, body = FONT_FAMILIES[style["font_pair"]]
        css.update(
            {
                "min-height": _mm(el["h"]),
                "font-family": heading if el["font"] == "heading" else body,
                "font-size": f"{el['size']:g}pt",
                "line-height": f"{el['line_height']:g}",
                "color": resolve_color(el["color"], style),
                "text-align": el["align"],
            }
        )
        if el["caps"]:
            css["text-transform"] = "uppercase"
            css["letter-spacing"] = "0.06em"
    else:
        css["height"] = _mm(el["h"])
        css["background"] = resolve_color(el["fill"], style)
        if el["stroke"] != "none" and el["stroke_pt"] > 0:
            css["border"] = f"{el['stroke_pt']:g}pt solid {resolve_color(el['stroke'], style)}"
        if el["radius"] > 0:
            css["border-radius"] = _mm(el["radius"])
    return css


def _style_attr(css: dict[str, str]) -> str:
    # Font names carry double quotes, so the whole value is escaped for use inside an attribute.
    return escape(";".join(f"{k}:{v}" for k, v in css.items()), quote=True)


_BASE_CSS = """
html{-webkit-text-size-adjust:100%}
body{margin:0;color:#1b1b1b}
.page{position:relative;overflow:hidden;background:#fff;box-sizing:border-box}
.el{position:absolute;box-sizing:border-box;margin:0}
.t{overflow-wrap:break-word}
.t p{margin:0}
.t p+p{margin-top:0.4em}
.t ul,.t ol{list-style:none;padding-left:1.5mm;margin:0.4mm 0 0}
.t ol{counter-reset:item}
.t li{display:flex;gap:1.8mm;margin-top:0.3mm}
.t li>p{flex:1;min-width:0}
.t ul>li::before{content:"\\2022";flex:none}
.t ol>li{counter-increment:item}
.t ol>li::before{content:counter(item) ".";flex:none;min-width:3.2mm;text-align:right}
.t strong{font-weight:600}
.t mark{background:#fff1a8;color:inherit;padding:0 .4mm}
.t u{text-decoration:underline;text-underline-offset:1pt}
"""


def render_canvas_html(doc: dict[str, Any], *, font_base: str, preview: bool = False) -> str:
    """The pages as HTML. Stacking uses z-index from the stored order, while the HTML itself is in
    reading order. The document must already have passed validate_canvas."""
    style = doc["style"]
    page_w, page_h = PAGE_MM[style["paper"]]
    sheet = (
        f"@page{{size:{_mm(page_w)} {_mm(page_h)};margin:0}}"
        f".page{{width:{_mm(page_w)};height:{_mm(page_h)};break-after:page}}"
        ".page:last-child{break-after:auto}"
    )
    if preview:
        sheet = (
            f".page{{width:{_mm(page_w)};height:{_mm(page_h)};margin:8px auto;"
            "box-shadow:0 1px 6px rgba(0,0,0,.25)}body{background:#e9e9e6}"
        )
    parts: list[str] = []
    for page in doc["pages"]:
        boxes: list[str] = []
        for z, el in enumerate(paint_order(page["elements"]), start=1):
            css = _style_attr(element_css(el, style, z))
            if el["kind"] == "text":
                inner = render_rich_nodes(el["body"])
                boxes.append(f'<div class="el t" style="{css}">{inner}</div>')
            else:
                boxes.append(f'<div class="el" style="{css}"></div>')
        parts.append(f'<section class="page">{"".join(boxes)}</section>')
    first_page = reading_order(doc["pages"][0]["elements"])
    name = next(
        (
            rich_to_text(el["body"]).splitlines()[0]
            for el in first_page
            if el["kind"] == "text" and el["body"]
        ),
        "",
    )
    title = f"{name} - Resume" if name else "Resume"
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        f"<title>{escape(title)}</title>"
        f"<style>{font_faces(font_base)}\n{_BASE_CSS}\n{sheet}</style></head><body>"
        + "".join(parts)
        + "</body></html>"
    )
