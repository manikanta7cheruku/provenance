"""Resume tailoring: what can be changed, and the check that a change adds no unsupported fact.

A model may PROPOSE better wording for a part of a resume. It is never trusted to say that the
wording is true. This module is the check, and it is plain code:

  - A **unit** is a part of the resume that can be reworded: a list of bullets, or the paragraph of
    a summary. Headings, dates, names and contacts are never units, so they cannot be changed.
  - A **claim** is a thing in the new wording that a reader would take as a fact about the person:
    a number, a name or tool (a capitalised word, an acronym, a word with digits or symbols), and
    any word that the job asks for. Each claim must already appear in the old wording or in the
    evidence the suggestion cites. Otherwise it is unsupported and the suggestion is blocked.
  - Everything else (verbs, connecting words) is free, so a suggestion can reorder, tighten and
    emphasise what is already true.

A second model asked "is this true?" would be one more guess about a guess. This check cannot be
talked into anything: the same text and the same sources give the same answer every time.
"""

import copy
import re
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

MAX_UNITS = 40
MAX_LINES = 8
MAX_LINE_CHARS = 300
MAX_SUGGESTIONS = 10


class SuggestionStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class TailoringStatus(StrEnum):
    QUEUED = "queued"
    WORKING = "working"
    READY = "ready"
    FAILED = "failed"


class TailoringErrorCode(StrEnum):
    AI_NOT_CONFIGURED = "AI_NOT_CONFIGURED"
    AI_UNAVAILABLE = "AI_UNAVAILABLE"
    ANALYSIS_NEEDED = "ANALYSIS_NEEDED"


TAILORING_ERROR_MESSAGES = {
    TailoringErrorCode.AI_NOT_CONFIGURED.value: (
        "The suggestion service is not set up yet. Nothing in your resume was changed."
    ),
    TailoringErrorCode.AI_UNAVAILABLE.value: (
        "The suggestion service did not answer. Nothing in your resume was changed. Try again in a few minutes."
    ),
    TailoringErrorCode.ANALYSIS_NEEDED.value: (
        "Check this job against your profile first. Suggestions only use what that check confirmed."
    ),
}


# ---- units


@dataclass(frozen=True)
class Unit:
    unit_id: str
    target_id: str
    index: int
    kind: str  # "bullets" or "paragraph"
    label: str  # what it sits under, such as "Data Intern, Kestrel"
    lines: tuple[str, ...]


def _inline_text(node: dict[str, Any]) -> str:
    if node.get("type") == "hardBreak":
        return " "
    return str(node.get("text", ""))


def _paragraph_text(node: dict[str, Any]) -> str:
    return " ".join("".join(_inline_text(c) for c in node.get("content", [])).split())


def _list_lines(node: dict[str, Any]) -> list[str]:
    lines = []
    for item in node.get("content", []):
        text = " ".join(
            _paragraph_text(child)
            for child in item.get("content", [])
            if child.get("type") == "paragraph"
        ).strip()
        if text:
            lines.append(text)
    return lines


def _units_of_body(
    body: dict[str, Any] | None, target_id: str, *, label: str, paragraphs: bool
) -> list[Unit]:
    out: list[Unit] = []
    for index, node in enumerate((body or {}).get("content", [])):
        kind = node.get("type")
        if kind in ("bulletList", "orderedList"):
            lines = _list_lines(node)
            if lines:
                out.append(
                    Unit(f"{target_id}:{index}", target_id, index, "bullets", label, tuple(lines))
                )
        elif kind == "paragraph" and paragraphs:
            text = _paragraph_text(node)
            if text:
                out.append(
                    Unit(f"{target_id}:{index}", target_id, index, "paragraph", label, (text,))
                )
    return out


def _heading_of(body: dict[str, Any] | None, fallback: str) -> str:
    nodes = (body or {}).get("content", [])
    if nodes and nodes[0].get("type") == "paragraph":
        return _paragraph_text(nodes[0])[:80] or fallback
    return fallback


