"""Write a Report (pv_domain.report) as CSV, an Excel workbook or a Word document.

The two Office formats are written straight from their XML with the standard library, the same way
tabular.py reads them, so no document library is added to the supply chain and every byte written
is ours. They are checked in the tests by opening them with real readers (openpyxl and python-docx,
which are test-only).

What makes the output safe:
  - cells arrive already neutralized (pv_domain.report.neutralize): no leading = + - @ and no
    characters XML forbids. Labels written here go through clean_text as well
  - every string in a workbook is an inline string, never a formula, and no formula is ever written
  - nothing in either file refers to anything outside it: no links that fetch, no external
    relationships, no macros
  - the same Report always gives the same bytes (a fixed timestamp inside the archive), so a report
    can be compared and a test can pin it
"""

import csv
import io
import zipfile
from collections.abc import Sequence
from xml.sax.saxutils import escape

from pv_domain.report import (
    BAND_LABELS,
    ELIGIBILITY_LABELS,
    VERDICT_LABELS,
    Report,
    ReportJob,
    Table,
    clean_text,
)

_FIXED_TIME = (2000, 1, 1, 0, 0, 0)
_XML_HEAD = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
_MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
_CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
_W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _esc(value: str) -> str:
    return escape(clean_text(value, 32000, strip=False))


