"""Build small spreadsheet files for tests. Real XLSX structure, written with the standard library."""

import io
import zipfile
from xml.sax.saxutils import escape

_CT = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="xml" ContentType="application/xml"/></Types>'
)
_WB = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
    'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
    '<sheets><sheet name="Jobs" sheetId="1" r:id="rId1"/></sheets></workbook>'
)
_RELS = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="worksheet" Target="worksheets/sheet1.xml"/></Relationships>'
)
_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


def _col(index: int) -> str:
    letters = ""
    index += 1
    while index:
        index, rem = divmod(index - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


def make_xlsx(
    rows: list[list[str]],
    *,
    inline: bool = False,
    extra: dict[str, bytes] | None = None,
    sheet_xml: str | None = None,
    skip_rows: tuple[int, ...] = (),
) -> bytes:
    """A workbook with one sheet. Strings go to the shared string table unless inline=True."""
    shared: list[str] = []
    body: list[str] = []
    for r, row in enumerate(rows, start=1):
        if r in skip_rows:
            continue
        cells: list[str] = []
        for c, value in enumerate(row):
            ref = f"{_col(c)}{r}"
            if value == "":
                continue
            if inline:
                cells.append(f'<c r="{ref}" t="inlineStr"><is><t>{escape(value)}</t></is></c>')
            else:
                shared.append(value)
                cells.append(f'<c r="{ref}" t="s"><v>{len(shared) - 1}</v></c>')
        body.append(f'<row r="{r}">{"".join(cells)}</row>')
    sheet = sheet_xml or (
        f'<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="{_NS}"><sheetData>'
        f"{''.join(body)}</sheetData></worksheet>"
    )
    strings = (
        f'<?xml version="1.0" encoding="UTF-8"?><sst xmlns="{_NS}">'
        + "".join(f"<si><t>{escape(s)}</t></si>" for s in shared)
        + "</sst>"
    )
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", _CT)
        z.writestr("xl/workbook.xml", _WB)
        z.writestr("xl/_rels/workbook.xml.rels", _RELS)
        z.writestr("xl/worksheets/sheet1.xml", sheet)
        z.writestr("xl/sharedStrings.xml", strings)
        for name, data in (extra or {}).items():
            z.writestr(name, data)
    return out.getvalue()


def csv_bytes(rows: list[list[str]], delimiter: str = ",", encoding: str = "utf-8") -> bytes:
    def quote(cell: str) -> str:
        if any(ch in cell for ch in (delimiter, '"', "\n")):
            return '"' + cell.replace('"', '""') + '"'
        return cell

    return "\r\n".join(delimiter.join(quote(c) for c in row) for row in rows).encode(encoding)


LONG = (
    "We are hiring a backend engineer to build and run services in Python and PostgreSQL. You will "
    "design APIs, review code, and own what you ship. Two or more years of experience are required."
)