def extract_units(content: dict[str, Any]) -> list[Unit]:
    """Every part of a resume (guided or free canvas) that tailoring may reword."""
    units: list[Unit] = []
    if content.get("version") == 2:
        for page in content.get("pages", []):
            for el in page.get("elements", []):
                if el.get("kind") != "text" or not el.get("body"):
                    continue
                meta = el.get("meta") or {}
                summary = meta.get("kind") == "summary"
                label = (
                    _heading_of(el["body"], el.get("name", "Text")) if not summary else "Summary"
                )
                units.extend(_units_of_body(el["body"], el["id"], label=label, paragraphs=summary))
    else:
        for section in content.get("sections", []):
            summary = section.get("kind") == "summary"
            for block in section.get("blocks", []):
                label = (
                    ", ".join(p for p in (block.get("heading"), block.get("subheading")) if p)
                    or section.get("title")
                    or "Section"
                )
                units.extend(
                    _units_of_body(
                        block.get("body"), block["id"], label=label[:80], paragraphs=summary
                    )
                )
    return units[:MAX_UNITS]


def _rich_for(kind: str, lines: Iterable[str]) -> dict[str, Any]:
    texts = [line for line in lines if line.strip()]
    if kind == "paragraph":
        return {"type": "paragraph", "content": [{"type": "text", "text": " ".join(texts)}]}
    return {
        "type": "bulletList",
        "content": [
            {
                "type": "listItem",
                "content": [{"type": "paragraph", "content": [{"type": "text", "text": text}]}],
            }
            for text in texts
        ],
    }


def _bodies(content: dict[str, Any]) -> Iterable[tuple[str, dict[str, Any]]]:
    if content.get("version") == 2:
        for page in content.get("pages", []):
            for el in page.get("elements", []):
                if el.get("kind") == "text" and el.get("body"):
                    yield el["id"], el["body"]
    else:
        for section in content.get("sections", []):
            for block in section.get("blocks", []):
                if block.get("body"):
                    yield block["id"], block["body"]


def apply_unit(
    content: dict[str, Any], unit: Unit, after: Iterable[str], expected_before: Iterable[str]
) -> dict[str, Any] | None:
    """A copy of the resume with one unit reworded, or None when that part is not as it was.

    The old lines must still match what the suggestion was made from. If the person edited that
    part in the meantime, the suggestion is out of date and nothing is changed."""
    updated = copy.deepcopy(content)
    for target, body in _bodies(updated):
        if target != unit.target_id:
            continue
        nodes = body.get("content", [])
        if unit.index >= len(nodes):
            return None
        node = nodes[unit.index]
        now = (
            _list_lines(node)
            if node.get("type") in ("bulletList", "orderedList")
            else [_paragraph_text(node)]
        )
        if now != list(expected_before):
            return None
        nodes[unit.index] = _rich_for(unit.kind, after)
        return updated
    return None


def find_unit(content: dict[str, Any], unit_id: str) -> Unit | None:
    return next((u for u in extract_units(content) if u.unit_id == unit_id), None)


# ---- claims

_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9+#./&'-]*")
_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
_SENTENCE_START = re.compile(r"(?:^|[.!?]\s+)([A-Za-z])", re.MULTILINE)

# Words that carry no claim even when a job asks for them, or that sit at the start of a line.
_COMMON = frozenset(
    [
        "a",
        "about",
        "across",
        "after",
        "all",
        "also",
        "an",
        "and",
        "any",
        "are",
        "as",
        "at",
        "be",
        "been",
        "by",
        "can",
        "for",
        "from",
        "has",
        "have",
        "in",
        "into",
        "is",
        "it",
        "its",
        "of",
        "on",
        "or",
        "our",
        "per",
        "than",
        "that",
        "the",
        "their",
        "them",
        "then",
        "this",
        "through",
        "to",
        "up",
        "use",
        "used",
        "using",
        "via",
        "was",
        "were",
        "which",
        "while",
        "with",
        "within",
        "work",
        "worked",
        "working",
        "team",
        "teams",
        "ability",
        "able",
        "strong",
        "skills",
        "skill",
        "experience",
        "experienced",
        "knowledge",
        "understanding",
        "responsible",
        "role",
        "roles",
        "years",
        "year",
        "including",
        "etc",
        "new",
        "key",
        "high",
        "large",
        "based",
        "build",
        "built",
        "building",
        "develop",
        "developed",
        "developing",
        "manage",
        "managed",
        "managing",
        "lead",
        "led",
        "leading",
        "support",
        "supported",
        "supporting",
        "create",
        "created",
        "creating",
        "improve",
        "improved",
        "improving",
        "help",
        "helped",
        "helping",
    ]
)


