"""Read an uploaded spreadsheet (CSV or XLSX) into rows of text. Everything in the file is untrusted.

CSV is decoded and split with the standard library. XLSX is read straight from its ZIP and XML with
the standard library and defusedxml, so every limit is ours:
  - archive: entry count, total uncompressed size, per-entry compression ratio (zip bombs), no paths
    that climb out of the archive
  - XML: no external entities or DTDs (defusedxml) and a hard cap on the bytes read per part
  - macros: a workbook that carries a macro project is refused, never opened
  - cells: only the stored text or number is read. A formula is never calculated and an external
    link is never followed
  - size: rows, columns and cell length are capped while reading

The result is plain text per cell. Nothing in it is run or followed.
"""

import csv
import io
import re
import zipfile
from posixpath import normpath
from typing import Any

from defusedxml import ElementTree

from pv_domain.job import MAX_POSTING_CHARS
from pv_domain.job_import import (
    MAX_IMPORT_BYTES,
    MAX_IMPORT_COLUMNS,
    MAX_IMPORT_ROWS,
    ImportFileError,
)
from pv_domain.resume import MAX_ZIP_ENTRIES, MAX_ZIP_RATIO, MAX_ZIP_UNCOMPRESSED_BYTES

MAX_SHEET_XML_BYTES = 20 * 1024 * 1024
MAX_SHARED_STRINGS_BYTES = 20 * 1024 * 1024
MAX_CELL_CHARS = MAX_POSTING_CHARS + 2000  # a little over the limit, so a too-long cell is reported
_MAX_ROW_SCAN = MAX_IMPORT_ROWS + 1000  # rows read before giving up, blank ones included
csv.field_size_limit(1_000_000)  # a field over this is not a posting: the file is refused

_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
_PKG_REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"
_CELL_REF = re.compile(r"^([A-Z]{1,3})([0-9]+)$")

_ZIP_MAGIC = b"PK\x03\x04"
_OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"  # an old binary Excel file, or an encrypted one


def sniff_table_kind(data: bytes) -> str | None:
    """ "xlsx" or "csv" from the first bytes, or None. The file name and the type the browser
    claims are never used."""
    if data.startswith(_OLE_MAGIC):
        return "ole"
    if data.startswith(_ZIP_MAGIC):
        return "xlsx"
    if b"\x00" in data[:4096] and not data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return None
    head = data[:4096]
    if head.startswith(b"%PDF-") or head.startswith(b"MZ") or head.startswith(b"\x7fELF"):
        return None
    return "csv"


# ---- CSV


def _decode(data: bytes) -> str:
    if data.startswith(b"\xef\xbb\xbf"):
        return data[3:].decode("utf-8", errors="replace")
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16", errors="replace")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("cp1252", errors="replace")  # what Excel on Windows writes as "CSV"


def _delimiter(sample: str) -> str:
    first = sample.split("\n", 1)[0]
    counts = {d: first.count(d) for d in (",", ";", "\t", "|")}
    best = max(counts, key=lambda d: counts[d])
    return best if counts[best] > 0 else ","


def read_csv(data: bytes) -> list[list[str]]:
    if b"\x00" in data and not data.startswith((b"\xff\xfe", b"\xfe\xff")):
        raise ImportFileError("not_a_table")
    text = _decode(data)
    if not text.strip():
        raise ImportFileError("empty")
    rows: list[list[str]] = []
    try:
        reader = csv.reader(io.StringIO(text, newline=""), delimiter=_delimiter(text[:8192]))
        for row in reader:
            if len(rows) > _MAX_ROW_SCAN:
                raise ImportFileError("too_many_rows")
            rows.append([c[:MAX_CELL_CHARS] for c in row[:MAX_IMPORT_COLUMNS]])
    except csv.Error as exc:  # a field over the csv module's own limit, or broken quoting
        raise ImportFileError("unreadable") from exc
    return rows


# ---- XLSX


def _open_xlsx(data: bytes) -> zipfile.ZipFile:
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except (zipfile.BadZipFile, OSError, ValueError) as exc:
        raise ImportFileError("unreadable") from exc
    infos = archive.infolist()
    if len(infos) > MAX_ZIP_ENTRIES:
        raise ImportFileError("unsafe_archive")
    if sum(info.file_size for info in infos) > MAX_ZIP_UNCOMPRESSED_BYTES:
        raise ImportFileError("unsafe_archive")
    for info in infos:
        name = info.filename
        if name.startswith(("/", "\\")) or ".." in name.split("/") or "\\" in name:
            raise ImportFileError("unsafe_archive")
        if (
            info.file_size > 1_000_000
            and info.compress_size > 0
            and info.file_size / info.compress_size > MAX_ZIP_RATIO
        ):
            raise ImportFileError("unsafe_archive")
        if info.flag_bits & 0x1:
            raise ImportFileError("encrypted")
    names = {info.filename.lower() for info in infos}
    if any(n.endswith("vbaproject.bin") for n in names):
        raise ImportFileError("macros")
    if "[content_types].xml" not in names or "xl/workbook.xml" not in names:
        raise ImportFileError("not_a_table")
    return archive


