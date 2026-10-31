"""The resume as a structured document: sections, blocks, rich text, and style that is kept apart.

Content is data, not markup. The editor sends this JSON, the server validates it against a small
whitelist and stores it, and one renderer (pv_domain.resume_render) turns it into the HTML that both
the live preview and the PDF use. Because no raw HTML is ever stored, a saved resume cannot carry
script, a remote image or a link tag, and tailoring (2.3) can work on the structured text.

Style is a handful of named choices, not free CSS: a template, a font pair, a size, a spacing scale,
margins, an accent color that must be readable on white, a divider style and a paper size.
"""

import re
import uuid
from dataclasses import dataclass
from typing import Any

SCHEMA_VERSION = 1

# Limits keep a document small enough to save on every pause in typing and to render in seconds.
MAX_SECTIONS = 14
MAX_BLOCKS_PER_SECTION = 30
MAX_BLOCKS = 80
MAX_TEXT_CHARS = 30_000
MAX_CONTACTS = 8
MAX_RICH_DEPTH = 5
MAX_NODES_PER_BODY = 400
MAX_VERSIONS = 20

SECTION_KINDS = (
    "summary",
    "experience",
    "education",
    "projects",
    "skills",
    "certifications",
    "achievements",
    "custom",
)
MARKS = ("bold", "italic", "underline", "highlight")
TEMPLATES = ("classic", "modern", "compact")
FONT_PAIRS = ("plex-newsreader", "plex", "newsreader")
SIZES = ("small", "medium", "large")
SPACINGS = ("tight", "normal", "relaxed")
MARGINS = ("narrow", "normal", "wide")
DIVIDERS = ("none", "thin", "bold", "dotted")
PAPERS = ("a4", "letter")

_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
_ID = re.compile(r"^[A-Za-z0-9_-]{1,40}$")

# The minimum contrast of the accent color on white for normal text (WCAG AA).
MIN_ACCENT_CONTRAST = 4.5


@dataclass(frozen=True)
class TemplateInfo:
    key: str
    name: str
    description: str
    # Single column, standard headings, no tables, images or sidebars: what applicant tracking
    # systems read most reliably. Shown to the person, never hidden (resume-studio-requirements).
    ats_safe: bool


TEMPLATE_INFO = {
    "classic": TemplateInfo(
        "classic",
        "Classic",
        "A serif name and headings over plain body text, with thin rules. The safe, traditional choice.",
        True,
    ),
    "modern": TemplateInfo(
        "modern",
        "Modern",
        "Sans serif throughout, an accent color on headings and a heavier rule under the name.",
        True,
    ),
    "compact": TemplateInfo(
        "compact",
        "Compact",
        "Tighter type and spacing to fit more on one page. Best for a fresher with a short history.",
        True,
    ),
}


class ResumeDocError(ValueError):
    """The document did not pass validation. `problems` maps a path to a sentence for a person."""

    def __init__(self, problems: dict[str, str]) -> None:
        super().__init__("; ".join(problems.values()))
        self.problems = problems


def _luminance(hex_color: str) -> float:
    channels = []
    for i in (1, 3, 5):
        c = int(hex_color[i : i + 2], 16) / 255
        channels.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def contrast_on_white(hex_color: str) -> float:
    return 1.05 / (_luminance(hex_color) + 0.05)


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def default_style(template: str = "classic") -> dict[str, Any]:
    return {
        "template": template,
        "font_pair": "plex" if template == "modern" else "plex-newsreader",
        "size": "small" if template == "compact" else "medium",
        "spacing": "tight" if template == "compact" else "normal",
        "margins": "narrow" if template == "compact" else "normal",
        "accent": "#1f3d7a" if template == "modern" else "#222222",
        "divider": "bold" if template == "modern" else "thin",
        "paper": "a4",
    }


def blank_document(template: str = "classic", name: str = "") -> dict[str, Any]:
    return {
        "version": SCHEMA_VERSION,
        "style": default_style(template),
        "header": {"name": name, "headline": "", "contacts": []},
        "sections": [],
    }


# ---- rich text


def _clean_str(value: Any, limit: int, path: str, problems: dict[str, str]) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        problems[path] = "This should be text."
        return ""
    text = value.replace("\r\n", "\n").replace("\r", "\n")
    text = "".join(ch for ch in text if ch == "\n" or ch >= " " and ch != "\x7f")
    if len(text) > limit:
        problems[path] = f"This is too long. Keep it under {limit} characters."
        return text[:limit]
    return text.strip()


