"""Read a job posting from the web page a person pointed us at.

Pure code on text that has already been fetched and capped. The page is untrusted: scripts and styles
are dropped, nothing in it is run, and any instruction inside it is only text that may end up in the
posting, where it is read as data like any pasted posting.

Two ways in, best first:
  1. structured data (JSON-LD "JobPosting"), which many career pages publish for search engines
  2. the visible text of the page
"""

import contextlib
import json
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any

from pv_domain.job import clean_posting_text

MAX_STRUCTURED_BYTES = 500_000

_SKIP = frozenset(
    {
        "script",
        "style",
        "noscript",
        "template",
        "svg",
        "iframe",
        "head",
        "nav",
        "footer",
        "select",
        "button",
    }
)
_BREAK = frozenset(
    {
        "p",
        "div",
        "br",
        "li",
        "ul",
        "ol",
        "tr",
        "table",
        "section",
        "article",
        "main",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "blockquote",
        "dt",
        "dd",
    }
)
_SPACES = re.compile(r"[ 	  -   　]+")


@dataclass(frozen=True)
class PageJob:
    title: str | None
    company: str | None
    location: str | None
    text: str
    structured: bool


class _TextParser(HTMLParser):
    """Visible text with line breaks where a block ends. Also collects the page title and the
    contents of JSON-LD script blocks."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.title_parts: list[str] = []
        self.heading_parts: list[str] = []
        self.json_ld: list[str] = []
        self._skip = 0
        self._in_title = False
        self._in_h1 = False
        self._in_ld = False
        self._ld_buf: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "script":
            kind = dict(attrs).get("type") or ""
            if kind.lower().startswith("application/ld+json"):
                self._in_ld = True
                self._ld_buf = []
                return
        if tag == "title":
            self._in_title = True
        if tag == "h1":
            self._in_h1 = True
        if tag in _SKIP:
            self._skip += 1
        if tag in _BREAK and not self._skip:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._in_ld:
            self._in_ld = False
            self.json_ld.append("".join(self._ld_buf))
            return
        if tag == "title":
            self._in_title = False
        if tag == "h1":
            self._in_h1 = False
        if tag in _SKIP and self._skip:
            self._skip -= 1
        if tag in _BREAK and not self._skip:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._in_ld:
            self._ld_buf.append(data)
            return
        if self._in_title:
            self.title_parts.append(data)
        if self._skip:
            return
        if self._in_h1:
            self.heading_parts.append(data)
        self.parts.append(data)


def html_to_text(html: str) -> str:
    """The readable text of an HTML fragment or page."""
    parser = _TextParser()
    with contextlib.suppress(Exception):  # hostile markup: use what the parser had
        parser.feed(html)
        parser.close()
    lines = [_SPACES.sub(" ", line).strip() for line in "".join(parser.parts).split("\n")]
    return clean_posting_text("\n".join(line for line in lines if line))


def _as_text(value: Any) -> str | None:
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, dict):
        return _as_text(value.get("name"))
    return None


def _place(value: Any) -> str | None:
    items = value if isinstance(value, list) else [value]
    names: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        address = item.get("address")
        if isinstance(address, dict):
            pieces = [
                _as_text(address.get(key))
                for key in ("addressLocality", "addressRegion", "addressCountry")
            ]
            line = ", ".join(p for p in pieces if p)
            if line:
                names.append(line)
        elif isinstance(address, str) and address.strip():
            names.append(address.strip())
    return "; ".join(names) or None


def _job_objects(node: Any, depth: int = 0) -> list[dict[str, Any]]:
    if depth > 4:
        return []
    found: list[dict[str, Any]] = []
    if isinstance(node, list):
        for item in node:
            found.extend(_job_objects(item, depth + 1))
    elif isinstance(node, dict):
        kind = node.get("@type")
        kinds = kind if isinstance(kind, list) else [kind]
        if "JobPosting" in kinds:
            found.append(node)
        found.extend(_job_objects(node.get("@graph"), depth + 1))
    return found


def _from_structured(blocks: list[str]) -> PageJob | None:
    for block in blocks:
        if not block.strip() or len(block) > MAX_STRUCTURED_BYTES:
            continue
        try:
            data = json.loads(block)
        except ValueError:
            continue
        for job in _job_objects(data):
            description = _as_text(job.get("description"))
            if not description:
                continue
            body = (
                html_to_text(description) if "<" in description else clean_posting_text(description)
            )
            if not body:
                continue
            title = _as_text(job.get("title"))
            company = _as_text(job.get("hiringOrganization"))
            location = _place(job.get("jobLocation"))
            if _as_text(job.get("jobLocationType")) == "TELECOMMUTE":
                location = f"{location}, remote" if location else "Remote"
            return PageJob(title, company, location, body, structured=True)
    return None


def extract_job_page(html: str) -> PageJob | None:
    """The job on a page, or None when no description could be found."""
    parser = _TextParser()
    with contextlib.suppress(Exception):  # hostile markup: use what the parser had
        parser.feed(html)
        parser.close()
    structured = _from_structured(parser.json_ld)
    if structured is not None:
        return structured
    lines = [_SPACES.sub(" ", line).strip() for line in "".join(parser.parts).split("\n")]
    text = clean_posting_text("\n".join(line for line in lines if line))
    if not text:
        return None
    heading = clean_posting_text(" ".join(parser.heading_parts)) or None
    page_title = clean_posting_text(" ".join(parser.title_parts)) or None
    return PageJob(heading or page_title, None, None, text, structured=False)
