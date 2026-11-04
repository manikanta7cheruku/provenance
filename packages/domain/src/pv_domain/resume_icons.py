"""The icons a resume may carry, as plain drawing instructions.

Each icon is a short list of shapes on a 24 by 24 grid, drawn as an outline. They are data, not
files: nothing is uploaded, no markup is stored in a document, and the same shapes are drawn by the
server for the PDF and by the browser for the page (tests/fixtures/canvas_icons_golden.json is
checked by both). Brand logos are left out on purpose: they are trademarks and change.

An icon is decoration. It never carries information that is not also written in words next to it.
"""

from typing import Any

# Each shape is a dict with "t" (path, circle, rect or polyline) and its own numbers.
ICON_DATA: dict[str, list[dict[str, Any]]] = {
    "mail": [
        {"t": "rect", "x": 3, "y": 5, "w": 18, "h": 14, "rx": 2},
        {"t": "polyline", "points": "3,7 12,13 21,7"},
    ],
    "phone": [
        {
            "t": "path",
            "d": "M6.6 3h3l1.6 4-2 1.4a11 11 0 0 0 5.4 5.4l1.4-2 4 1.6v3a2 2 0 0 1-2.2 2A16 16 0 0 1 4.6 5.2 2 2 0 0 1 6.6 3z",
        }
    ],
    "pin": [
        {"t": "path", "d": "M12 21s7-6.2 7-11.5A7 7 0 0 0 5 9.5C5 14.8 12 21 12 21z"},
        {"t": "circle", "cx": 12, "cy": 9.5, "r": 2.5},
    ],
    "globe": [
        {"t": "circle", "cx": 12, "cy": 12, "r": 9},
        {"t": "path", "d": "M3 12h18"},
        {
            "t": "path",
            "d": "M12 3c2.8 2.6 4.2 5.6 4.2 9S14.8 18.4 12 21c-2.8-2.6-4.2-5.6-4.2-9S9.2 5.6 12 3z",
        },
    ],
    "link": [
        {"t": "path", "d": "M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1"},
        {"t": "path", "d": "M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"},
    ],
    "calendar": [
        {"t": "rect", "x": 3, "y": 5, "w": 18, "h": 16, "rx": 2},
        {"t": "path", "d": "M3 10h18M8 3v4M16 3v4"},
    ],
    "briefcase": [
        {"t": "rect", "x": 3, "y": 7, "w": 18, "h": 13, "rx": 2},
        {"t": "path", "d": "M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2M3 13h18"},
    ],
    "graduation": [
        {"t": "path", "d": "M2 9l10-5 10 5-10 5z"},
        {"t": "path", "d": "M6 11.5V16c0 1.4 2.7 3 6 3s6-1.6 6-3v-4.5"},
    ],
    "code": [
        {"t": "polyline", "points": "8,8 4,12 8,16"},
        {"t": "polyline", "points": "16,8 20,12 16,16"},
        {"t": "path", "d": "M13.5 6l-3 12"},
    ],
    "award": [
        {"t": "circle", "cx": 12, "cy": 9, "r": 5},
        {"t": "path", "d": "M8.5 13.5L7 21l5-3 5 3-1.5-7.5"},
    ],
    "user": [
        {"t": "circle", "cx": 12, "cy": 8, "r": 4},
        {"t": "path", "d": "M4 21c0-4.4 3.6-7 8-7s8 2.6 8 7"},
    ],
    "star": [
        {"t": "path", "d": "M12 3l2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1L3.2 9.5l6.1-.9z"}
    ],
    "check": [{"t": "polyline", "points": "4,12.5 9.5,18 20,6.5"}],
    "arrow": [{"t": "path", "d": "M4 12h16M14 6l6 6-6 6"}],
    "building": [
        {"t": "rect", "x": 5, "y": 3, "w": 14, "h": 18, "rx": 1},
        {"t": "path", "d": "M9 7h2M13 7h2M9 11h2M13 11h2M9 15h2M13 15h2"},
    ],
    "chat": [{"t": "path", "d": "M4 5h16v11H9l-5 4z"}],
}

ICON_NAMES = tuple(ICON_DATA)
ICON_LABELS = {
    "mail": "Email",
    "phone": "Phone",
    "pin": "Place",
    "globe": "Website",
    "link": "Link",
    "calendar": "Date",
    "briefcase": "Work",
    "graduation": "Education",
    "code": "Code",
    "award": "Award",
    "user": "Person",
    "star": "Star",
    "check": "Check",
    "arrow": "Arrow",
    "building": "Company",
    "chat": "Message",
}
WEIGHTS = {1: 1.25, 2: 1.75, 3: 2.25}  # the line weight of an icon, in units of its 24 grid
DEFAULT_WEIGHT = 2


def _num(value: float) -> str:
    text = f"{value:g}"
    return text


def _shape(shape: dict[str, Any]) -> str:
    kind = shape["t"]
    if kind == "path":
        return f'<path d="{shape["d"]}"/>'
    if kind == "polyline":
        return f'<polyline points="{shape["points"]}"/>'
    if kind == "circle":
        return f'<circle cx="{_num(shape["cx"])}" cy="{_num(shape["cy"])}" r="{_num(shape["r"])}"/>'
    return (
        f'<rect x="{_num(shape["x"])}" y="{_num(shape["y"])}" width="{_num(shape["w"])}" '
        f'height="{_num(shape["h"])}" rx="{_num(shape.get("rx", 0))}"/>'
    )


def icon_svg(name: str, weight: int = DEFAULT_WEIGHT) -> str:
    """The icon as an inline SVG that takes its color from the text color around it (currentColor)."""
    shapes = "".join(_shape(s) for s in ICON_DATA[name])
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="100%" height="100%" '
        'fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" '
        f'stroke-width="{_num(WEIGHTS[weight])}" focusable="false">{shapes}</svg>'
    )
