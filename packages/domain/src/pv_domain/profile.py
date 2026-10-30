"""Profile entries: what each type contains, how it is validated and how it is grounded.

Pure code, shared by the API (user edits) and the worker (resume parsing), so both apply the
same rules. The field specs are also served to the browser, which draws its forms from them:
there is one definition of "what is an education entry".
"""

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

MAX_LIST_ITEMS = 30
MAX_LIST_ITEM_LENGTH = 80
MAX_URL_LENGTH = 500

_DATE = re.compile(r"^(\d{4})(-(0[1-9]|1[0-2]))?$")


@dataclass(frozen=True)
class FieldSpec:
    name: str
    label: str
    kind: str  # text, longtext, date, url, list
    max_length: int = 200
    required: bool = False
    # Recommended fields do not block saving. A missing one marks the entry "needs correction".
    recommended: bool = False
    hint: str = ""


@dataclass(frozen=True)
class EntrySpec:
    entry_type: str
    label: str
    plural: str
    primary_field: str
    fields: tuple[FieldSpec, ...]
    # Fields that identify an entry, used to spot duplicates between a re-parse and user edits.
    key_fields: tuple[str, ...] = field(default=())

    @property
    def field_names(self) -> frozenset[str]:
        return frozenset(f.name for f in self.fields)


_START = FieldSpec("start_date", "Start", "date", 7, recommended=True, hint="YYYY or YYYY-MM")
_END = FieldSpec("end_date", "End", "date", 7, hint="YYYY, YYYY-MM or present")

_ROLE_FIELDS = (
    FieldSpec("company", "Company", "text", 120, required=True),
    FieldSpec("title", "Role", "text", 120, required=True),
    FieldSpec("location", "Location", "text", 120),
    _START,
    _END,
    FieldSpec(
        "highlights",
        "What you did",
        "list",
        400,
        recommended=True,
        hint="One achievement per line. Say what you did and what changed.",
    ),
)

ENTRY_SPECS: dict[str, EntrySpec] = {
    spec.entry_type: spec
    for spec in (
        EntrySpec(
            "education",
            "Education",
            "Education",
            "institution",
            (
                FieldSpec("institution", "Institution", "text", 160, required=True),
                FieldSpec("degree", "Degree", "text", 120, recommended=True),
                FieldSpec("field_of_study", "Field of study", "text", 120),
                _START,
                FieldSpec("end_date", "End or expected end", "date", 7, recommended=True),
                FieldSpec("grade", "Grade or CGPA", "text", 40),
                FieldSpec("details", "Details", "longtext", 1000),
            ),
            key_fields=("institution", "degree"),
        ),
        EntrySpec(
            "work",
            "Work experience",
            "Work experience",
            "company",
            _ROLE_FIELDS,
            key_fields=("company", "title"),
        ),
        EntrySpec(
            "internship",
            "Internship",
            "Internships",
            "company",
            _ROLE_FIELDS,
            key_fields=("company", "title"),
        ),
        EntrySpec(
            "project",
            "Project",
            "Projects",
            "name",
            (
                FieldSpec("name", "Project name", "text", 120, required=True),
                FieldSpec("description", "What it is", "longtext", 1000, recommended=True),
                FieldSpec("technologies", "Technologies", "list", 60),
                FieldSpec("url", "Link", "url", MAX_URL_LENGTH),
                _START,
                _END,
            ),
            key_fields=("name",),
        ),
        EntrySpec(
            "skill",
            "Skill",
            "Skills",
            "name",
            (
                FieldSpec("name", "Skill", "text", 80, required=True),
                FieldSpec("category", "Group", "text", 60, hint="For example Languages or Tools"),
            ),
            key_fields=("name",),
        ),
        EntrySpec(
            "certification",
            "Certification",
            "Certifications",
            "name",
            (
                FieldSpec("name", "Certification", "text", 160, required=True),
                FieldSpec("issuer", "Issued by", "text", 120, recommended=True),
                FieldSpec("date", "Date", "date", 7),
                FieldSpec("url", "Link", "url", MAX_URL_LENGTH),
            ),
            key_fields=("name", "issuer"),
        ),
        EntrySpec(
            "achievement",
            "Achievement",
            "Achievements",
            "title",
            (
                FieldSpec("title", "Achievement", "text", 160, required=True),
                FieldSpec("description", "Details", "longtext", 600),
                FieldSpec("date", "Date", "date", 7),
            ),
            key_fields=("title",),
        ),
        EntrySpec(
            "link",
            "Link",
            "Links",
            "url",
            (
                FieldSpec("label", "Label", "text", 60, required=True, hint="For example GitHub"),
                FieldSpec("url", "Address", "url", MAX_URL_LENGTH, required=True),
            ),
            key_fields=("url",),
        ),
    )
}

ENTRY_TYPES = tuple(ENTRY_SPECS)


@dataclass(frozen=True)
class EntryCheck:
    """Outcome of validating one entry's data."""

    clean: dict[str, Any]
    # Field name -> plain sentence. Non-empty means the entry is not acceptable.
    errors: dict[str, str]
    # Fields whose value was invalid and removed (lenient mode only).
    dropped_fields: tuple[str, ...]


def _clean_text(value: Any, max_length: int, *, multiline: bool) -> str | None:
    if not isinstance(value, str):
        return None
    text = unicodedata.normalize("NFC", value).replace("\r\n", "\n").replace("\r", "\n")
    text = "".join(ch for ch in text if ch == "\n" or ch == "\t" or ord(ch) >= 32)
    text = text.strip() if multiline else " ".join(text.split())
    if not text or len(text) > max_length:
        return None
    return text