@dataclass(frozen=True)
class Claim:
    text: str
    kind: str  # "number", "name" or "job term"
    supported: bool
    source: str | None  # "resume", "evidence" or None


def _norm(token: str) -> str:
    return token.strip(".,;:()[]'\"").lower()


def _numbers(text: str) -> set[str]:
    return {m.group(0).replace(",", "").rstrip(".") for m in _NUMBER.finditer(text)}


def _words(text: str) -> set[str]:
    return {_norm(t) for t in _TOKEN.findall(text) if _norm(t)}


def _is_name(token: str, at_start: bool) -> bool:
    bare = token.strip(".,;:()[]'\"")
    if len(bare) < 2 or bare.lower() in _COMMON:
        return False
    if any(ch.isdigit() for ch in bare) and not bare.replace(",", "").replace(".", "").isdigit():
        return True  # Python3, S3, 2FA
    if any(ch in bare for ch in "+#") or ("." in bare.strip(".") and not bare.endswith(".")):
        return True  # C++, C#, Node.js
    if bare.isupper() and len(bare) >= 2:
        return True  # SQL, AWS, ETL
    return bare[0].isupper() and not at_start  # a proper name or a tool in mid sentence


def extract_claims(text: str, job_words: Iterable[str] = ()) -> list[tuple[str, str]]:
    """(claim, kind) for everything in `text` that a reader would take as a fact about the person."""
    found: dict[str, str] = {}
    for number in sorted(_numbers(text)):
        found.setdefault(number, "number")
    starts = {m.start(1) for m in _SENTENCE_START.finditer(text)}
    wanted = {w.lower() for w in job_words}
    for match in _TOKEN.finditer(text):
        token = match.group(0)
        if _is_name(token, match.start() in starts):
            found.setdefault(_norm(token), "name")
        elif _norm(token) in wanted and _norm(token) not in _COMMON and len(_norm(token)) >= 4:
            found.setdefault(_norm(token), "job term")
    return [
        (claim, kind) for claim, kind in found.items() if not claim.isdigit() or kind == "number"
    ]


def job_vocabulary(requirement_texts: Iterable[str]) -> set[str]:
    """The words a job asks for, minus the plain ones. Adding one of these without evidence is
    the usual way a tailored resume starts to lie."""
    words: set[str] = set()
    for text in requirement_texts:
        words |= {w for w in _words(text) if w not in _COMMON and len(w) >= 4 and not w.isdigit()}
    return words


@dataclass(frozen=True)
class Verification:
    claims: tuple[Claim, ...]

    @property
    def unsupported(self) -> tuple[Claim, ...]:
        return tuple(c for c in self.claims if not c.supported)

    @property
    def blocked(self) -> bool:
        return bool(self.unsupported)


def verify_text(
    after: Iterable[str],
    *,
    before: Iterable[str],
    evidence: Iterable[str],
    job_words: Iterable[str] = (),
) -> Verification:
    """Check every claim in the new wording against the old wording and the cited evidence."""
    new_text = "\n".join(after)
    old_text = "\n".join(before)
    evidence_text = "\n".join(evidence)
    old_numbers, old_words = _numbers(old_text), _words(old_text)
    ev_numbers, ev_words = _numbers(evidence_text), _words(evidence_text)
    checked: list[Claim] = []
    for claim, kind in extract_claims(new_text, job_words):
        if kind == "number":
            in_old, in_ev = claim in old_numbers, claim in ev_numbers
        else:
            in_old, in_ev = claim in old_words, claim in ev_words
        checked.append(
            Claim(
                claim,
                kind,
                in_old or in_ev,
                "resume" if in_old else ("evidence" if in_ev else None),
            )
        )
    return Verification(tuple(checked))


# ---- what a model's suggestion may look like


def clean_lines(raw: Any) -> list[str] | None:
    """The lines of a suggestion with whitespace tidied, or None if it is not usable."""
    if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_LINES:
        return None
    lines = []
    for item in raw:
        if not isinstance(item, str):
            return None
        text = " ".join("".join(ch for ch in item if ch >= " " and ch != "\x7f").split())
        text = text.lstrip("-*• ").strip()
        if not text or len(text) > MAX_LINE_CHARS:
            return None
        lines.append(text)
    return lines
