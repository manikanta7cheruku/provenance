"""Deciding that two postings are the same job, in layers, with no model.

The same job turns up more than once: on a company's board and on another site, reposted under a
new id, or pasted by a person after the poller already found it. This module compares two postings
and answers one of three things: not the same, probably the same (suggested, a person decides), or
the same (auto, linked at once). It says why in words.

Layers, strongest first. A stronger layer wins, and a weaker one never overrides it:
  1. the same address (after tracking noise is removed)
  2. the same source and board, the same content under a new id (a repost)
  3. the same company and title, in the same place, with text that agrees
  4. a very close title in the same place, with nearly the same text

Hard rules that no score overrides:
  - two postings in different places are different jobs (the same title in two cities is two jobs),
    unless their address is the same
  - two postings at different companies are never linked
  - when the text is missing, agreement is never assumed from the title alone

All of it is plain code: the same two postings give the same answer every time, and each answer can
be explained, tested and undone. Links are edges. A group is the connected set of postings joined by
active links, so undoing one link can split a group again.
"""

import re
import zlib
from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import parse_qsl, urlencode, urlsplit

from pv_domain.company import normalize as normalize_company_name
from pv_domain.company import similarity
from pv_domain.search_intent import COUNTRIES

SHINGLE_WORDS = 5
SHINGLE_LIMIT = 600  # words read from the start of a description
AUTO_TEXT = 0.35
UNKNOWN_PLACE_TEXT = 0.6
CLOSE_TITLE = 0.82
NEAR_SAME_TEXT = 0.9
SUGGEST_TEXT = 0.6

_TRACKING = re.compile(
    r"^(utm_.*|gh_src|gh_jid_src|lever-source|lever-origin|ref|refid|source|src|trk|trackingid|fbclid|gclid|mc_cid|mc_eid)$"
)
_KEEP_QUERY = frozenset({"gh_jid", "jid", "id", "jobid", "job_id", "requisitionid", "req", "reqid"})
_BRACKETS = re.compile(r"[\(\[\{][^)\]}]*[)\]}]")
_NON_WORD = re.compile(r"[^a-z0-9]+")
_WORDS = re.compile(r"[a-z0-9]+")
_PLACE_SPLIT = re.compile(r"[;|/]| or |, (?=[A-Z])| - ")
_ABBREV = {"sr": "senior", "jr": "junior", "mgr": "manager", "eng": "engineer", "dev": "developer"}
_TITLE_NOISE = frozenset(
    {"m", "f", "d", "x", "w", "all", "genders", "gender", "remote", "hybrid", "onsite"}
)
_PLACE_STOP = frozenset(
    {"the", "of", "and", "area", "greater", "region", "metro", "state", "province", "district"}
)
_COUNTRY_NAMES: dict[str, str] = {
    alias: country.lower() for country, aliases in COUNTRIES.items() for alias in aliases
}


class Level(StrEnum):
    AUTO = "auto"
    SUGGESTED = "suggested"


@dataclass(frozen=True)
class JobFacts:
    """What is compared. Built from a fetched job or from a posting a person pasted."""

    url: str | None
    company: str | None
    title: str
    location: str
    description: str
    source_key: str = ""
    board_id: str = ""
    external_id: str = ""
    content_hash: str = ""


@dataclass(frozen=True)
class Match:
    method: str
    score: float
    level: Level
    reason: str


# ---- normalising


def normalize_url(url: str | None) -> str | None:
    """An address with tracking noise removed, so two links to one job compare equal."""
    if not url:
        return None
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return None
    if not parts.hostname:
        return None
    query = sorted(
        (k.lower(), v)
        for k, v in parse_qsl(parts.query, keep_blank_values=False)
        if not _TRACKING.match(k.lower()) and (k.lower() in _KEEP_QUERY)
    )
    host = parts.hostname.lower().removeprefix("www.")
    path = re.sub(r"/(apply|application)/?$", "", parts.path.lower().rstrip("/"))
    return f"{host}{path}" + (f"?{urlencode(query)}" if query else "")


def normalize_company(name: str | None) -> str:
    return normalize_company_name(name or "") if name else ""


def normalize_title(title: str) -> str:
    text = _BRACKETS.sub(" ", title.lower().replace("&", " and "))
    words = [_ABBREV.get(w, w) for w in _WORDS.findall(_NON_WORD.sub(" ", text))]
    return " ".join(w for w in words if w not in _TITLE_NOISE)


def place_tokens(location: str) -> tuple[frozenset[str], bool]:
    """(place words, is_remote). Country names and their short forms become one word."""
    lowered = location.lower()
    remote = bool(re.search(r"\bremote\b", lowered))
    tokens: set[str] = set()
    for chunk in re.split(r"[,;|/()]| - ", lowered):
        phrase = " ".join(_WORDS.findall(chunk)).strip()
        if not phrase or phrase in ("remote", "hybrid", "onsite", "on site"):
            continue
        phrase = phrase.replace("remote", "").strip()
        if phrase in _COUNTRY_NAMES:
            tokens.add(_COUNTRY_NAMES[phrase])
            continue
        tokens.update(
            w for w in phrase.split() if w not in _PLACE_STOP and w not in ("remote", "hybrid")
        )
    return frozenset(tokens), remote


