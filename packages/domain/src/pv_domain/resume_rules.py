"""Read resume text with plain rules, no AI.

Used when the AI reader is not set up, so uploading a resume still fills the profile. It finds
the usual headings (Education, Experience, Projects, Skills and so on) and copies what is written
under them. It never writes a word the resume does not contain: every value is a slice of the text.
It is less clever than the model, so the person is asked to check the entries.

Entries go through the same validation and grounding as model output (pv_domain.profile).
"""

import re
from dataclasses import dataclass, field
from typing import Any

from pv_domain.profile import entry_key, is_grounded, resume_token_set, validate_entry

RULES_PARSER_VERSION = "resume-rules-1"
MAX_ENTRIES_KEPT = 80
_MAX_SKILLS = 60
_MAX_LINKS = 6

_SECTIONS: dict[str, tuple[str, ...]] = {
    "education": ("education", "academic background", "academics", "qualifications"),
    "work": (
        "experience",
        "work experience",
        "professional experience",
        "employment",
        "employment history",
        "work history",
    ),
    "internship": ("internship", "internships", "internship experience"),
    "project": (
        "projects",
        "personal projects",
        "academic projects",
        "key projects",
        "selected projects",
    ),
    "skill": (
        "skills",
        "technical skills",
        "core skills",
        "key skills",
        "skills and tools",
        "tools and technologies",
        "technologies",
    ),
    "certification": (
        "certifications",
        "certificates",
        "licenses and certifications",
        "courses",
        "courses and certifications",
    ),
    "achievement": (
        "achievements",
        "awards",
        "honors",
        "honours",
        "awards and achievements",
        "accomplishments",
    ),
    "link": ("links", "profiles", "social"),
    "ignore": (
        "summary",
        "profile",
        "objective",
        "about me",
        "professional summary",
        "career objective",
        "interests",
        "hobbies",
        "languages",
        "references",
        "declaration",
        "personal details",
    ),
}
_HEADING_LOOKUP = {name: key for key, names in _SECTIONS.items() for name in names}

_BULLET = re.compile(r"^\s*(?:[•●▪■◦○*·►➢✓-]|\u2013|\u2014)\s+")
_MONTH = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?,?"
_DATE_TOKEN = rf"(?:{_MONTH}\s+)?(?:19|20)\d{{2}}"
_NOW = r"present|current|now|ongoing|till date|to date|date"
_RANGE = re.compile(
    rf"({_DATE_TOKEN})\s*(?:-|\u2013|\u2014|to)\s*({_DATE_TOKEN}|{_NOW})", re.IGNORECASE
)
_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
_MONTH_NUMBER = {
    name: number
    for number, name in enumerate(
        ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), 1
    )
}
_URL = re.compile(
    r"(?:https?://|www\.|github\.com/|linkedin\.com/|gitlab\.com/)[^\s,;|<>()]+", re.IGNORECASE
)
_SPLIT = re.compile(r"\s+[|\u2013\u2014-]\s+|\s+\|\s+|\s+@\s+|\s+at\s+|\s*\|\s*", re.IGNORECASE)
_INSTITUTION = re.compile(
    r"\b(university|college|institute|school|academy|polytechnic|iit|nit|iiit|vidyalaya)\b",
    re.IGNORECASE,
)
_DEGREE = re.compile(
    r"\b(b\.?\s?tech|m\.?\s?tech|b\.?\s?e\.?|m\.?\s?e\.?|b\.?\s?sc|m\.?\s?sc|b\.?\s?a\.?|m\.?\s?a\.?|"
    r"b\.?\s?com|m\.?\s?com|bca|mca|mba|bba|diploma|ph\.?d|bachelor|master|doctorate|"
    r"intermediate|higher secondary|secondary|class x|class xii|hsc|ssc)\b",
    re.IGNORECASE,
)
_GRADE = re.compile(
    r"(?:cgpa|gpa|percentage|score)\s*[:\-]?\s*([\d.]+\s*(?:/\s*[\d.]+)?\s*%?)|\b(\d{2,3}(?:\.\d+)?\s*%)",
    re.IGNORECASE,
)
_ROLE_WORD = re.compile(
    r"\b(engineer|developer|intern|analyst|manager|designer|scientist|associate|consultant|lead|"
    r"trainee|architect|administrator|researcher|assistant|executive|officer|specialist|director|"
    r"programmer|tester|technician|apprentice|fellow|coordinator|volunteer|member|head)\b",
    re.IGNORECASE,
)
_TECH_LINE = re.compile(
    r"^\s*(?:tech(?:nologies| stack)?|stack|built with|tools|tools used|technologies used)"
    r"\s*:\s*(.+)$",
    re.IGNORECASE,
)


