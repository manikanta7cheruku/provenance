"""Turn an uploaded resume into plain text. Everything in the file is untrusted.

PDF text comes from pypdf. DOCX is read straight from its ZIP and XML with the standard
library and defusedxml, so we control every limit:
  - archive: entry count, total uncompressed size and per-entry compression ratio (zip bombs)
  - XML: no external entities or DTDs (defusedxml), and a hard cap on bytes read
  - text: page and character caps
The extracted text is data. Nothing in it is ever run or followed as an instruction.
"""

import io
import re
import zipfile
from dataclasses import dataclass

from defusedxml import ElementTree
from pypdf import PdfReader

from pv_domain.resume import (
    MAX_DOCUMENT_XML_BYTES,
    MAX_PAGES,
    MAX_TEXT_CHARS,
    MAX_ZIP_ENTRIES,
    MAX_ZIP_RATIO,
    MAX_ZIP_UNCOMPRESSED_BYTES,
    MIN_TEXT_CHARS,
    ParseErrorCode,
    detect_kind,
)

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_BLANK_LINES = re.compile(r"\n{3,}")
_SPACES = re.compile(r"[ \t ]+")


class ExtractionError(Exception):
    """Extraction stopped for a known, content-free reason."""

    def __init__(self, code: ParseErrorCode) -> None:
        super().__init__(code.value)
        self.code = code


@dataclass(frozen=True)
class ExtractedText:
    text: str
    pages: int | None


def _open_docx(data: bytes) -> zipfile.ZipFile:
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except (zipfile.BadZipFile, OSError, ValueError) as exc:
        raise ExtractionError(ParseErrorCode.FILE_UNREADABLE) from exc
    infos = archive.infolist()
    if len(infos) > MAX_ZIP_ENTRIES:
        raise ExtractionError(ParseErrorCode.UNSAFE_ARCHIVE)
    if sum(info.file_size for info in infos) > MAX_ZIP_UNCOMPRESSED_BYTES:
        raise ExtractionError(ParseErrorCode.UNSAFE_ARCHIVE)
    for info in infos:
        name = info.filename
        if name.startswith(("/", "\\")) or ".." in name.split("/"):
            raise ExtractionError(ParseErrorCode.UNSAFE_ARCHIVE)
        if (
            info.file_size > 1_000_000
            and info.compress_size > 0
            and info.file_size / info.compress_size > MAX_ZIP_RATIO
        ):
            raise ExtractionError(ParseErrorCode.UNSAFE_ARCHIVE)
    names = {info.filename for info in infos}
    if "[Content_Types].xml" not in names or "word/document.xml" not in names:
        raise ExtractionError(ParseErrorCode.FILE_UNREADABLE)
    return archive


def _docx_text(data: bytes) -> str:
    archive = _open_docx(data)
    with archive.open("word/document.xml") as handle:
        # Read one byte past the cap so an archive that lies about its size is still stopped.
        xml = handle.read(MAX_DOCUMENT_XML_BYTES + 1)
    if len(xml) > MAX_DOCUMENT_XML_BYTES:
        raise ExtractionError(ParseErrorCode.UNSAFE_ARCHIVE)
    try:
        root = ElementTree.fromstring(xml)
    except Exception as exc:  # defusedxml raises several types for hostile or broken XML
        raise ExtractionError(ParseErrorCode.FILE_UNREADABLE) from exc
    paragraphs: list[str] = []
    for paragraph in root.iter(f"{_W}p"):
        parts: list[str] = []
        for node in paragraph.iter():
            if node.tag == f"{_W}t" and node.text:
                parts.append(node.text)
            elif node.tag == f"{_W}tab":
                parts.append("\t")
            elif node.tag in (f"{_W}br", f"{_W}cr"):
                parts.append("\n")
        paragraphs.append("".join(parts))
        if sum(len(p) for p in paragraphs) > MAX_TEXT_CHARS * 2:
            raise ExtractionError(ParseErrorCode.TOO_LONG)
    return "\n".join(paragraphs)


def _pdf_text(data: bytes) -> tuple[str, int]:
    try:
        reader = PdfReader(io.BytesIO(data), strict=False)
        if reader.is_encrypted:
            raise ExtractionError(ParseErrorCode.ENCRYPTED)
        page_count = len(reader.pages)
        if page_count > MAX_PAGES:
            raise ExtractionError(ParseErrorCode.TOO_MANY_PAGES)
        chunks: list[str] = []
        total = 0
        for page in reader.pages:
            chunk = page.extract_text() or ""
            total += len(chunk)
            if total > MAX_TEXT_CHARS * 2:
                raise ExtractionError(ParseErrorCode.TOO_LONG)
            chunks.append(chunk)
    except ExtractionError:
        raise
    except Exception as exc:  # pypdf raises many types for damaged or hostile files
        raise ExtractionError(ParseErrorCode.FILE_UNREADABLE) from exc
    return "\n".join(chunks), page_count


def _normalise(text: str) -> str:
    lines = [_SPACES.sub(" ", line).strip() for line in text.replace("\r\n", "\n").split("\n")]
    return _BLANK_LINES.sub("\n\n", "\n".join(lines)).strip()


def extract_text(kind: str, data: bytes) -> ExtractedText:
    """Return the resume text, or raise ExtractionError with a short reason code."""
    pages: int | None = None
    if kind == "pdf":
        raw, pages = _pdf_text(data)
    elif kind == "docx":
        raw = _docx_text(data)
    else:
        raise ExtractionError(ParseErrorCode.FILE_UNREADABLE)
    text = _normalise(raw)
    if len(text) > MAX_TEXT_CHARS:
        raise ExtractionError(ParseErrorCode.TOO_LONG)
    if len(text) < MIN_TEXT_CHARS:
        raise ExtractionError(ParseErrorCode.NO_TEXT)
    return ExtractedText(text=text, pages=pages)


def check_upload(data: bytes) -> str | None:
    """Cheap checks at upload time. Returns "pdf" or "docx", or None if the file is neither.

    The type comes from the first bytes only. A DOCX must also be a safe archive with the
    expected parts. The deeper PDF checks (pages, encryption, text) run in the worker.
    """
    kind = detect_kind(data)
    if kind == "docx":
        try:
            _open_docx(data).close()
        except ExtractionError:
            return None
    return kind