def _clean_url(value: Any, max_length: int) -> str | None:
    text = _clean_text(value, max_length, multiline=False)
    if text is None or " " in text:
        return None
    lowered = text.lower()
    if not (lowered.startswith("https://") or lowered.startswith("http://")):
        return None
    if len(text.split("://", 1)[1]) < 3:
        return None
    return text


def _clean_date(value: Any) -> str | None:
    text = _clean_text(value, 7, multiline=False)
    if text is None:
        return None
    if text.lower() == "present":
        return "present"
    return text if _DATE.match(text) else None


def _clean_list(value: Any, max_length: int) -> list[str] | None:
    if isinstance(value, str):
        value = [line for line in value.split("\n")]
    if not isinstance(value, list):
        return None
    items: list[str] = []
    for item in value[:MAX_LIST_ITEMS]:
        cleaned = _clean_text(item, max_length, multiline=False)
        if cleaned:
            items.append(cleaned)
    return items or None


_ERROR_BY_KIND = {
    "text": "Enter a shorter value.",
    "longtext": "Enter a shorter value.",
    "date": "Use YYYY or YYYY-MM, or the word present for an end date.",
    "url": "Enter a full address that starts with https:// or http://.",
    "list": "Enter one item per line, each a short phrase.",
}


def validate_entry(entry_type: str, data: Any, *, lenient: bool = False) -> EntryCheck:
    """Check and normalise one entry.

    Strict (user input): any invalid field is an error the user can fix.
    Lenient (model output): invalid optional values are dropped, and only a missing or invalid
    required field makes the entry unacceptable. Unknown fields are always discarded.
    """
    spec = ENTRY_SPECS.get(entry_type)
    if spec is None:
        return EntryCheck({}, {"entry_type": "Unknown entry type."}, ())
    raw = data if isinstance(data, dict) else {}
    clean: dict[str, Any] = {}
    errors: dict[str, str] = {}
    dropped: list[str] = []
    for spec_field in spec.fields:
        value = raw.get(spec_field.name)
        empty = value is None or value == "" or value == []
        if empty:
            if spec_field.required:
                errors[spec_field.name] = "This is required."
            continue
        cleaned: Any
        if spec_field.kind in ("text", "longtext"):
            cleaned = _clean_text(
                value, spec_field.max_length, multiline=spec_field.kind == "longtext"
            )
        elif spec_field.kind == "date":
            cleaned = _clean_date(value)
        elif spec_field.kind == "url":
            cleaned = _clean_url(value, spec_field.max_length)
        else:
            cleaned = _clean_list(value, spec_field.max_length)
        if cleaned is None:
            if lenient and not spec_field.required:
                dropped.append(spec_field.name)
            else:
                errors[spec_field.name] = (
                    "This is required."
                    if spec_field.required and lenient
                    else _ERROR_BY_KIND[spec_field.kind]
                )
            continue
        clean[spec_field.name] = cleaned
    return EntryCheck(clean, errors, tuple(dropped))


def flagged_fields(entry_type: str, clean: dict[str, Any]) -> list[str]:
    """Recommended fields still empty. Advice for the user, never a reason to refuse the entry."""
    spec = ENTRY_SPECS.get(entry_type)
    if spec is None:
        return []
    return [f.name for f in spec.fields if f.recommended and not clean.get(f.name)]


# ---- grounding: a parsed entry must be visible in the resume text

_WORD = re.compile(r"[a-z0-9]+")
_STOP_WORDS = frozenset(
    {"a", "an", "and", "at", "for", "from", "in", "of", "on", "the", "to", "with", "by", "or"}
)
_URL_NOISE = frozenset({"http", "https", "www"})


def _tokens(text: str) -> list[str]:
    folded = unicodedata.normalize("NFKC", text).casefold()
    return _WORD.findall(folded)


def resume_token_set(resume_text: str) -> frozenset[str]:
    return frozenset(_tokens(resume_text))


def significant_tokens(value: str) -> list[str]:
    return [t for t in _tokens(value) if t not in _STOP_WORDS and t not in _URL_NOISE]


def is_grounded(entry_type: str, clean: dict[str, Any], resume_tokens: frozenset[str]) -> bool:
    """True when every meaningful word of the entry's main field appears in the resume text.

    This catches invented employers, schools and projects. It does not prove a bullet is true;
    the later checkpoints add claim-level checks. An entry with no meaningful word is dropped.
    """
    spec = ENTRY_SPECS.get(entry_type)
    if spec is None:
        return False
    primary = clean.get(spec.primary_field)
    if not isinstance(primary, str):
        return False
    words = significant_tokens(primary)
    return bool(words) and all(word in resume_tokens for word in words)


def entry_key(entry_type: str, clean: dict[str, Any]) -> str:
    """A stable identity for duplicate detection, built from the spec's key fields."""
    spec = ENTRY_SPECS.get(entry_type)
    if spec is None:
        return ""
    parts = [" ".join(significant_tokens(str(clean.get(name, "")))) for name in spec.key_fields]
    return f"{entry_type}|" + "|".join(parts)


def specs_as_dicts() -> list[dict[str, Any]]:
    """The field specs in a JSON-friendly form for the browser."""
    return [
        {
            "entry_type": spec.entry_type,
            "label": spec.label,
            "plural": spec.plural,
            "primary_field": spec.primary_field,
            "fields": [
                {
                    "name": f.name,
                    "label": f.label,
                    "kind": f.kind,
                    "max_length": f.max_length,
                    "required": f.required,
                    "recommended": f.recommended,
                    "hint": f.hint,
                }
                for f in spec.fields
            ],
        }
        for spec in ENTRY_SPECS.values()
    ]
