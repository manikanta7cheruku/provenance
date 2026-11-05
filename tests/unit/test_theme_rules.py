"""Checkpoint 2.13: the rules a saved theme must follow. They are the rules the colors of a resume
follow, so a saved theme can never make a resume unreadable."""

from typing import Any

import pytest

from pv_domain.resume_doc import FONT_PAIRS
from pv_domain.resume_themes import NAME_MAX, clean_theme, tidy_name

GOOD: dict[str, Any] = {
    "name": "Interview blue",
    "font_pair": FONT_PAIRS[0],
    "accent": "#1f3d7a",
    "ink": "#1b1b1b",
    "muted": "#4a4a4a",
    "tint": "#eef1f6",
}


def problems(**changes: Any) -> dict[str, str]:
    data, found = clean_theme({**GOOD, **changes})
    assert data is None
    return found


def test_a_good_theme_is_accepted_and_colors_are_lowercased() -> None:
    data, found = clean_theme({**GOOD, "accent": "#1F3D7A"})
    assert found == {} and data is not None
    assert data.accent == "#1f3d7a" and data.name == "Interview blue"
    assert data.font_pair == FONT_PAIRS[0]


def test_names_are_one_tidy_line() -> None:
    assert tidy_name("  Dark \t  blue\n ") == "Dark blue"
    assert tidy_name("a\x00b\x7fc") == "abc"
    assert tidy_name(None) == "" and tidy_name(5) == ""


def test_a_name_is_needed_and_is_not_too_long() -> None:
    assert "name" in problems(name="")
    assert "name" in problems(name="   ")
    assert "name" in problems(name=7)
    assert "name" in problems(name="x" * (NAME_MAX + 1))
    data, found = clean_theme({**GOOD, "name": "x" * NAME_MAX})
    assert data is not None and found == {}


def test_every_part_is_needed() -> None:
    for key in ("font_pair", "accent", "ink", "muted", "tint"):
        raw = {k: v for k, v in GOOD.items() if k != key}
        data, found = clean_theme(raw)
        assert data is None and key in found


def test_only_a_known_font_pair_is_accepted() -> None:
    assert "font_pair" in problems(font_pair="comic-sans")
    assert "font_pair" in problems(font_pair=3)


@pytest.mark.parametrize("bad", ["red", "#fff", "#12345", "#1234567", "1f3d7a", "", None, 5])
def test_colors_must_be_six_digit_hex_codes(bad: Any) -> None:
    for key in ("accent", "ink", "muted", "tint"):
        assert key in problems(**{key: bad})


def test_text_colors_must_be_readable_on_white() -> None:
    assert "ink" in problems(ink="#dddddd")
    assert "muted" in problems(muted="#cccccc")


def test_a_tint_must_stay_readable_with_the_text_on_it() -> None:
    assert "tint" in problems(tint="#202020")


def test_something_that_is_not_a_theme_is_refused() -> None:
    for raw in (None, [], "theme", 5):
        data, found = clean_theme(raw)
        assert data is None and "theme" in found


def test_extra_fields_are_dropped_not_stored() -> None:
    data, found = clean_theme({**GOOD, "evil": "<script>", "margin_mm": 99})
    assert found == {} and data is not None
    assert set(vars(data)) == {"name", "font_pair", "accent", "ink", "muted", "tint"}
