"""Bringing jobs in from a spreadsheet, a typed entry or a web page, and saying what happened.

The rules in one place, all pure:
  - which column holds what (a header can say "Job title", "Position" or "Role")
  - what makes a row acceptable, and the plain sentence when it is not
  - how a row becomes the posting text that is stored and read
  - the report: every row ends as created, already saved, or rejected with its reason

Nothing here trusts the file. Cells are text, never evaluated, and a spreadsheet formula in a cell is
only ever stored as the characters it is made of.
"""

import re
from dataclasses import dataclass, field
from enum import StrEnum
from urllib.parse import urlsplit

from pv_domain.job import (
    MAX_POSTING_CHARS,
    MIN_POSTING_CHARS,
    SOURCE_NAMES,
    clean_posting_text,
    posting_content_hash,
)

MAX_IMPORT_ROWS = 200
MAX_IMPORT_COLUMNS = 40
MAX_IMPORT_BYTES = 5 * 1024 * 1024
MAX_TITLE_CHARS = 200
MAX_COMPANY_CHARS = 200
MAX_LOCATION_CHARS = 200
MAX_LINK_CHARS = 500

ACQUISITION_MANUAL = "manual_entry"
ACQUISITION_CSV = "csv_import"
ACQUISITION_XLSX = "xlsx_import"
ACQUISITION_URL = "url_import"
ACQUISITION_SOURCE = "source_job"
IMPORT_ACQUISITIONS = (
    "user_paste",
    ACQUISITION_MANUAL,
    ACQUISITION_CSV,
    ACQUISITION_XLSX,
    ACQUISITION_URL,
    ACQUISITION_SOURCE,
)

KIND_CSV = "csv"
KIND_XLSX = "xlsx"
KIND_URL = "url"
BATCH_KINDS = (KIND_CSV, KIND_XLSX, KIND_URL)


class ItemStatus(StrEnum):
    QUEUED = "queued"
    CREATED = "created"
    DUPLICATE = "duplicate"
    REJECTED = "rejected"


class BatchStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


# What a header may be called. Matching ignores case, spaces, punctuation and underscores.
FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "description": (
        "description",
        "job description",
        "jobdescription",
        "details",
        "job details",
        "posting",
        "job posting",
        "text",
        "body",
        "content",
        "summary",
    ),
    "title": ("title", "job title", "jobtitle", "position", "role", "job", "designation"),
    "company": ("company", "company name", "employer", "organization", "organisation", "firm"),
    "location": ("location", "city", "place", "job location", "where"),
    "link": ("link", "url", "job url", "job link", "posting url", "apply url", "web address"),
    "source": ("source", "board", "site", "platform", "found on", "found at"),
}

ROW_MESSAGES: dict[str, str] = {
    "too_short": f"The description is under {MIN_POSTING_CHARS} characters. Paste the whole posting.",
    "too_long": f"The description is over {MAX_POSTING_CHARS:,} characters. Keep the posting text only.",
    "bad_link": "The link is not a web address that starts with http:// or https://.",
    "title_too_long": f"The title is over {MAX_TITLE_CHARS} characters.",
    "company_too_long": f"The company name is over {MAX_COMPANY_CHARS} characters.",
    "location_too_long": f"The location is over {MAX_LOCATION_CHARS} characters.",
    "duplicate_in_file": "Another row in this file has the same posting. Only the first is kept.",
    "already_saved": "You already have this posting. Nothing new was made.",
    "no_description": "The description cell is empty.",
}

FILE_MESSAGES: dict[str, str] = {
    "no_header": "The first row must be a header row that names each column.",
    "no_description_column": (
        "No column holds the job description. Name one of the columns Description, Job description, "
        "Details, Posting or Text."
    ),
    "no_rows": "The file has a header but no jobs under it.",
    "too_many_rows": f"The file has more than {MAX_IMPORT_ROWS} jobs. Split it into smaller files.",
    "too_big": "The file is over the 5 MB limit. Split it or remove columns you do not need.",
    "not_a_table": "This is not a CSV or XLSX spreadsheet.",
    "unreadable": "The file could not be read. Save it again as CSV or XLSX and try again.",
    "unsafe_archive": "This file is packed in a way we do not read. Save it again as CSV or XLSX.",
    "macros": "This workbook contains macros, which are not read. Save it as plain XLSX or CSV.",
    "encrypted": "This file is password protected. Remove the password and try again.",
    "empty": "The file is empty.",
}

