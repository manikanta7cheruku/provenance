"""The opportunities report: what goes in it, in what words, and how a cell is made safe.

Pure rules, no files and no database. A report is built from stored data only (never from the
screen), the same stored data gives the same report, and it always says when it was made, which
filters chose the jobs and which sources they came from. Three formats (CSV, XLSX, DOCX) are written
from the one `Report` model in pv_files, so what a person sees in each is the same.

Cells are untrusted text (a job title is whatever a posting said). Two things are done to every
text cell before it is written anywhere:
  - characters that cannot exist in an XML or Word file are dropped, so one odd posting cannot make
    the whole file unreadable
  - a cell that starts with = + - @ (or a tab or carriage return) gets a leading apostrophe, so a
    spreadsheet never reads it as a formula (formula injection)
"""

import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime

from pv_domain.pipeline import STATE_LABELS, VIEW_LABELS, DecisionState, WorkQuery

FORMATS = ("csv", "xlsx", "docx")
FORMAT_LABELS = {"csv": "CSV", "xlsx": "Excel workbook", "docx": "Word document"}
MEDIA_TYPES = {
    "csv": "text/csv; charset=utf-8",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
MAX_REPORT_JOBS = 500
MAX_CELL_CHARS = 5000  # far under Excel's 32,767, and long enough for any note or reason
MAX_QUOTE_CHARS = 300  # an evidence quote, when the person asks for quotes
MAX_ACTIVE_EXPORTS = 3  # reports being made at once, per person
KEEP_EXPORTS = 20  # reports kept per person; older ones are removed

BAND_LABELS = {
    "strong": "Strong match",
    "good": "Good match",
    "review": "Needs review",
    "not_recommended": "Not recommended",
    "not_eligible": "Not eligible",
}
ELIGIBILITY_LABELS = {
    "eligible": "Eligible",
    "uncertain": "Not sure yet",
    "requires_user_input": "Needs your answer",
    "not_eligible": "Not eligible",
}
VERDICT_LABELS = {
    "met": "Shown",
    "partial": "Partly shown",
    "not_verified": "Not shown",
    "conflicting": "Conflicting",
    "": "Not checked yet",
}
ACQUISITION_LABELS = {
    "user_paste": "Pasted by you",
    "manual_entry": "Typed in by you",
    "url_import": "Read from an address you gave",
    "csv_import": "From a CSV file you brought",
    "xlsx_import": "From a spreadsheet you brought",
    "source_job": "Found by a job source",
}

_FORMULA_START = ("=", "+", "-", "@", "\t", "\r")
# Everything XML 1.0 forbids: C0 controls except tab, newline and carriage return, and the two
# non-characters. Surrogates cannot appear in a Python str that was decoded from UTF-8.
_BAD_XML = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f￾￿]")


def clean_text(value: object, limit: int = MAX_CELL_CHARS, *, strip: bool = True) -> str:
    """Text made safe to write into any of the three formats. Never raises."""
    if value is None:
        return ""
    text = _BAD_XML.sub("", str(value))
    if strip:
        text = text.strip()
    if len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    return text


def neutralize(value: object, limit: int = MAX_CELL_CHARS) -> str:
    """clean_text, plus a leading apostrophe when a spreadsheet could read the cell as a formula."""
    text = clean_text(value, limit)
    return "'" + text if text.startswith(_FORMULA_START) else text


@dataclass(frozen=True)
class ReportEvidence:
    source: str  # where the evidence came from, in words ("Resume", "GitHub")
    entry: str  # what kind of entry ("Project", "Experience")
    quote: str = ""  # only when the person asked for quotes


@dataclass(frozen=True)
class ReportRequirement:
    text: str
    importance: str  # "Required" or "Preferred" or ""
    verdict: str  # a key of VERDICT_LABELS
    reason: str
    evidence: tuple[ReportEvidence, ...] = ()