def _read_part(archive: zipfile.ZipFile, name: str, limit: int) -> bytes | None:
    try:
        with archive.open(name) as handle:
            body = handle.read(limit + 1)  # one past the cap: an archive that lies is still stopped
    except KeyError:
        return None
    except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
        raise ImportFileError("unreadable") from exc
    if len(body) > limit:
        raise ImportFileError("unsafe_archive")
    return body


def _parse(xml: bytes) -> Any:
    try:
        return ElementTree.fromstring(xml)
    except Exception as exc:  # defusedxml raises several types for hostile or broken XML
        raise ImportFileError("unreadable") from exc


def _text_of(node: Any) -> str:
    """All the text of a shared string or inline string: plain runs, not phonetic hints."""
    parts: list[str] = []
    for child in node:
        if child.tag == f"{_NS}t" and child.text:
            parts.append(child.text)
        elif child.tag == f"{_NS}r":
            parts.extend(t.text or "" for t in child if t.tag == f"{_NS}t")
    return "".join(parts)


def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
    body = _read_part(archive, "xl/sharedStrings.xml", MAX_SHARED_STRINGS_BYTES)
    if body is None:
        return []
    root = _parse(body)
    return [_text_of(si)[:MAX_CELL_CHARS] for si in root.iter(f"{_NS}si")]


def _first_sheet_path(archive: zipfile.ZipFile) -> str:
    workbook = _read_part(archive, "xl/workbook.xml", 2_000_000)
    rels = _read_part(archive, "xl/_rels/workbook.xml.rels", 2_000_000)
    if workbook is None:
        raise ImportFileError("not_a_table")
    sheets = list(_parse(workbook).iter(f"{_NS}sheet"))
    if sheets and rels is not None:
        rid = sheets[0].get(f"{_REL}id")
        for rel in _parse(rels).iter(f"{_PKG_REL}Relationship"):
            target = rel.get("Target") or ""
            if rel.get("Id") == rid and rel.get("TargetMode") != "External":
                path = (
                    normpath(target.lstrip("/"))
                    if target.startswith("/")
                    else normpath("xl/" + target)
                )
                if path.startswith("xl/") and ".." not in path:
                    return path
    return "xl/worksheets/sheet1.xml"


def _column_index(letters: str) -> int:
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def read_xlsx(data: bytes) -> list[list[str]]:
    archive = _open_xlsx(data)
    try:
        shared = _shared_strings(archive)
        sheet = _read_part(archive, _first_sheet_path(archive), MAX_SHEET_XML_BYTES)
        if sheet is None:
            raise ImportFileError("not_a_table")
        root = _parse(sheet)
    finally:
        archive.close()
    rows: list[list[str]] = []
    for row in root.iter(f"{_NS}row"):
        if len(rows) > _MAX_ROW_SCAN:
            raise ImportFileError("too_many_rows")
        try:
            row_number = int(row.get("r") or len(rows) + 1)
        except ValueError:
            raise ImportFileError("unreadable") from None
        if row_number > _MAX_ROW_SCAN:
            raise ImportFileError("too_many_rows")
        while len(rows) < row_number - 1:  # rows the sheet leaves out are blank rows
            rows.append([])
        cells: list[str] = []
        for position, cell in enumerate(row.iter(f"{_NS}c")):
            ref = _CELL_REF.match(cell.get("r") or "")
            index = _column_index(ref.group(1)) if ref else position
            if index >= MAX_IMPORT_COLUMNS:
                continue
            while len(cells) < index:
                cells.append("")
            kind = cell.get("t")
            value = cell.find(f"{_NS}v")
            if kind == "s" and value is not None and (value.text or "").isdigit():
                at = int(value.text or "0")
                text = shared[at] if at < len(shared) else ""
            elif kind == "inlineStr":
                inline = cell.find(f"{_NS}is")
                text = _text_of(inline) if inline is not None else ""
            elif kind == "e":
                text = ""  # a spreadsheet error value (#REF!) is not content
            elif value is not None and value.text is not None:
                text = value.text  # str, number or boolean as stored. A formula's cached result
            else:
                text = ""
            cells.append(text[:MAX_CELL_CHARS])
        rows.append(cells)
    return rows


def read_table(data: bytes) -> tuple[str, list[list[str]]]:
    """The kind ("csv" or "xlsx") and the rows. Raises ImportFileError with a key of FILE_MESSAGES."""
    if len(data) > MAX_IMPORT_BYTES:
        raise ImportFileError("too_big")
    if not data:
        raise ImportFileError("empty")
    kind = sniff_table_kind(data)
    if kind == "ole":
        raise ImportFileError("encrypted")  # an old .xls or a protected workbook: neither is read
    if kind == "xlsx":
        return "xlsx", read_xlsx(data)
    if kind == "csv":
        return "csv", read_csv(data)
    raise ImportFileError("not_a_table")


def check_table_upload(data: bytes) -> str:
    """Cheap checks at upload time. Returns "csv" or "xlsx", or raises ImportFileError. The
    spreadsheet itself is read later, in the worker."""
    if len(data) > MAX_IMPORT_BYTES:
        raise ImportFileError("too_big")
    if not data:
        raise ImportFileError("empty")
    kind = sniff_table_kind(data)
    if kind == "ole":
        raise ImportFileError("encrypted")
    if kind is None:
        raise ImportFileError("not_a_table")
    if kind == "xlsx":
        _open_xlsx(data).close()
    return kind