@dataclass
class RulesOutcome:
    entries: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    dropped: int = 0


def _heading(line: str) -> str | None:
    text = line.strip().strip(":").strip()
    if not text or len(text) > 40 or any(ch.isdigit() for ch in text):
        return None
    key = " ".join(text.lower().replace("&", "and").split())
    return _HEADING_LOOKUP.get(key)


def _is_bullet(line: str) -> bool:
    return bool(_BULLET.match(line))


def _unbullet(line: str) -> str:
    return _BULLET.sub("", line, count=1).strip()


def _iso(token: str) -> str | None:
    lowered = token.strip().lower()
    if re.fullmatch(_NOW, lowered):
        return "present"
    year = _YEAR.search(lowered)
    if year is None:
        return None
    month = re.match(r"([a-z]{3})", lowered)
    number = _MONTH_NUMBER.get(month.group(1)) if month else None
    return f"{year.group(1)}-{number:02d}" if number else year.group(1)


def _strip_range(text: str) -> str:
    return _RANGE.sub(" ", text)


def _tidy(text: str) -> str:
    text = re.sub(r"\(\s*\)", " ", text)
    text = text.strip(" \t|,;:\u2013\u2014-()[]")
    return " ".join(text.split())


def _parts(text: str) -> list[str]:
    return [part for part in (_tidy(p) for p in _SPLIT.split(text)) if part]


def _clean_url(raw: str) -> str | None:
    url = raw.rstrip(".,;:)")
    if not url.lower().startswith("http"):
        url = "https://" + url
    return url if len(url) < 300 else None


def _link_label(url: str) -> str:
    host = url.split("://", 1)[1].split("/", 1)[0].lower().removeprefix("www.")
    if "github" in host:
        return "GitHub"
    if "linkedin" in host:
        return "LinkedIn"
    return host.split(".")[0].capitalize() or "Website"


def _links(lines: list[str], link_lines: list[str]) -> list[tuple[str, dict[str, Any]]]:
    found: list[tuple[str, dict[str, Any]]] = []
    seen: set[str] = set()
    for line in [*lines[:15], *link_lines]:
        for match in _URL.findall(line):
            url = _clean_url(match)
            if url is None or url.lower() in seen:
                continue
            seen.add(url.lower())
            found.append(("link", {"label": _link_label(url), "url": url}))
    return found[:_MAX_LINKS]


def _split_sections(lines: list[str]) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in lines:
        key = _heading(line)
        if key is not None:
            current = key
            sections.setdefault(key, [])
            continue
        if current is not None and line.strip():
            sections[current].append(line.rstrip())
    return sections


def _education(lines: list[str]) -> list[tuple[str, dict[str, Any]]]:
    blocks: list[list[str]] = []
    for line in lines:
        if _INSTITUTION.search(line) and not _is_bullet(line):
            blocks.append([line])
        elif blocks:
            blocks[-1].append(line)
    entries: list[tuple[str, dict[str, Any]]] = []
    for block in blocks:
        joined = " ".join(block)
        data: dict[str, Any] = {}
        for text in block:
            if "institution" not in data and _INSTITUTION.search(text):
                parts = _parts(_GRADE.sub(" ", _strip_range(text)))
                inst = next((p for p in parts if _INSTITUTION.search(p)), None)
                if inst:
                    data["institution"] = inst
                degree_part = next((p for p in parts if _DEGREE.search(p) and p != inst), None)
                if degree_part:
                    data["degree"] = degree_part
            elif "degree" not in data and _DEGREE.search(text):
                data["degree"] = _tidy(_GRADE.sub(" ", _strip_range(text)))
        grade = _GRADE.search(joined)
        if grade:
            data["grade"] = _tidy(grade.group(1) or grade.group(2))
        span = _RANGE.search(joined)
        if span:
            data["start_date"] = _iso(span.group(1))
            data["end_date"] = _iso(span.group(2))
        else:
            years = _YEAR.findall(joined)
            if years:
                data["end_date"] = years[-1]
        if data.get("institution"):
            entries.append(("education", data))
    return entries