@dataclass(frozen=True)
class ReportJob:
    id: str
    title: str
    company: str
    location: str
    work_mode: str
    employment_type: str
    seniority: str
    source: str
    acquisition: str  # a key of ACQUISITION_LABELS
    link: str
    eligibility: str  # a key of ELIGIBILITY_LABELS, or ""
    band: str  # a key of BAND_LABELS, or ""
    recommendation: str  # the sentence the fit score gave, or ""
    state: str  # a DecisionState value
    applied_on: str  # a date, or ""
    note: str
    added_on: str
    requirements: tuple[ReportRequirement, ...] = ()


@dataclass(frozen=True)
class ReportInput:
    generated_at: datetime
    criteria: tuple[str, ...]  # the filters, in words
    jobs: tuple[ReportJob, ...]
    include_quotes: bool = False
    truncated: bool = False  # more jobs matched than the report holds


@dataclass(frozen=True)
class Table:
    name: str  # a sheet name, at most 31 characters
    headers: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]
    widths: tuple[int, ...] = ()  # in characters, for the workbook


@dataclass(frozen=True)
class Report:
    title: str
    generated_at: datetime
    summary: tuple[tuple[str, str], ...]  # label and value, in order
    sentence: str  # "41 opportunities. 12 strong matches. ..."
    tables: tuple[Table, ...]
    notes: tuple[str, ...] = field(default_factory=tuple)
    jobs: tuple[ReportJob, ...] = ()  # for the Word report, which reads job by job


def stamp(moment: datetime) -> str:
    """When, in UTC, in a form that sorts and is unambiguous."""
    return moment.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")


def describe_query(query: WorkQuery) -> tuple[str, ...]:
    """The filters that chose the jobs, in plain words. Always at least the list that was open."""
    lines = [f"List: {VIEW_LABELS.get(query.view, query.view)}"]
    if query.states:
        names = [STATE_LABELS[DecisionState(s)] for s in sorted(query.states)]
        lines.append("Decision: " + ", ".join(names))
    if query.text:
        lines.append(f"Words: {query.text}")
    if query.company:
        lines.append(f"Company: {query.company}")
    if query.location:
        lines.append(f"Location: {query.location}")
    if query.bands:
        lines.append("Fit: " + ", ".join(BAND_LABELS.get(b, b) for b in sorted(query.bands)))
    if query.eligibility:
        lines.append(
            "Eligibility: "
            + ", ".join(ELIGIBILITY_LABELS.get(e, e) for e in sorted(query.eligibility))
        )
    for label, values in (
        ("Work mode", query.work_modes),
        ("Employment type", query.employment_types),
        ("Seniority", query.seniorities),
        ("Source", query.sources),
    ):
        if values:
            lines.append(f"{label}: " + ", ".join(sorted(values)))
    return tuple(lines)


def counts_sentence(jobs: tuple[ReportJob, ...]) -> str:
    """ "41 opportunities. 12 strong matches. ..." from the stored data, never estimated."""
    total = len(jobs)
    noun = "opportunity" if total == 1 else "opportunities"
    bands = Counter(j.band for j in jobs if j.band)
    parts = [f"{total} {noun}."]
    for key in ("strong", "good", "review", "not_recommended"):
        if bands.get(key):
            n = bands[key]
            label = BAND_LABELS[key].lower()
            parts.append(f"{n} {label if n == 1 else label.replace('match', 'matches')}.")
    not_eligible = sum(1 for j in jobs if j.eligibility == "not_eligible")
    if not_eligible:
        parts.append(f"{not_eligible} not eligible under your rules.")
    unchecked = sum(1 for j in jobs if not j.band and j.eligibility != "not_eligible")
    if unchecked:
        parts.append(f"{unchecked} not checked against your evidence yet.")
    return " ".join(parts)


def source_lines(jobs: tuple[ReportJob, ...]) -> tuple[str, ...]:
    """Which sources the jobs came from, and how each came in, with counts."""
    by_source: Counter[tuple[str, str]] = Counter(
        (j.source or "Unknown", ACQUISITION_LABELS.get(j.acquisition, j.acquisition)) for j in jobs
    )
    return tuple(f"{src} ({how}): {n}" for (src, how), n in sorted(by_source.items()))


