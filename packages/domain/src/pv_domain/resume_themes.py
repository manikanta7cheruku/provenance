"""Saved themes: a named set of fonts and colors a person reuses across resumes.

A theme is the look and nothing else: a font pair and four colors (the accent, the text, the grey
and a soft tint). It holds no words and no pictures, so applying one never changes what a resume
says. Every theme goes through the same rules as the colors in a resume (hex codes, text readable
on white, a tint that the text stays readable on), so a saved theme can never make a resume
unreadable.
"""

from dataclasses import dataclass
from typing import Any

from pv_domain.resume_canvas import clean_style
from pv_domain.resume_doc import FONT_PAIRS

MAX_THEMES_PER_USER = 20
NAME_MAX = 40
THEME_KEYS = ("font_pair", "accent", "ink", "muted", "tint")


@dataclass(frozen=True)
class ThemeData:
    name: str
    font_pair: str
    accent: str
    ink: str
    muted: str
    tint: str


def tidy_name(value: Any) -> str:
    """One line, single spaces, no control characters."""
    if not isinstance(value, str):
        return ""
    cleaned = "".join(" " if ch in "\t\r\n" else ch for ch in value if ch >= " " or ch in "\t\r\n")
    return " ".join(cleaned.replace("\x7f", "").split())


def clean_theme(raw: Any) -> tuple[ThemeData | None, dict[str, str]]:
    """Check a theme from outside. Returns the clean theme, or None and a message per field."""
    problems: dict[str, str] = {}
    if not isinstance(raw, dict):
        return None, {"theme": "The theme is not valid."}
    name = tidy_name(raw.get("name"))
    if not name:
        problems["name"] = "Give the theme a name."
    elif len(name) > NAME_MAX:
        problems["name"] = f"Keep the name under {NAME_MAX} characters."
    for key in THEME_KEYS:
        if key not in raw:
            problems[key] = "This is needed."
    if problems:
        return None, problems
    style_problems: dict[str, str] = {}
    style = clean_style({key: raw[key] for key in THEME_KEYS}, style_problems)
    for path, message in style_problems.items():
        problems[path.removeprefix("style.")] = message
    if problems:
        return None, problems
    if style["font_pair"] not in FONT_PAIRS:  # pragma: no cover - clean_style already checks
        return None, {"font_pair": "Choose one of the options shown."}
    return (
        ThemeData(
            name=name,
            font_pair=style["font_pair"],
            accent=style["accent"],
            ink=style["ink"],
            muted=style["muted"],
            tint=style["tint"],
        ),
        {},
    )