def _role_header(lines: list[str], index: int) -> tuple[list[str], int]:
    """The title and company text around a line that holds a date range."""
    span = _RANGE.search(lines[index])
    head = _tidy(_strip_range(lines[index])) if span else ""
    texts: list[str] = []
    if head:
        texts.append(head)
    elif index > 0 and not _is_bullet(lines[index - 1]):
        texts.append(_tidy(lines[index - 1]))
    nxt = lines[index + 1] if index + 1 < len(lines) else ""
    if (
        head
        and nxt.strip()
        and not _is_bullet(nxt)
        and not _RANGE.search(nxt)
        and len(nxt) < 60
        and not nxt[:1].islower()
    ):
        texts.append(_tidy(nxt))
        return texts, index + 1
    return texts, index


def _role(entry_type: str, texts: list[str], span: re.Match[str] | None) -> dict[str, Any] | None:
    parts = [p for text in texts for p in (_parts(text) or [text])]
    if len(parts) < 2:
        return None
    title = next((p for p in parts if _ROLE_WORD.search(p)), None)
    if title is None:
        return None
    rest = [p for p in parts if p != title]
    data: dict[str, Any] = {"title": title, "company": rest[0]}
    if len(rest) > 1:
        data["location"] = rest[1]
    if span:
        data["start_date"] = _iso(span.group(1))
        data["end_date"] = _iso(span.group(2))
    return data


def _roles(entry_type: str, lines: list[str]) -> list[tuple[str, dict[str, Any]]]:
    starts = [i for i, line in enumerate(lines) if not _is_bullet(line) and _RANGE.search(line)]
    entries: list[tuple[str, dict[str, Any]]] = []
    for n, start in enumerate(starts):
        texts, last_header = _role_header(lines, start)
        end = starts[n + 1] if n + 1 < len(starts) else len(lines)
        if n + 1 < len(starts) and not _tidy(_strip_range(lines[end])):
            end -= 1  # the next entry's header sits on the line above its dates
        data = _role(entry_type, texts, _RANGE.search(lines[start]))
        if data is None:
            continue
        bullets: list[str] = []
        for text in lines[last_header + 1 : end]:
            if _is_bullet(text):
                bullets.append(_unbullet(text))
            elif bullets and text[:1].islower():
                bullets[-1] += " " + text.strip()
            elif len(text.strip()) > 25 and not _RANGE.search(text):
                bullets.append(text.strip())
        if bullets:
            data["highlights"] = bullets[:12]
        kind = "internship" if "intern" in data["title"].lower() else entry_type
        entries.append((kind, data))
    return entries


def _projects(lines: list[str]) -> list[tuple[str, dict[str, Any]]]:
    projects: list[dict[str, Any]] = []
    previous_bullet = True
    for text in lines:
        tech = _TECH_LINE.match(text)
        if tech and projects:
            listed = projects[-1].setdefault("technologies", [])
            listed.extend(t.strip() for t in re.split(r"[,;|]", tech.group(1)))
            previous_bullet = True
            continue
        if _is_bullet(text):
            if projects:
                projects[-1].setdefault("_bullets", []).append(_unbullet(text))
            previous_bullet = True
            continue
        if projects and not previous_bullet and text[:1].islower():
            bullets = projects[-1].setdefault("_bullets", [])
            if bullets:
                bullets[-1] += " " + text.strip()
            continue
        if len(text) <= 110 and (previous_bullet or not projects):
            span = _RANGE.search(text)
            head = _tidy(_strip_range(text))
            url = _URL.search(head)
            if url:
                head = _tidy(head.replace(url.group(0), " "))
            parts = _parts(head) or ([head] if head else [])
            if not parts:
                continue
            project: dict[str, Any] = {"name": parts[0]}
            if len(parts) > 1 and "," in parts[1]:
                project["technologies"] = [t.strip() for t in parts[1].split(",")]
            if url:
                project["url"] = _clean_url(url.group(0))
            if span:
                project["start_date"] = _iso(span.group(1))
                project["end_date"] = _iso(span.group(2))
            projects.append(project)
            previous_bullet = False
        elif projects:
            projects[-1].setdefault("_bullets", []).append(text.strip())
    entries: list[tuple[str, dict[str, Any]]] = []
    for project in projects:
        bullets = project.pop("_bullets", [])
        if bullets:
            project["description"] = " ".join(bullets)[:1000]
        entries.append(("project", project))
    return entries