def _zip(parts: list[tuple[str, str]]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in parts:
            info = zipfile.ZipInfo(name, _FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            archive.writestr(info, content.encode("utf-8"))
    return buffer.getvalue()


# ---------------------------------------------------------------------------------------- CSV


def write_csv(report: Report) -> bytes:
    """The opportunities as one flat table. UTF-8 with a byte order mark so Excel reads accents."""
    table = report.tables[0]
    out = io.StringIO(newline="")
    writer = csv.writer(out, lineterminator="\r\n")
    writer.writerow([clean_text(h) for h in table.headers])
    for row in table.rows:
        writer.writerow(row)
    return b"\xef\xbb\xbf" + out.getvalue().encode("utf-8")


# --------------------------------------------------------------------------------------- XLSX


def _column(index: int) -> str:
    letters = ""
    index += 1
    while index:
        index, rest = divmod(index - 1, 26)
        letters = chr(65 + rest) + letters
    return letters


def _cell(ref: str, value: str, style: int) -> str:
    if value == "":
        return f'<c r="{ref}" s="{style}"/>'
    return f'<c r="{ref}" s="{style}" t="inlineStr"><is><t xml:space="preserve">{_esc(value)}</t></is></c>'


def _sheet_xml(rows: list[list[str]], widths: tuple[int, ...], *, header: bool) -> str:
    body: list[str] = []
    for r, row in enumerate(rows, start=1):
        style = 1 if header and r == 1 else 2
        cells = "".join(_cell(f"{_column(c)}{r}", v, style) for c, v in enumerate(row))
        body.append(f'<row r="{r}">{cells}</row>')
    cols = "".join(
        f'<col min="{i}" max="{i}" width="{w}" customWidth="1"/>'
        for i, w in enumerate(widths, start=1)
    )
    columns = max((len(r) for r in rows), default=1)
    last = f"{_column(columns - 1)}{max(len(rows), 1)}"
    pane = (
        '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" '
        'activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
        if header
        else '<sheetViews><sheetView workbookViewId="0"/></sheetViews>'
    )
    autofilter = f'<autoFilter ref="A1:{last}"/>' if header and len(rows) > 1 else ""
    return (
        f'{_XML_HEAD}<worksheet xmlns="{_MAIN_NS}">{pane}<sheetFormatPr defaultRowHeight="15"/>'
        f"<cols>{cols}</cols><sheetData>{''.join(body)}</sheetData>{autofilter}</worksheet>"
    )


def _styles_xml() -> str:
    return (
        f'{_XML_HEAD}<styleSheet xmlns="{_MAIN_NS}">'
        '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font>'
        '<font><b/><sz val="11"/><name val="Calibri"/></font></fonts>'
        '<fills count="3"><fill><patternFill patternType="none"/></fill>'
        '<fill><patternFill patternType="gray125"/></fill>'
        '<fill><patternFill patternType="solid"><fgColor rgb="FFE9E4D8"/></patternFill></fill></fills>'
        '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
        '<cellXfs count="3">'
        '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
        '<xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1" '
        'applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf>'
        '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1">'
        '<alignment vertical="top" wrapText="1"/></xf>'
        "</cellXfs>"
        '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
        "</styleSheet>"
    )


def write_xlsx(report: Report) -> bytes:
    """Sheets: Summary, then Opportunities, Requirements and Evidence."""
    summary_rows: list[list[str]] = [[report.title, ""]]
    summary_rows += [[label, value] for label, value in report.summary]
    summary_rows.append(["", ""])
    summary_rows += [["Note", note] for note in report.notes]
    sheets: list[tuple[str, str]] = [("Summary", _sheet_xml(summary_rows, (24, 100), header=False))]
    for table in report.tables:
        rows = [list(table.headers), *[list(r) for r in table.rows]]
        sheets.append((table.name, _sheet_xml(rows, table.widths, header=True)))

    overrides = "".join(
        f'<Override PartName="/xl/worksheets/sheet{i}.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for i in range(1, len(sheets) + 1)
    )
    content_types = (
        f'{_XML_HEAD}<Types xmlns="{_CT_NS}">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/styles.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        f"{overrides}</Types>"
    )
    root_rels = (
        f'{_XML_HEAD}<Relationships xmlns="{_PKG_REL_NS}">'
        f'<Relationship Id="rId1" Type="{_REL_NS}/officeDocument" Target="xl/workbook.xml"/>'
        "</Relationships>"
    )
    workbook = (
        f'{_XML_HEAD}<workbook xmlns="{_MAIN_NS}" xmlns:r="{_REL_NS}"><sheets>'
        + "".join(
            f'<sheet name="{escape(name)}" sheetId="{i}" r:id="rId{i}"/>'
            for i, (name, _x) in enumerate(sheets, start=1)
        )
        + "</sheets></workbook>"
    )
    workbook_rels = (
        f'{_XML_HEAD}<Relationships xmlns="{_PKG_REL_NS}">'
        + "".join(
            f'<Relationship Id="rId{i}" Type="{_REL_NS}/worksheet" Target="worksheets/sheet{i}.xml"/>'
            for i in range(1, len(sheets) + 1)
        )
        + f'<Relationship Id="rId{len(sheets) + 1}" Type="{_REL_NS}/styles" Target="styles.xml"/>'
        "</Relationships>"
    )
    parts = [
        ("[Content_Types].xml", content_types),
        ("_rels/.rels", root_rels),
        ("xl/workbook.xml", workbook),
        ("xl/_rels/workbook.xml.rels", workbook_rels),
        ("xl/styles.xml", _styles_xml()),
    ]
    parts += [(f"xl/worksheets/sheet{i}.xml", xml) for i, (_n, xml) in enumerate(sheets, start=1)]
    return _zip(parts)


# --------------------------------------------------------------------------------------- DOCX


def _run(text: str, *, bold: bool = False, italic: bool = False) -> str:
    props = ("<w:b/>" if bold else "") + ("<w:i/>" if italic else "")
    rpr = f"<w:rPr>{props}</w:rPr>" if props else ""
    return f'<w:r>{rpr}<w:t xml:space="preserve">{_esc(text)}</w:t></w:r>'


def _para(*runs: str, style: str | None = None, indent: int = 0) -> str:
    ppr = ""
    if style or indent:
        ppr = "<w:pPr>"
        if style:
            ppr += f'<w:pStyle w:val="{style}"/>'
        if indent:
            ppr += f'<w:ind w:left="{indent}"/>'
        ppr += "</w:pPr>"
    return f"<w:p>{ppr}{''.join(runs)}</w:p>"


def _table(headers: tuple[str, ...], rows: Sequence[tuple[str, ...]]) -> str:
    def cell(text: str, *, bold: bool = False) -> str:
        return f'<w:tc><w:tcPr><w:tcW w:w="0" w:type="auto"/></w:tcPr>{_para(_run(text, bold=bold))}</w:tc>'

    head = (
        "<w:tr><w:trPr><w:tblHeader/></w:trPr>"
        + "".join(cell(h, bold=True) for h in headers)
        + "</w:tr>"
    )
    body = "".join("<w:tr>" + "".join(cell(c) for c in row) + "</w:tr>" for row in rows)
    return (
        '<w:tbl><w:tblPr><w:tblStyle w:val="TableGrid"/><w:tblW w:w="5000" w:type="pct"/></w:tblPr>'
        f"{head}{body}</w:tbl>"
    )


def _job_block(job: ReportJob) -> list[str]:
    name = (
        ", ".join(p for p in (clean_text(job.company), clean_text(job.title)) if p)
        or "Untitled job"
    )
    out = [_para(_run(name), style="Heading2")]
    facts = [
        ("Fit", BAND_LABELS.get(job.band, "Not checked yet")),
        ("Eligibility", ELIGIBILITY_LABELS.get(job.eligibility, "")),
        ("Why", job.recommendation),
        ("Where", ", ".join(p for p in (job.location, job.work_mode, job.employment_type) if p)),
        ("Source", job.source),
        ("Posting", job.link),
        ("Your note", job.note),
    ]
    for label, value in facts:
        if value:
            out.append(_para(_run(f"{label}: ", bold=True), _run(value)))
    if job.requirements:
        out.append(_para(_run("What it asks for", bold=True)))
    for req in job.requirements:
        verdict = VERDICT_LABELS.get(req.verdict, req.verdict)
        kind = f" ({req.importance.lower()})" if req.importance else ""
        out.append(_para(_run(f"{req.text}{kind}: ", bold=True), _run(verdict), indent=360))
        if req.reason:
            out.append(_para(_run(req.reason, italic=True), indent=720))
        for ev in req.evidence:
            line = f"Evidence: {ev.source}, {ev.entry}" if ev.entry else f"Evidence: {ev.source}"
            out.append(_para(_run(line), indent=720))
            if ev.quote:
                out.append(_para(_run(ev.quote, italic=True), indent=1080))
    return out


def write_docx(report: Report) -> bytes:
    """A report to read and edit: the summary, a table of the jobs, then each job in turn."""
    body: list[str] = [_para(_run(report.title), style="Title")]
    for label, value in report.summary:
        body.append(_para(_run(f"{label}: ", bold=True), _run(value)))
    body.append(_para(_run("Jobs"), style="Heading1"))
    overview = [
        (
            clean_text(j.company),
            clean_text(j.title),
            clean_text(j.location),
            BAND_LABELS.get(j.band, "Not checked yet"),
            ELIGIBILITY_LABELS.get(j.eligibility, ""),
        )
        for j in report.jobs
    ]
    body.append(_table(("Company", "Role", "Location", "Fit", "Eligibility"), overview))
    body.append(_para(_run("Job by job"), style="Heading1"))
    for job in report.jobs:
        body.extend(_job_block(job))
    body.append(_para(_run("Notes"), style="Heading1"))
    for note in report.notes:
        body.append(_para(_run(note)))
    section = (
        '<w:sectPr><w:pgSz w:w="12240" w:h="15840"/>'
        '<w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134" w:header="708" '
        'w:footer="708" w:gutter="0"/></w:sectPr>'
    )
    document = f'{_XML_HEAD}<w:document xmlns:w="{_W_NS}"><w:body>{"".join(body)}{section}</w:body></w:document>'
    styles = (
        f'{_XML_HEAD}<w:styles xmlns:w="{_W_NS}">'
        '<w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/>'
        '<w:sz w:val="22"/></w:rPr></w:rPrDefault>'
        '<w:pPrDefault><w:pPr><w:spacing w:after="120" w:line="264" w:lineRule="auto"/></w:pPr>'
        "</w:pPrDefault></w:docDefaults>"
        '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>'
        '<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/>'
        '<w:pPr><w:spacing w:after="240"/></w:pPr><w:rPr><w:b/><w:sz w:val="40"/></w:rPr></w:style>'
        '<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/>'
        '<w:basedOn w:val="Normal"/><w:pPr><w:keepNext/><w:spacing w:before="360" w:after="120"/>'
        '<w:outlineLvl w:val="0"/></w:pPr><w:rPr><w:b/><w:sz w:val="30"/></w:rPr></w:style>'
        '<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/>'
        '<w:basedOn w:val="Normal"/><w:pPr><w:keepNext/><w:spacing w:before="280" w:after="80"/>'
        '<w:outlineLvl w:val="1"/></w:pPr><w:rPr><w:b/><w:sz w:val="26"/></w:rPr></w:style>'
        '<w:style w:type="table" w:default="1" w:styleId="TableNormal"><w:name w:val="Normal Table"/>'
        '<w:tblPr><w:tblCellMar><w:top w:w="0" w:type="dxa"/><w:left w:w="108" w:type="dxa"/>'
        '<w:bottom w:w="0" w:type="dxa"/><w:right w:w="108" w:type="dxa"/></w:tblCellMar></w:tblPr></w:style>'
        '<w:style w:type="table" w:styleId="TableGrid"><w:name w:val="Table Grid"/>'
        '<w:basedOn w:val="TableNormal"/><w:tblPr><w:tblBorders>'
        + "".join(
            f'<w:{side} w:val="single" w:sz="4" w:space="0" w:color="999999"/>'
            for side in ("top", "left", "bottom", "right", "insideH", "insideV")
        )
        + "</w:tblBorders></w:tblPr></w:style></w:styles>"
    )
    content_types = (
        f'{_XML_HEAD}<Types xmlns="{_CT_NS}">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        '<Override PartName="/word/styles.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
        "</Types>"
    )
    root_rels = (
        f'{_XML_HEAD}<Relationships xmlns="{_PKG_REL_NS}">'
        f'<Relationship Id="rId1" Type="{_REL_NS}/officeDocument" Target="word/document.xml"/>'
        "</Relationships>"
    )
    document_rels = (
        f'{_XML_HEAD}<Relationships xmlns="{_PKG_REL_NS}">'
        f'<Relationship Id="rId1" Type="{_REL_NS}/styles" Target="styles.xml"/>'
        "</Relationships>"
    )
    return _zip(
        [
            ("[Content_Types].xml", content_types),
            ("_rels/.rels", root_rels),
            ("word/document.xml", document),
            ("word/styles.xml", styles),
            ("word/_rels/document.xml.rels", document_rels),
        ]
    )


def write_report(report: Report, fmt: str) -> bytes:
    if fmt == "csv":
        return write_csv(report)
    if fmt == "xlsx":
        return write_xlsx(report)
    if fmt == "docx":
        return write_docx(report)
    raise ValueError(f"Unknown report format: {fmt}")


__all__ = ["Table", "write_csv", "write_docx", "write_report", "write_xlsx"]