def _clean_inline(
    node: Any, path: str, problems: dict[str, str], budget: list[int]
) -> dict[str, Any] | None:
    if not isinstance(node, dict):
        problems[path] = "This is not a valid piece of text."
        return None
    kind = node.get("type")
    budget[0] -= 1
    if kind == "hardBreak":
        return {"type": "hardBreak"}
    if kind != "text":
        problems[path] = "Only plain text with simple formatting is allowed here."
        return None
    text = node.get("text")
    if not isinstance(text, str) or text == "":
        return None
    marks: list[dict[str, str]] = []
    for mark in node.get("marks") or []:
        mark_type = mark.get("type") if isinstance(mark, dict) else None
        if mark_type not in MARKS:
            problems[path] = "That formatting is not available."
            continue
        if mark_type not in [m["type"] for m in marks]:
            marks.append({"type": mark_type})
    cleaned = "".join(ch for ch in text if ch >= " " and ch != "\x7f")
    out: dict[str, Any] = {"type": "text", "text": cleaned}
    if marks:
        out["marks"] = marks
    return out


def _clean_block_node(
    node: Any, depth: int, path: str, problems: dict[str, str], budget: list[int]
) -> dict[str, Any] | None:
    if depth > MAX_RICH_DEPTH or budget[0] <= 0:
        problems[path] = "This is too complicated. Simplify the formatting."
        return None
    if not isinstance(node, dict):
        problems[path] = "This is not a valid paragraph."
        return None
    kind = node.get("type")
    budget[0] -= 1
    items = node.get("content") or []
    if not isinstance(items, list):
        problems[path] = "This is not valid."
        return None
    if kind == "paragraph":
        content = [
            c
            for i, raw in enumerate(items)
            if (c := _clean_inline(raw, f"{path}.{i}", problems, budget)) is not None
        ]
        return {"type": "paragraph", "content": content}
    if kind in ("bulletList", "orderedList"):
        entries = []
        for i, raw in enumerate(items):
            if not isinstance(raw, dict) or raw.get("type") != "listItem":
                problems[path] = "A list can only contain list items."
                continue
            inner = [
                c
                for j, child in enumerate(raw.get("content") or [])
                if (c := _clean_block_node(child, depth + 1, f"{path}.{i}.{j}", problems, budget))
                is not None
            ]
            entries.append({"type": "listItem", "content": inner})
        return {"type": kind, "content": entries}
    problems[path] = "That kind of content is not available."
    return None


def clean_rich(body: Any, path: str, problems: dict[str, str]) -> dict[str, Any] | None:
    if body is None:
        return None
    if not isinstance(body, dict) or body.get("type") != "doc":
        problems[path] = "This is not valid text."
        return None
    budget = [MAX_NODES_PER_BODY]
    content = [
        c
        for i, raw in enumerate(body.get("content") or [])
        if (c := _clean_block_node(raw, 1, f"{path}.{i}", problems, budget)) is not None
    ]
    return {"type": "doc", "content": content} if content else None


def rich_to_text(body: dict[str, Any] | None) -> str:
    """Plain text of a rich body, one line per paragraph or list item."""
    lines: list[str] = []

    def walk(node: dict[str, Any], prefix: str) -> None:
        kind = node.get("type")
        if kind == "paragraph":
            text = "".join(
                "\n" if c.get("type") == "hardBreak" else c.get("text", "")
                for c in node.get("content", [])
            )
            lines.append(prefix + text)
        elif kind in ("bulletList", "orderedList"):
            for n, item in enumerate(node.get("content", []), start=1):
                mark = "- " if kind == "bulletList" else f"{n}. "
                for child in item.get("content", []):
                    walk(child, mark)

    for node in (body or {}).get("content", []):
        walk(node, "")
    return "\n".join(lines)


# ---- the document


def _clean_style(raw: Any, problems: dict[str, str]) -> dict[str, Any]:
    style = default_style()
    if raw is None:
        return style
    if not isinstance(raw, dict):
        problems["style"] = "The style is not valid."
        return style
    choices = {
        "template": TEMPLATES,
        "font_pair": FONT_PAIRS,
        "size": SIZES,
        "spacing": SPACINGS,
        "margins": MARGINS,
        "divider": DIVIDERS,
        "paper": PAPERS,
    }
    for key, allowed in choices.items():
        if key in raw:
            if raw[key] in allowed:
                style[key] = raw[key]
            else:
                problems[f"style.{key}"] = "Choose one of the options shown."
    if "accent" in raw:
        accent = raw["accent"]
        if not isinstance(accent, str) or not _HEX.match(accent):
            problems["style.accent"] = "Use a color like #1f3d7a."
        elif contrast_on_white(accent) < MIN_ACCENT_CONTRAST:
            problems["style.accent"] = (
                "This color is too light to read on white paper. Choose a darker one."
            )
        else:
            style["accent"] = accent.lower()
    return style


