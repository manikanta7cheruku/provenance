"""Reading a job source's answer: one parser per source, no network, no database.

Each source answers in its own shape. A parser turns that into the same small record (FeedJob), and
nothing else leaves it: no HTML, no script, no address that is not https, no text longer than a
limit. The fetch layer (in the worker) gets the bytes and enforces the limits on rate and size.
These functions only read what they were given, so they can be tested with saved responses.

What the parsers assume about each source comes from its official documentation and from a real
response read once on 2026-11-02, recorded in tests/fixtures/sources. If a source changes shape,
jobs are skipped and counted, never guessed, and a response that is not the expected kind at all is
an error that counts against the source's health.
"""

import hashlib
import html
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from html.parser import HTMLParser
from typing import Any

from pv_domain.job import EMPLOYMENT_TYPES

MAX_DESCRIPTION = 20_000
MAX_TITLE = 200
MAX_URL = 500
MAX_FIELD = 200
BOARD_ID = re.compile(r"^[A-Za-z0-9_-]{1,100}$")
_BLOCK = frozenset(
    [
        "p",
        "div",
        "br",
        "li",
        "ul",
        "ol",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "tr",
        "table",
        "section",
        "article",
    ]
)
_SKIP = frozenset(["script", "style", "template", "head"])
_SPACES = re.compile(r"[ \t\r\f\v ]+")
_BLANKS = re.compile(r"\n{3,}")


class FeedError(ValueError):
    """The answer is not the kind of document this source gives. Counts against the source."""


@dataclass(frozen=True)
class FeedJob:
    external_id: str
    url: str
    title: str
    company_name: str | None
    location: str
    workplace: str | None  # "remote", "hybrid" or "onsite"
    employment_type: str | None  # one of EMPLOYMENT_TYPES
    department: str
    description: str  # plain text
    posted_at: datetime | None
    updated_at: datetime | None
    content_hash: str


@dataclass(frozen=True)
class Parsed:
    jobs: tuple[FeedJob, ...]
    skipped: int