def place_agreement(a: str, b: str) -> str:
    """ "same", "different" or "unknown". An empty place never contradicts, and is not agreement."""
    if not a.strip() or not b.strip():
        return "unknown"
    ta, ra = place_tokens(a)
    tb, rb = place_tokens(b)
    if ra and rb and (not ta or not tb):
        return "same" if not ta and not tb else "unknown"
    if not ta and not tb:
        return "different" if ra != rb else "unknown"
    if ra != rb and not (ta & tb):
        return "different"
    return "same" if ta & tb else "different"


def shingles(text: str) -> frozenset[int]:
    """Hashes of five-word runs from the start of a text, for comparing wording."""
    words = _WORDS.findall(text.lower())[:SHINGLE_LIMIT]
    if len(words) < SHINGLE_WORDS:
        return frozenset({zlib.crc32(" ".join(words).encode())}) if words else frozenset()
    return frozenset(
        zlib.crc32(" ".join(words[i : i + SHINGLE_WORDS]).encode())
        for i in range(len(words) - SHINGLE_WORDS + 1)
    )


def text_agreement(a: str, b: str) -> float | None:
    """Share of wording two descriptions have in common, or None when either has none to compare."""
    sa, sb = shingles(a), shingles(b)
    if not sa or not sb:
        return None
    return len(sa & sb) / len(sa | sb)


def _percent(value: float) -> str:
    return f"{round(value * 100)}%"


# ---- the layers


def compare(a: JobFacts, b: JobFacts) -> Match | None:
    """Whether two postings are the same job, and how sure that is. None means not the same."""
    ua, ub = normalize_url(a.url), normalize_url(b.url)
    if ua and ua == ub:
        return Match("same_address", 1.0, Level.AUTO, "Both postings are at the same address.")
    ca, cb = normalize_company(a.company), normalize_company(b.company)
    if not ca or not cb or ca != cb:
        return None
    if (
        a.source_key
        and a.source_key == b.source_key
        and a.board_id == b.board_id
        and a.external_id != b.external_id
        and a.content_hash
        and a.content_hash == b.content_hash
    ):
        return Match(
            "same_content", 0.98, Level.AUTO, "The same posting was published again under a new id."
        )
    place = place_agreement(a.location, b.location)
    if place == "different":
        return None
    ta, tb = normalize_title(a.title), normalize_title(b.title)
    if not ta or not tb:
        return None
    text = text_agreement(a.description, b.description)
    if ta == tb:
        if place == "same":
            if text is None:
                return Match(
                    "same_company_title_place",
                    0.7,
                    Level.SUGGESTED,
                    "Same company, title and place, but there is no text to compare.",
                )
            if text >= AUTO_TEXT:
                return Match(
                    "same_company_title_place",
                    round(0.8 + 0.2 * text, 2),
                    Level.AUTO,
                    f"Same company, title and place, and {_percent(text)} of the wording matches.",
                )
            return Match(
                "same_company_title_place",
                0.5,
                Level.SUGGESTED,
                f"Same company, title and place, but only {_percent(text)} of the wording matches.",
            )
        if text is not None and text >= UNKNOWN_PLACE_TEXT:
            return Match(
                "same_company_title_text",
                round(0.7 + 0.3 * text, 2),
                Level.AUTO,
                f"Same company and title, one place is missing, and {_percent(text)} of the wording matches.",
            )
        return Match(
            "same_company_title",
            0.4,
            Level.SUGGESTED,
            "Same company and title, but a place is missing and the text does not settle it.",
        )
    if place == "same" and similarity(ta, tb) >= CLOSE_TITLE and text is not None:
        if text >= NEAR_SAME_TEXT:
            return Match(
                "near_identical",
                round(0.7 + 0.3 * text, 2),
                Level.AUTO,
                f"A very close title in the same place, and {_percent(text)} of the wording matches.",
            )
        if text >= SUGGEST_TEXT:
            return Match(
                "similar",
                round(text, 2),
                Level.SUGGESTED,
                f"A close title in the same place, and {_percent(text)} of the wording matches.",
            )
    return None


# ---- groups


def components(nodes: list[str], edges: list[tuple[str, str]]) -> dict[str, str]:
    """Each node's group: the smallest id in its connected set. Nodes with no edge are their own group.

    Undoing a link is removing its edge and calling this again, so a group splits exactly where the
    link was the only thing joining it."""
    parent = {n: n for n in nodes}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b in edges:
        if a in parent and b in parent:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[max(ra, rb)] = min(ra, rb)
    return {n: find(n) for n in nodes}


def ordered_pair(a: str, b: str) -> tuple[str, str]:
    """A link is stored once, smaller id first."""
    return (a, b) if a < b else (b, a)
