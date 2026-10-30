"""Resume file rules. Pure functions and constants: no I/O, no framework.

The limits are the single source of truth. The API checks the cheap ones at upload, the worker
checks the rest while extracting text, and the documentation quotes these numbers.
"""

import re
import unicodedata
from enum import StrEnum

from pv_domain.states import ResumeUiState

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_PAGES = 12
MAX_TEXT_CHARS = 60_000
MIN_TEXT_CHARS = 200

# DOCX is a ZIP archive. These limits stop decompression bombs before anything is parsed.
MAX_ZIP_ENTRIES = 500
MAX_ZIP_UNCOMPRESSED_BYTES = 40 * 1024 * 1024
MAX_ZIP_RATIO = 100
MAX_DOCUMENT_XML_BYTES = 20 * 1024 * 1024

PARSER_VERSION = "resume-parse-1"

MEDIA_TYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

_PDF_MAGIC = b"%PDF-"
_ZIP_MAGIC = b"PK\x03\x04"


class ParseStatus(StrEnum):
    UPLOADED = "uploaded"
    PARSING = "parsing"
    PARSED = "parsed"
    PARSE_FAILED = "parse_failed"


class ReviewStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"


class ParseErrorCode(StrEnum):
    """Short, content-free reasons a parse stopped. Each has a user-facing sentence in the API."""

    FILE_UNREADABLE = "file_unreadable"
    ENCRYPTED = "encrypted"
    TOO_MANY_PAGES = "too_many_pages"
    TOO_LONG = "too_long"
    NO_TEXT = "no_text"
    UNSAFE_ARCHIVE = "unsafe_archive"
    AI_NOT_CONFIGURED = "ai_not_configured"
    AI_UNAVAILABLE = "ai_unavailable"
    AI_BAD_OUTPUT = "ai_bad_output"
    FILE_MISSING = "file_missing"


ERROR_MESSAGES: dict[str, str] = {
    ParseErrorCode.FILE_UNREADABLE: (
        "We could not read this file. Try exporting it again as a PDF or DOCX."
    ),
    ParseErrorCode.ENCRYPTED: (
        "This PDF is password protected. Remove the password and upload it again."
    ),
    ParseErrorCode.TOO_MANY_PAGES: (
        f"This resume has more than {MAX_PAGES} pages. Upload a shorter version."
    ),
    ParseErrorCode.TOO_LONG: (
        "This resume has far more text than a resume should. Upload a shorter version."
    ),
    ParseErrorCode.NO_TEXT: (
        "We found no readable text. If this is a scanned image, export a text version instead."
    ),
    ParseErrorCode.UNSAFE_ARCHIVE: (
        "This file could not be opened safely. Export it again from your editor."
    ),
    ParseErrorCode.AI_NOT_CONFIGURED: (
        "The reading service is not set up yet. Your file is safe. Try again later."
    ),
    ParseErrorCode.AI_UNAVAILABLE: (
        "The reading service did not answer. Your file is safe. Try again in a few minutes."
    ),
    ParseErrorCode.AI_BAD_OUTPUT: (
        "We could not turn this resume into a profile. Your file is safe. Try again, "
        "or add your details by hand."
    ),
    ParseErrorCode.FILE_MISSING: "The stored file could not be found. Upload it again.",
}


def detect_kind(data: bytes) -> str | None:
    """Decide the file type from the first bytes. Filename and Content-Type are never trusted."""
    if data.startswith(_PDF_MAGIC):
        return "pdf"
    if data.startswith(_ZIP_MAGIC):
        return "docx"  # confirmed by the structure check in pv_files.extract
    return None


_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


def safe_display_filename(name: str) -> str:
    """A name safe to show and to put in a Content-Disposition header. Never used as a path."""
    base = name.replace("\\", "/").rsplit("/", 1)[-1]
    base = unicodedata.normalize("NFC", _CONTROL.sub("", base)).strip().strip(".")
    base = base.replace('"', "").replace(";", "_")
    return base[:120] or "resume"


def resume_ui_state(
    parse_status: str, review_status: str, flagged_entry_count: int
) -> ResumeUiState:
    """Map stored facts to what the user sees. The browser adds Idle and Uploading itself."""
    if parse_status == ParseStatus.PARSE_FAILED:
        return ResumeUiState.FAILED
    if parse_status == ParseStatus.UPLOADED:
        return ResumeUiState.UPLOADED
    if parse_status == ParseStatus.PARSING:
        return ResumeUiState.PARSING
    if review_status == ReviewStatus.CONFIRMED:
        return ResumeUiState.CONFIRMED
    return ResumeUiState.NEEDS_CORRECTION if flagged_entry_count > 0 else ResumeUiState.PARSED
