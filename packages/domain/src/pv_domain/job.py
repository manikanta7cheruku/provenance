"""Job postings: limits, vocabularies, quote finding and the user-facing state.

Pure code. A pasted posting is untrusted text. Everything the model says about it must be found
in it again (find_quote) before it is stored.
"""

import hashlib
import re
import unicodedata
from enum import StrEnum

from pv_domain.states import JobUiState

MIN_POSTING_CHARS = 100
MAX_POSTING_CHARS = 20_000
MAX_QUOTE_CHARS = 400
MAX_REQUIREMENTS_KEPT = 40

ACQUISITION_USER_PASTE = "user_paste"
VISIBILITY_PRIVATE = "private"

# What the person tells us about where the text came from. It is a label they choose, stored
# separately from how the text reached us (acquisition_method), and shown honestly.
SOURCE_NAMES = (
    "LinkedIn",
    "Wellfound",
    "Indeed",
    "Naukri",
    "Internshala",
    "Company career page",
    "Message or referral",
    "Other",
)

WORK_MODES = ("remote", "hybrid", "onsite")
EMPLOYMENT_TYPES = ("full_time", "part_time", "internship", "contract", "freelance")
SENIORITY_LEVELS = ("intern", "entry", "mid", "senior", "lead")
SPONSORSHIP_VALUES = ("offered", "not_offered")
REQUIREMENT_KINDS = ("required", "preferred")
REQUIREMENT_CATEGORIES = (
    "skill",
    "experience",
    "education",
    "certification",
    "language",
    "work_authorization",
    "location",
    "other",
)

PROMPT_VERSION = "job-extract-1"


class JobParseStatus(StrEnum):
    QUEUED = "queued"
    EXTRACTING = "extracting"
    EXTRACTED = "extracted"
    FAILED = "failed"


class JobErrorCode(StrEnum):
    """Short, content-free reasons a posting could not be read."""

    AI_NOT_CONFIGURED = "ai_not_configured"
    AI_UNAVAILABLE = "ai_unavailable"
    AI_BAD_OUTPUT = "ai_bad_output"
    NO_REQUIREMENTS = "no_requirements"


JOB_ERROR_MESSAGES: dict[str, str] = {
    JobErrorCode.AI_NOT_CONFIGURED: (
        "The reading service is not set up yet. Your posting is saved. Try again later."
    ),
    JobErrorCode.AI_UNAVAILABLE: (
        "The reading service did not answer. Your posting is saved. Try again in a few minutes."
    ),
    JobErrorCode.AI_BAD_OUTPUT: (
        "We could not turn this posting into a clear list of requirements. Your posting is saved. "
        "Try again."
    ),
    JobErrorCode.NO_REQUIREMENTS: (
        "We could not find any requirements in this text. Check that you pasted the whole "
        "posting, not only its title."
    ),
}

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_BLANKS = re.compile(r"\n{3,}")
_SPACES = re.compile(r"\s+")


def clean_posting_text(text: str) -> str:
    """Normalise a pasted posting: newlines, control characters, runs of blank lines."""
    cleaned = unicodedata.normalize("NFC", text).replace("\r\n", "\n").replace("\r", "\n")
    cleaned = _CONTROL.sub("", cleaned)
    return _BLANKS.sub("\n\n", cleaned).strip()


def posting_content_hash(clean_text: str) -> str:
    """Fingerprint for "the same posting". Spacing and capitals do not make a new posting."""
    folded = _SPACES.sub(" ", clean_text).strip().casefold()
    return hashlib.sha256(folded.encode()).hexdigest()


_EN, _EM = chr(0x2013), chr(0x2014)
_SINGLE = "['" + chr(0x2018) + chr(0x2019) + "]"
_DOUBLE = '["' + chr(0x201C) + chr(0x201D) + "]"
_DASH_CLASS = "[-" + _EN + _EM + "]"
_DASHES = frozenset("-" + _EN + _EM)
_QUOTE_CLASSES = {
    "'": _SINGLE,
    chr(0x2018): _SINGLE,
    chr(0x2019): _SINGLE,
    '"': _DOUBLE,
    chr(0x201C): _DOUBLE,
    chr(0x201D): _DOUBLE,
    "-": _DASH_CLASS,
    _EN: _DASH_CLASS,
    _EM: _DASH_CLASS,
}


def _token_pattern(token: str) -> str:
    if set(token) <= _DASHES:
        return _DASH_CLASS + "{1,3}"  # a dash, a double hyphen or a long dash all mean the same
    return "".join(_QUOTE_CLASSES.get(ch) or re.escape(ch) for ch in token)


def find_quote(text: str, quote: str) -> tuple[int, int] | None:
    """Where the quote appears in the text, or None. Whitespace, capitals and the kind of quotation
    mark or dash may differ. The words and their order may not. The returned span is of the
    original text, so what we store is always a real piece of the posting."""
    tokens = quote.split()
    if not tokens or len(quote) > MAX_QUOTE_CHARS:
        return None
    pattern = r"\s+".join(_token_pattern(token) for token in tokens)
    match = re.search(pattern, text, flags=re.IGNORECASE)
    return (match.start(), match.end()) if match else None


def job_ui_state(parse_status: str) -> JobUiState:
    if parse_status == JobParseStatus.EXTRACTED:
        return JobUiState.READY
    if parse_status == JobParseStatus.FAILED:
        return JobUiState.FAILED
    return JobUiState.READING