class _Text(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._hidden = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SKIP:
            self._hidden += 1
        elif tag in _BLOCK:
            self.parts.append("\n")
            if tag == "li":
                self.parts.append("- ")

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP and self._hidden:
            self._hidden -= 1
        elif tag in _BLOCK:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._hidden:
            self.parts.append(data)


def html_to_text(raw: Any, limit: int = MAX_DESCRIPTION) -> str:
    """Plain text from HTML, including HTML that arrives escaped (Greenhouse sends it that way).

    Tags are removed, script and style are dropped with their contents, entities are decoded, lists
    become lines starting with a dash, and the result is capped. Nothing here can carry markup on."""
    if not isinstance(raw, str) or not raw.strip():
        return ""
    text = raw
    if "&lt;" in text and "<" not in text:
        text = html.unescape(text)
    parser = _Text()
    try:
        parser.feed(text)
        parser.close()
    except Exception:  # noqa: BLE001 - broken markup must never stop a poll
        return _clean_plain(re.sub(r"<[^>]*>", " ", text), limit)
    return _clean_plain("".join(parser.parts), limit)


def _clean_plain(text: str, limit: int) -> str:
    text = "".join(ch for ch in text if ch == "\n" or ch >= " " and ch != "\x7f")
    lines = [_SPACES.sub(" ", line).strip() for line in text.split("\n")]
    return _BLANKS.sub("\n\n", "\n".join(lines)).strip()[:limit]


def clean_url(value: Any) -> str | None:
    """An https address with no spaces, quotes or angle brackets, or None."""
    if not isinstance(value, str):
        return None
    url = value.strip()
    if not url.startswith("https://") or len(url) > MAX_URL or len(url) <= len("https://"):
        return None
    if any(ch <= " " or ch == "\x7f" or ch in '<>"`' for ch in url):
        return None
    return url


def _obj(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _line(value: Any, limit: int = MAX_FIELD) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join("".join(ch for ch in value if ch >= " " and ch != "\x7f").split())[:limit]


def _when(value: Any) -> datetime | None:
    if isinstance(value, bool):
        return None
    try:
        if isinstance(value, int | float):
            return datetime.fromtimestamp(value / 1000, tz=UTC)
        if isinstance(value, str) and value:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    except (ValueError, OverflowError, OSError):
        return None
    return None


_EMPLOYMENT = {
    "fulltime": "full_time",
    "full-time": "full_time",
    "full time": "full_time",
    "parttime": "part_time",
    "part-time": "part_time",
    "part time": "part_time",
    "intern": "internship",
    "internship": "internship",
    "contract": "contract",
    "contractor": "contract",
    "temporary": "contract",
    "freelance": "freelance",
}


def _employment(value: Any) -> str | None:
    mapped = _EMPLOYMENT.get(_line(value).lower())
    return mapped if mapped in EMPLOYMENT_TYPES else None


def _workplace(value: Any, remote_flag: Any = None, location: str = "") -> str | None:
    word = _line(value).lower().replace("-", "").replace(" ", "")
    if word in ("remote", "hybrid"):
        return word
    if word in ("onsite", "office"):
        return "onsite"
    if remote_flag is True and not word:
        return "remote"
    if re.search(r"\bremote\b", location.lower()):
        return "remote"
    return None


def _digest(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()


def _job(
    external_id: Any,
    url: Any,
    title: Any,
    *,
    company: Any = None,
    location: str = "",
    workplace: str | None = None,
    employment: str | None = None,
    department: Any = "",
    description: str = "",
    posted: datetime | None = None,
    updated: datetime | None = None,
) -> FeedJob | None:
    ident = (
        _line(str(external_id), 100)
        if isinstance(external_id, str | int) and not isinstance(external_id, bool)
        else ""
    )
    address = clean_url(url)
    name = _line(title, MAX_TITLE)
    if not ident or address is None or not name:
        return None
    return FeedJob(
        external_id=ident,
        url=address,
        title=name,
        company_name=_line(company, 120) or None,
        location=location,
        workplace=workplace,
        employment_type=employment,
        department=_line(department),
        description=description,
        posted_at=posted,
        updated_at=updated,
        content_hash=_digest(name, location, description, address),
    )


def _collect(items: Any, make: Callable[[dict[str, Any]], FeedJob | None]) -> Parsed:
    if not isinstance(items, list):
        raise FeedError("The answer did not hold a list of jobs.")
    jobs: list[FeedJob] = []
    skipped = 0
    seen: set[str] = set()
    for raw in items:
        job = make(raw) if isinstance(raw, dict) else None
        if job is None or job.external_id in seen:
            skipped += 1
            continue
        seen.add(job.external_id)
        jobs.append(job)
    return Parsed(tuple(jobs), skipped)


# ---- the three ATS sources


def parse_lever(data: Any) -> Parsed:
    """Lever postings: a JSON list. Plain text and HTML descriptions are both given."""

    def make(raw: dict[str, Any]) -> FeedJob | None:
        cats = _obj(raw.get("categories"))
        place = _line(cats.get("location"))
        text = (
            raw.get("descriptionPlain")
            if isinstance(raw.get("descriptionPlain"), str)
            else raw.get("description")
        )
        body = html_to_text(text)
        extra = html_to_text(raw.get("additionalPlain") or raw.get("additional"))
        description = _clean_plain("\n\n".join(p for p in (body, extra) if p), MAX_DESCRIPTION)
        return _job(
            raw.get("id"),
            raw.get("hostedUrl"),
            raw.get("text"),
            location=place,
            workplace=_workplace(raw.get("workplaceType"), None, place),
            employment=_employment(cats.get("commitment")),
            department=cats.get("team") or cats.get("department") or "",
            description=description,
            posted=_when(raw.get("createdAt")),
        )

    return _collect(data, make)


def parse_greenhouse(data: Any) -> Parsed:
    """Greenhouse job board: an object with a jobs list. The description (content) is escaped HTML."""
    if not isinstance(data, dict):
        raise FeedError("The answer was not a Greenhouse job board.")

    def make(raw: dict[str, Any]) -> FeedJob | None:
        loc = _obj(raw.get("location"))
        place = _line(loc.get("name"))
        depts = raw.get("departments") if isinstance(raw.get("departments"), list) else []
        dept = depts[0].get("name") if depts and isinstance(depts[0], dict) else ""
        return _job(
            raw.get("id"),
            raw.get("absolute_url"),
            raw.get("title"),
            company=raw.get("company_name"),
            location=place,
            workplace=_workplace(None, None, place),
            employment=None,
            department=dept,
            description=html_to_text(raw.get("content")),
            posted=_when(raw.get("first_published")),
            updated=_when(raw.get("updated_at")),
        )

    return _collect(data.get("jobs"), make)


def parse_ashby(data: Any) -> Parsed:
    """Ashby job board: an object with a jobs list. Jobs not marked listed are skipped."""
    if not isinstance(data, dict):
        raise FeedError("The answer was not an Ashby job board.")

    def make(raw: dict[str, Any]) -> FeedJob | None:
        if raw.get("isListed") is False:
            return None
        place = _line(raw.get("location"))
        text = (
            raw.get("descriptionPlain")
            if isinstance(raw.get("descriptionPlain"), str)
            else raw.get("descriptionHtml")
        )
        return _job(
            raw.get("id"),
            raw.get("jobUrl"),
            raw.get("title"),
            location=place,
            workplace=_workplace(raw.get("workplaceType"), raw.get("isRemote"), place),
            employment=_employment(raw.get("employmentType")),
            department=raw.get("department") or raw.get("team") or "",
            description=html_to_text(text),
            posted=_when(raw.get("publishedAt")),
        )

    return _collect(data.get("jobs"), make)


@dataclass(frozen=True)
class Adapter:
    """What the fetch layer needs to know about one source: where to ask, and how to read the answer."""

    key: str
    url_template: str  # "{board}" is the only thing filled in
    hosts: tuple[str, ...]
    parse: Callable[[Any], Parsed]
    # True when one answer is the whole list of a board's open jobs, so a job missing from it is closed.
    complete_listing: bool = True


ADAPTERS: dict[str, Adapter] = {
    "lever": Adapter(
        "lever",
        "https://api.lever.co/v0/postings/{board}?mode=json",
        ("api.lever.co",),
        parse_lever,
    ),
    "greenhouse": Adapter(
        "greenhouse",
        "https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true",
        ("boards-api.greenhouse.io",),
        parse_greenhouse,
    ),
    "ashby": Adapter(
        "ashby",
        "https://api.ashbyhq.com/posting-api/job-board/{board}",
        ("api.ashbyhq.com",),
        parse_ashby,
    ),
}


def board_url(adapter: Adapter, board: str) -> str | None:
    """The address for one board, or None if the board id is not a plain identifier. Nothing a person
    types ever reaches here: board ids come from the company registry and are checked again."""
    if not BOARD_ID.match(board):
        return None
    return adapter.url_template.replace("{board}", board)
