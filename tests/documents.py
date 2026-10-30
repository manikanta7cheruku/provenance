"""Builds small, valid PDF and DOCX files for tests, with no extra libraries.

The PDF is hand-written (header, objects, cross-reference table) so tests control the page
count and the text. The DOCX is a ZIP with the three parts a reader needs.
"""

import io
import zipfile

RESUME_LINES = [
    "Asha Verma",
    "Bengaluru, India  asha.verma@example.com  github.com/ashaverma",
    "EDUCATION",
    "BMS College of Engineering - B.E. Computer Science, 2021 to 2025, CGPA 8.4",
    "EXPERIENCE",
    "Kestrel Analytics - Data Intern, June 2024 to August 2024",
    "Cleaned and merged six CSV sources with pandas before analysis.",
    "Wrote SQL joins over 1.2 million order rows to find late deliveries.",
    "PROJECTS",
    "Delivery delay report - Python, SQL, Plotly dashboard for operations leads.",
    "SKILLS",
    "Python, SQL, pandas, Git, Plotly",
    "CERTIFICATIONS",
    "SQL for data analysis, issued by Example Learning, 2023",
]
RESUME_TEXT = "\n".join(RESUME_LINES)


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def make_pdf(pages: list[list[str]]) -> bytes:
    """One content stream per page. Each inner list is the lines of that page."""
    objects: list[bytes] = []
    page_ids = [4 + 2 * index for index in range(len(pages))]
    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode())
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    for index, lines in enumerate(pages):
        content_id = page_ids[index] + 1
        body = "BT /F1 11 Tf 50 760 Td 14 TL\n" + "\n".join(
            f"({_escape(line)}) Tj T*" for line in lines
        )
        stream = (body + "\nET").encode("latin-1", "replace")
        objects.append(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_id} 0 R >>"
            ).encode()
        )
        objects.append(f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream")
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(out.tell())
        out.write(f"{number} 0 obj\n".encode() + body + b"\nendobj\n")
    xref = out.tell()
    out.write(f"xref\n0 {len(objects) + 1}\n".encode())
    out.write(b"0000000000 65535 f \n")
    for offset in offsets:
        out.write(f"{offset:010d} 00000 n \n".encode())
    out.write(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    return out.getvalue()


def resume_pdf(lines: list[str] | None = None) -> bytes:
    return make_pdf([lines or RESUME_LINES])


_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def make_docx(paragraphs: list[str], *, document_xml: str | None = None) -> bytes:
    body = "".join(
        f'<w:p><w:r><w:t xml:space="preserve">{_xml(p)}</w:t></w:r></w:p>' for p in paragraphs
    )
    xml = document_xml or (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:document xmlns:w="{_W}"><w:body>{body}</w:body></w:document>'
    )
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/'
            'content-types"><Default Extension="xml" ContentType="application/xml"/></Types>',
        )
        archive.writestr("word/document.xml", xml)
    return out.getvalue()


def resume_docx(lines: list[str] | None = None) -> bytes:
    return make_docx(lines or RESUME_LINES)


def _xml(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