def validate_document(raw: Any) -> dict[str, Any]:
    """Return a clean copy of a document, or raise ResumeDocError naming what is wrong."""
    problems: dict[str, str] = {}
    if not isinstance(raw, dict):
        raise ResumeDocError({"document": "The resume is not valid."})
    style = _clean_style(raw.get("style"), problems)

    header_raw: dict[str, Any] = raw["header"] if isinstance(raw.get("header"), dict) else {}
    contacts_raw = header_raw.get("contacts") or []
    if not isinstance(contacts_raw, list) or len(contacts_raw) > MAX_CONTACTS:
        problems["header.contacts"] = f"Add at most {MAX_CONTACTS} contact details."
        contacts_raw = contacts_raw[:MAX_CONTACTS] if isinstance(contacts_raw, list) else []
    header = {
        "name": _clean_str(header_raw.get("name"), 120, "header.name", problems),
        "headline": _clean_str(header_raw.get("headline"), 160, "header.headline", problems),
        "contacts": [
            c
            for i, item in enumerate(contacts_raw)
            if (c := _clean_str(item, 160, f"header.contacts.{i}", problems))
        ],
    }

    sections_raw = raw.get("sections") or []
    if not isinstance(sections_raw, list):
        raise ResumeDocError({"sections": "The sections are not valid."})
    if len(sections_raw) > MAX_SECTIONS:
        problems["sections"] = f"Use at most {MAX_SECTIONS} sections."
    sections: list[dict[str, Any]] = []
    total_blocks = 0
    seen_ids: set[str] = set()
    for si, sec in enumerate(sections_raw[:MAX_SECTIONS]):
        path = f"sections.{si}"
        if not isinstance(sec, dict):
            problems[path] = "This section is not valid."
            continue
        kind = sec.get("kind") if sec.get("kind") in SECTION_KINDS else "custom"
        raw_sid = sec.get("id")
        sid = raw_sid if isinstance(raw_sid, str) and _ID.match(raw_sid) else new_id()
        if sid in seen_ids:
            sid = new_id()
        seen_ids.add(sid)
        blocks_raw = sec.get("blocks") or []
        if not isinstance(blocks_raw, list) or len(blocks_raw) > MAX_BLOCKS_PER_SECTION:
            problems[f"{path}.blocks"] = f"Use at most {MAX_BLOCKS_PER_SECTION} items per section."
            blocks_raw = blocks_raw[:MAX_BLOCKS_PER_SECTION] if isinstance(blocks_raw, list) else []
        blocks = []
        for bi, blk in enumerate(blocks_raw):
            bpath = f"{path}.blocks.{bi}"
            if not isinstance(blk, dict):
                problems[bpath] = "This item is not valid."
                continue
            raw_bid = blk.get("id")
            bid = raw_bid if isinstance(raw_bid, str) and _ID.match(raw_bid) else new_id()
            if bid in seen_ids:
                bid = new_id()
            seen_ids.add(bid)
            blocks.append(
                {
                    "id": bid,
                    "heading": _clean_str(blk.get("heading"), 160, f"{bpath}.heading", problems),
                    "subheading": _clean_str(
                        blk.get("subheading"), 160, f"{bpath}.subheading", problems
                    ),
                    "dates": _clean_str(blk.get("dates"), 60, f"{bpath}.dates", problems),
                    "location": _clean_str(blk.get("location"), 120, f"{bpath}.location", problems),
                    "body": clean_rich(blk.get("body"), f"{bpath}.body", problems),
                }
            )
        total_blocks += len(blocks)
        sections.append(
            {
                "id": sid,
                "kind": kind,
                "title": _clean_str(sec.get("title"), 60, f"{path}.title", problems),
                "blocks": blocks,
            }
        )
    if total_blocks > MAX_BLOCKS:
        problems["sections"] = f"Use at most {MAX_BLOCKS} items in total."

    document = {"version": SCHEMA_VERSION, "style": style, "header": header, "sections": sections}
    if len(document_text(document)) > MAX_TEXT_CHARS:
        problems["document"] = (
            f"The resume is too long. Keep it under {MAX_TEXT_CHARS:,} characters."
        )
    if problems:
        raise ResumeDocError(problems)
    return document