PAGE_MESSAGES: dict[str, str] = {
    "dns": "That site name could not be found.",
    "private_address": "That address leads to a private network, so it is not read.",
    "redirect": "The page sent us somewhere that could not be followed.",
    "too_large": "The page is larger than the 2 MB limit.",
    "not_html": "The address did not return a web page we can read.",
    "blocked_by_site": "The site did not let us read this page. Open it yourself and paste the description instead.",
    "gone": "The page was not found. It may have been taken down.",
    "site_error": "The site had a problem and did not answer. Try again later.",
    "network": "The site could not be reached. Try again later.",
    "timeout": "The site took too long to answer. Try again later.",
    "no_text": "No job description could be found on that page. Open it yourself and paste the description instead.",
}

_NON_WORD = re.compile(r"[^a-z0-9]+")
_SPACES = re.compile(r"[ \t]+")


def _norm_header(value: str) -> str:
    return _NON_WORD.sub(" ", value.casefold()).strip()


@dataclass(frozen=True)
class ColumnMap:
    """Which column index holds which field. Fields with no column are absent."""

    columns: dict[str, int]
    ignored: tuple[str, ...]

    @property
    def recognised(self) -> tuple[str, ...]:
        return tuple(self.columns)


def map_columns(header: list[str]) -> ColumnMap:
    """Match header names to fields. The first column that matches a field wins."""
    lookup = {
        _norm_header(alias): field_name
        for field_name, names in FIELD_ALIASES.items()
        for alias in names
    }
    columns: dict[str, int] = {}
    ignored: list[str] = []
    for index, name in enumerate(header[:MAX_IMPORT_COLUMNS]):
        target = lookup.get(_norm_header(name))
        if target and target not in columns:
            columns[target] = index
        elif name.strip():
            ignored.append(name.strip()[:60])
    return ColumnMap(columns=columns, ignored=tuple(ignored))


@dataclass(frozen=True)
class PostingDraft:
    """One job ready to be stored."""

    title: str | None
    company: str | None
    location: str | None
    link: str | None
    source_name: str
    text: str
    content_hash: str


@dataclass(frozen=True)
class RowProblem:
    code: str
    message: str


@dataclass(frozen=True)
class PlannedRow:
    row_number: int  # the row's number in the file, counting the header as row 1
    draft: PostingDraft | None
    problem: RowProblem | None
    title: str | None = None  # kept for the report even when the row is rejected


@dataclass(frozen=True)
class ImportPlan:
    rows: list[PlannedRow] = field(default_factory=list)
    ignored_columns: tuple[str, ...] = ()
    blank_rows: int = 0