def _job_row(j: ReportJob) -> tuple[str, ...]:
    return tuple(
        neutralize(v)
        for v in (
            j.company,
            j.title,
            j.location,
            j.work_mode,
            j.employment_type,
            j.seniority,
            j.source,
            ACQUISITION_LABELS.get(j.acquisition, j.acquisition),
            j.link,
            ELIGIBILITY_LABELS.get(j.eligibility, ""),
            BAND_LABELS.get(j.band, "Not checked yet"),
            j.recommendation,
            STATE_LABELS[DecisionState(j.state)]
            if j.state in {s.value for s in DecisionState}
            else "",
            j.applied_on,
            j.added_on,
            j.note,
        )
    )


JOB_HEADERS = (
    "Company",
    "Role",
    "Location",
    "Work mode",
    "Employment type",
    "Seniority",
    "Source",
    "How it came in",
    "Posting link",
    "Eligibility",
    "Fit",
    "Why",
    "Your decision",
    "Applied on",
    "Added on",
    "Your note",
)
JOB_WIDTHS = (22, 30, 20, 12, 16, 14, 18, 22, 40, 16, 16, 50, 20, 12, 12, 40)

REQUIREMENT_HEADERS = ("Company", "Role", "Requirement", "Importance", "Evidence check", "Why")
EVIDENCE_HEADERS = ("Company", "Role", "Requirement", "Evidence from", "Kind of entry", "Quote")


def build_report(data: ReportInput) -> Report:
    jobs = data.jobs
    sentence = counts_sentence(jobs)
    when = stamp(data.generated_at)
    sources = source_lines(jobs)
    summary: list[tuple[str, str]] = [("Made on", when), ("Jobs in this report", str(len(jobs)))]
    summary += [("Chosen by", line) for line in data.criteria]
    summary += [("Source", line) for line in sources] or [("Source", "None")]
    summary.append(("In short", sentence))
    notes = [
        "Made from what is stored in Provenance on the date above. Postings change, so check the "
        "original posting before you rely on a detail.",
        "Nothing here was sent to anyone.",
    ]
    if data.truncated:
        notes.append(
            f"More jobs matched than a report holds. This report has the first {MAX_REPORT_JOBS}."
        )
    if not data.include_quotes:
        notes.append(
            "Evidence quotes are left out. Make the report again with quotes to include them."
        )

    req_rows: list[tuple[str, ...]] = []
    ev_rows: list[tuple[str, ...]] = []
    for j in jobs:
        for r in j.requirements:
            head = (neutralize(j.company), neutralize(j.title), neutralize(r.text))
            req_rows.append(
                (
                    *head,
                    neutralize(r.importance),
                    VERDICT_LABELS.get(r.verdict, r.verdict),
                    neutralize(r.reason),
                )
            )
            for e in r.evidence:
                ev_rows.append(
                    (
                        *head,
                        neutralize(e.source),
                        neutralize(e.entry),
                        neutralize(e.quote if data.include_quotes else "", MAX_QUOTE_CHARS),
                    )
                )

    tables = [
        Table("Opportunities", JOB_HEADERS, tuple(_job_row(j) for j in jobs), JOB_WIDTHS),
        Table("Requirements", REQUIREMENT_HEADERS, tuple(req_rows), (22, 30, 50, 12, 16, 50)),
        Table("Evidence", EVIDENCE_HEADERS, tuple(ev_rows), (22, 30, 50, 18, 18, 60)),
    ]
    return Report(
        title="Provenance opportunities report",
        generated_at=data.generated_at,
        summary=tuple((a, neutralize(b)) for a, b in summary),
        sentence=sentence,
        tables=tuple(tables),
        notes=tuple(notes),
        jobs=jobs,
    )


def export_filename(fmt: str, moment: datetime) -> str:
    """A name a person can find again: the date is in it, the characters are all safe."""
    return f"Provenance opportunities {moment.astimezone(UTC):%Y-%m-%d}.{fmt}"