def document_text(doc: dict[str, Any]) -> str:
    """All the text of a document in reading order. Used for limits, search and PDF checks."""
    header = doc["header"]
    parts = [header["name"], header["headline"], *header["contacts"]]
    for section in doc["sections"]:
        parts.append(section["title"])
        for block in section["blocks"]:
            parts += [block["heading"], block["subheading"], block["dates"], block["location"]]
            parts.append(rich_to_text(block["body"]))
    return "\n".join(p for p in parts if p)


# ---- building a first draft from the profile


def _doc_from_lines(lines: list[str]) -> dict[str, Any] | None:
    items = [line.strip() for line in lines if line and line.strip()]
    if not items:
        return None
    return {
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
                    for line in items
                ],
            }
        ],
    }


def _doc_from_text(text: str) -> dict[str, Any] | None:
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    if not paragraphs:
        return None
    return {
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": p}]} for p in paragraphs
        ],
    }


def _dates(data: dict[str, Any]) -> str:
    start, end = data.get("start_date") or "", data.get("end_date") or ""
    if start and end:
        return f"{start} to {end}"
    return start or end or ""


def document_from_entries(
    entries: list[tuple[str, dict[str, Any]]], *, name: str = "", template: str = "classic"
) -> dict[str, Any]:
    """A first draft from profile entries given as (entry_type, data). Nothing is invented: every
    word comes from an entry, and empty sections are left out."""
    doc = blank_document(template, name)
    by_type: dict[str, list[dict[str, Any]]] = {}
    for entry_type, data in entries:
        by_type.setdefault(entry_type, []).append(data)

    def section(kind: str, title: str, blocks: list[dict[str, Any]]) -> None:
        if blocks:
            doc["sections"].append(
                {
                    "id": new_id(),
                    "kind": kind,
                    "title": title,
                    "blocks": blocks[:MAX_BLOCKS_PER_SECTION],
                }
            )

    def block(**fields: Any) -> dict[str, Any]:
        base = {
            "id": new_id(),
            "heading": "",
            "subheading": "",
            "dates": "",
            "location": "",
            "body": None,
        }
        base.update(fields)
        return base

    roles = [
        block(
            heading=d.get("title", ""),
            subheading=d.get("company", ""),
            dates=_dates(d),
            location=d.get("location", "") or "",
            body=_doc_from_lines(d.get("highlights") or []),
        )
        for d in by_type.get("work", []) + by_type.get("internship", [])
    ]
    section("experience", "Experience", roles)
    section(
        "education",
        "Education",
        [
            block(
                heading=" ".join(x for x in (d.get("degree"), d.get("field_of_study")) if x)
                or d.get("institution", ""),
                subheading=d.get("institution", "")
                if d.get("degree") or d.get("field_of_study")
                else "",
                dates=_dates(d),
                body=_doc_from_text(
                    "\n".join(
                        x
                        for x in (
                            f"Grade: {d['grade']}" if d.get("grade") else "",
                            d.get("details", ""),
                        )
                        if x
                    )
                ),
            )
            for d in by_type.get("education", [])
        ],
    )
    section(
        "projects",
        "Projects",
        [
            block(
                heading=d.get("name", ""),
                subheading=", ".join(d.get("technologies") or []),
                dates=_dates(d),
                body=_doc_from_text(d.get("description", "") or ""),
            )
            for d in by_type.get("project", [])
        ],
    )
    skills: dict[str, list[str]] = {}
    for d in by_type.get("skill", []):
        skills.setdefault(d.get("category") or "Skills", []).append(d.get("name", ""))
    section(
        "skills",
        "Skills",
        [
            block(
                heading=group if group != "Skills" else "",
                body=_doc_from_text(", ".join(n for n in names if n)),
            )
            for group, names in skills.items()
        ],
    )
    section(
        "certifications",
        "Certifications",
        [
            block(
                heading=d.get("name", ""),
                subheading=d.get("issuer", "") or "",
                dates=d.get("date", "") or "",
            )
            for d in by_type.get("certification", [])
        ],
    )
    section(
        "achievements",
        "Achievements",
        [
            block(
                heading=d.get("title", ""),
                dates=d.get("date", "") or "",
                body=_doc_from_text(d.get("description", "") or ""),
            )
            for d in by_type.get("achievement", [])
        ],
    )
    doc["header"]["contacts"] = [
        f"{d.get('label', '')}: {d.get('url', '')}".strip(": ") for d in by_type.get("link", [])
    ][:MAX_CONTACTS]
    return validate_document(doc)