class ImportFileError(Exception):
    """The whole file cannot be used. code is a key of FILE_MESSAGES."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code

    @property
    def message(self) -> str:
        return FILE_MESSAGES.get(self.code, FILE_MESSAGES["unreadable"])


def clean_cell(value: str) -> str:
    """A cell as plain single-purpose text: control characters out, edges trimmed. A leading =, +,
    - or @ is kept as typed. It is stored and shown as text and never run or written back into a
    spreadsheet."""
    return clean_posting_text(value)


def clean_link(value: str | None) -> str | None:
    """A link that may be stored, or None when there is none. Raises ValueError when it is not a
    web address."""
    link = (value or "").strip()
    if not link:
        return None
    try:
        parts = urlsplit(link)
        ok = parts.scheme.lower() in ("http", "https") and bool(parts.hostname)
    except ValueError:
        ok = False
    if not ok or len(link) > MAX_LINK_CHARS or any(c.isspace() for c in link):
        raise ValueError("bad_link")
    return link


def source_label(value: str | None, default: str) -> str:
    """The source label for a row: the cell when it is one of the known names, else the default."""
    wanted = (value or "").strip().casefold()
    for name in SOURCE_NAMES:
        if name.casefold() == wanted:
            return name
    return default


def compose_posting_text(
    *, title: str | None, company: str | None, location: str | None, description: str
) -> str:
    """The text that is stored and read: the labelled fields, then the description.

    The labels make the title, company and place part of the text, so the reading step and the quote
    check can use them like any other words in the posting."""
    lines: list[str] = []
    if title:
        lines.append(f"Title: {title}")
    if company:
        lines.append(f"Company: {company}")
    if location:
        lines.append(f"Location: {location}")
    head = "\n".join(lines)
    return clean_posting_text(f"{head}\n\n{description}" if head else description)


def build_draft(
    *,
    title: str,
    company: str,
    location: str,
    link: str,
    source: str | None,
    description: str,
    default_source: str,
) -> PostingDraft:
    """Check one job and return it as a draft, or raise ValueError with a key of ROW_MESSAGES."""
    title, company, location = clean_cell(title), clean_cell(company), clean_cell(location)
    description = clean_cell(description)
    if len(title) > MAX_TITLE_CHARS:
        raise ValueError("title_too_long")
    if len(company) > MAX_COMPANY_CHARS:
        raise ValueError("company_too_long")
    if len(location) > MAX_LOCATION_CHARS:
        raise ValueError("location_too_long")
    cleaned_link = clean_link(link)
    if not description:
        raise ValueError("no_description")
    text = compose_posting_text(
        title=title or None,
        company=company or None,
        location=location or None,
        description=description,
    )
    if len(text) > MAX_POSTING_CHARS:
        raise ValueError("too_long")
    if len(text) < MIN_POSTING_CHARS:
        raise ValueError("too_short")
    return PostingDraft(
        title=title or None,
        company=company or None,
        location=location or None,
        link=cleaned_link,
        source_name=source_label(source, default_source),
        text=text,
        content_hash=posting_content_hash(text),
    )


def plan_rows(table: list[list[str]], *, default_source: str) -> ImportPlan:
    """Turn the rows of a spreadsheet into drafts and per-row problems.

    Raises ImportFileError when the file as a whole cannot be used (no header, no description
    column, nothing under the header, too many rows)."""
    rows = [list(r) for r in table]
    while rows and not any(cell.strip() for cell in rows[-1]):
        rows.pop()
    if not rows:
        raise ImportFileError("empty")
    header = rows[0]
    if not any(cell.strip() for cell in header):
        raise ImportFileError("no_header")
    mapping = map_columns(header)
    if "description" not in mapping.columns:
        raise ImportFileError("no_description_column")
    body = rows[1:]
    if not body:
        raise ImportFileError("no_rows")
    if len(body) > MAX_IMPORT_ROWS:
        raise ImportFileError("too_many_rows")

    def cell(row: list[str], name: str) -> str:
        index = mapping.columns.get(name)
        return row[index] if index is not None and index < len(row) else ""

    planned: list[PlannedRow] = []
    seen: set[str] = set()
    blank = 0
    for offset, row in enumerate(body):
        number = offset + 2
        if not any(c.strip() for c in row):
            blank += 1
            continue
        title_hint = _SPACES.sub(" ", cell(row, "title")).strip()[:MAX_TITLE_CHARS] or None
        try:
            draft = build_draft(
                title=cell(row, "title"),
                company=cell(row, "company"),
                location=cell(row, "location"),
                link=cell(row, "link"),
                source=cell(row, "source"),
                description=cell(row, "description"),
                default_source=default_source,
            )
        except ValueError as exc:
            code = str(exc)
            planned.append(
                PlannedRow(
                    number,
                    None,
                    RowProblem(code, ROW_MESSAGES.get(code, "This row could not be used.")),
                    title_hint,
                )
            )
            continue
        if draft.content_hash in seen:
            planned.append(
                PlannedRow(
                    number,
                    None,
                    RowProblem("duplicate_in_file", ROW_MESSAGES["duplicate_in_file"]),
                    draft.title,
                )
            )
            continue
        seen.add(draft.content_hash)
        planned.append(PlannedRow(number, draft, None, draft.title))
    return ImportPlan(rows=planned, ignored_columns=mapping.ignored, blank_rows=blank)
