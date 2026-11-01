"""Builders for canvas documents, shared by the canvas tests."""

from typing import Any

from pv_domain.resume_canvas import blank_canvas, default_canvas_style, validate_canvas


def rich(text: str, *marks: str) -> dict[str, Any]:
    node: dict[str, Any] = {"type": "text", "text": text}
    if marks:
        node["marks"] = [{"type": m} for m in marks]
    return {"type": "doc", "content": [{"type": "paragraph", "content": [node]}]}


def text_el(
    el_id: str,
    x: float,
    y: float,
    w: float,
    h: float,
    body: dict[str, Any] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": el_id, "kind": "text", "name": el_id, "x": x, "y": y, "w": w, "h": h, "locked": False,
        "group": None, "body": body, "font": "body", "size": 10.5, "color": "ink", "align": "left",
        "line_height": 1.3, "caps": False,
    }  # fmt: skip
    base.update(extra)
    return base


def shape_el(el_id: str, x: float, y: float, w: float, h: float, **extra: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": el_id, "kind": "shape", "name": el_id, "x": x, "y": y, "w": w, "h": h, "locked": False,
        "group": None, "fill": "accent", "stroke": "none", "stroke_pt": 0.0, "radius": 0.0,
    }  # fmt: skip
    base.update(extra)
    return base


def canvas(*elements: dict[str, Any], pages: int = 1, **style: Any) -> dict[str, Any]:
    st = default_canvas_style()
    st.update(style)
    doc = {
        "version": 2,
        "style": st,
        "pages": [
            {"id": f"p{i}", "elements": list(elements) if i == 0 else []} for i in range(pages)
        ],
    }
    return doc


def sample_canvas(name: str = "Asha Rao") -> dict[str, Any]:
    """A realistic page: a name and a right-aligned date row, two sections, a rule, bullets."""
    bullets = {
        "type": "doc",
        "content": [
            {
                "type": "bulletList",
                "content": [
                    {
                        "type": "listItem",
                        "content": [
                            {"type": "paragraph", "content": [{"type": "text", "text": line}]}
                        ],
                    }
                    for line in (
                        "Cleaned six CSV sources with pandas",
                        "Wrote SQL joins over 1.2 million rows",
                    )
                ],
            }
        ],
    }
    doc = canvas(
        text_el(
            "name",
            16,
            16,
            178,
            11,
            rich(name),
            font="heading",
            size=26,
            color="accent",
            line_height=1.1,
        ),
        text_el("headline", 16, 29, 178, 6, rich("Data analyst"), size=11),
        text_el(
            "contacts",
            16,
            36,
            178,
            5,
            rich("asha@example.com | Bengaluru, India"),
            size=9.5,
            color="muted",
        ),
        text_el(
            "h1",
            16,
            46,
            178,
            5,
            rich("Experience"),
            font="heading",
            size=11,
            color="accent",
            caps=True,
        ),
        shape_el("rule1", 16, 52, 178, 0.4),
        text_el("role", 16, 55, 140, 16, rich("Data Intern, Kestrel Analytics", "bold")),
        text_el(
            "dates",
            158,
            55,
            36,
            5,
            rich("2025-06 to 2025-08"),
            align="right",
            size=9.5,
            color="muted",
        ),
        text_el("bullets", 16, 61, 178, 14, bullets),
    )
    return validate_canvas(doc) if False else doc


def new_blank(name: str = "") -> dict[str, Any]:
    return blank_canvas(name)