def _skills(lines: list[str]) -> list[tuple[str, dict[str, Any]]]:
    entries: list[tuple[str, dict[str, Any]]] = []
    for line in lines:
        text = _unbullet(line)
        category: str | None = None
        if ":" in text:
            head, _, text = text.partition(":")
            if len(head.strip()) <= 40:
                category = _tidy(head)
        for item in re.split(r"[,;|•·]", text):
            name = _tidy(item)
            if name and len(name) <= 50 and len(name.split()) <= 4:
                data: dict[str, Any] = {"name": name}
                if category:
                    data["category"] = category
                entries.append(("skill", data))
    return entries[:_MAX_SKILLS]


def _certifications(lines: list[str]) -> list[tuple[str, dict[str, Any]]]:
    entries: list[tuple[str, dict[str, Any]]] = []
    for line in lines:
        text = _unbullet(line)
        if len(text) < 4 or (text[:1].islower() and entries):
            continue
        year = _YEAR.search(text)
        body = _tidy(_YEAR.sub(" ", text)) if year else _tidy(text)
        parts = re.split(r"\s+[|\u2013\u2014-]\s+|\s+by\s+|,\s+", body, maxsplit=1)
        data: dict[str, Any] = {"name": _tidy(parts[0])}
        if len(parts) > 1 and _tidy(parts[1]):
            data["issuer"] = _tidy(parts[1])
        if year:
            data["date"] = year.group(1)
        entries.append(("certification", data))
    return entries


def _achievements(lines: list[str]) -> list[tuple[str, dict[str, Any]]]:
    entries: list[tuple[str, dict[str, Any]]] = []
    for line in lines:
        text = _unbullet(line)
        if len(text) < 4:
            continue
        if text[:1].islower() and entries:
            continue  # a wrapped line, the earlier title already holds the thought
        entries.append(("achievement", {"title": _tidy(text)[:160]}))
    return entries


def parse_resume_rules(resume_text: str) -> RulesOutcome:
    """Fill profile entries from resume text with rules. Nothing here can add a word."""
    lines = [line for line in resume_text.replace("\r", "\n").split("\n")]
    sections = _split_sections(lines)
    found: list[tuple[str, dict[str, Any]]] = []
    found += _links([line for line in lines if line.strip()], sections.get("link", []))
    found += _education(sections.get("education", []))
    found += _roles("work", sections.get("work", []))
    found += _roles("internship", sections.get("internship", []))
    found += _projects(sections.get("project", []))
    found += _skills(sections.get("skill", []))
    found += _certifications(sections.get("certification", []))
    found += _achievements(sections.get("achievement", []))

    tokens = resume_token_set(resume_text)
    outcome = RulesOutcome()
    seen: set[str] = set()
    for entry_type, data in found:
        check = validate_entry(entry_type, data, lenient=True)
        if check.errors or not is_grounded(entry_type, check.clean, tokens):
            outcome.dropped += 1
            continue
        key = entry_key(entry_type, check.clean)
        if key in seen:
            continue
        seen.add(key)
        if len(outcome.entries) >= MAX_ENTRIES_KEPT:
            outcome.dropped += 1
            continue
        outcome.entries.append((entry_type, check.clean))
    return outcome
