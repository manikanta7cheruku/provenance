"""Checkpoint 3.4: the report rules and the three file formats.

The Office files are opened with real readers (openpyxl, python-docx), which are test-only, so
"opens in a standard viewer" is checked rather than assumed.
"""

import csv
import io
import zipfile
from datetime import UTC, datetime

import pytest
from docx import Document
from openpyxl import load_workbook

from pv_domain.pipeline import WorkQuery
from pv_domain.report import (
    BAND_LABELS,
    JOB_HEADERS,
    ReportEvidence,
    ReportInput,
    ReportJob,
    ReportRequirement,
    build_report,
    clean_text,
    counts_sentence,
    describe_query,
    export_filename,
    neutralize,
    source_lines,
)
from pv_files import read_table, write_csv, write_docx, write_report, write_xlsx

WHEN = datetime(2026, 11, 5, 9, 30, tzinfo=UTC)

ATTACKS = [
    '=HYPERLINK("http://evil.example","x")',
    "+1+1",
    "-2+3",
    "@SUM(A1:A2)",
    "\t=1+1",
    "\r=1+1",
]


def job(**over: object) -> ReportJob:
    base: dict[str, object] = {
        "id": "j1",
        "title": "Backend Engineer",
        "company": "Acme",
        "location": "Pune",
        "work_mode": "hybrid",
        "employment_type": "full-time",
        "seniority": "mid",
        "source": "Acme careers",
        "acquisition": "source_job",
        "link": "https://acme.example/jobs/1",
        "eligibility": "eligible",
        "band": "strong",
        "recommendation": "4 of 5 requirements are supported.",
        "state": "saved",
        "applied_on": "",
        "note": "",
        "added_on": "2026-11-01",
        "requirements": (
            ReportRequirement(
                "5 years of Python",
                "Required",
                "met",
                "Your resume shows 6 years.",
                (ReportEvidence("Resume", "Experience", "Built billing services in Python."),),
            ),
            ReportRequirement("Kubernetes", "Preferred", "not_verified", "Not in your evidence."),
        ),
    }
    base.update(over)
    return ReportJob(**base)  # type: ignore[arg-type]


def data(*jobs: ReportJob, quotes: bool = True, truncated: bool = False) -> ReportInput:
    return ReportInput(
        generated_at=WHEN,
        criteria=describe_query(WorkQuery()),
        jobs=tuple(jobs),
        include_quotes=quotes,
        truncated=truncated,
    )


# ------------------------------------------------------------------ making a cell safe


@pytest.mark.parametrize("attack", ATTACKS)
def test_a_cell_that_could_be_a_formula_gets_an_apostrophe(attack: str) -> None:
    assert neutralize(attack).startswith("'")
    assert neutralize(attack).strip("'").startswith(attack.strip()[:1]) or attack[0] in "\t\r"


def test_ordinary_text_is_left_alone() -> None:
    assert neutralize("Backend Engineer") == "Backend Engineer"
    assert neutralize("C++ and C#") == "C++ and C#"
    assert neutralize("5 - 7 years") == "5 - 7 years"  # only a LEADING character matters


def test_characters_xml_forbids_are_dropped() -> None:
    assert clean_text("a\x00b\x0bc\x1fd￾e") == "abcde"
    assert clean_text("tab\tnewline\nok") == "tab\tnewline\nok"


def test_a_long_cell_is_cut_with_an_ellipsis() -> None:
    cut = clean_text("x" * 9000)
    assert len(cut) == 5000 and cut.endswith("…")
    assert neutralize(None) == ""


# ------------------------------------------------------------------ what the report says


def test_the_sentence_counts_stored_jobs_in_the_required_words() -> None:
    jobs = (
        job(band="strong"),
        job(band="strong"),
        job(band="good"),
        job(band="", eligibility="not_eligible"),
        job(band="", eligibility="eligible"),
    )
    text = counts_sentence(jobs)
    assert text.startswith("5 opportunities.")
    assert "2 strong matches." in text and "1 good match." in text
    assert "1 not eligible under your rules." in text
    assert "1 not checked against your evidence yet." in text
    assert counts_sentence((job(),)).startswith("1 opportunity.")


def test_sources_are_listed_with_how_each_came_in() -> None:
    lines = source_lines((job(), job(), job(source="My paste", acquisition="user_paste")))
    assert "Acme careers (Found by a job source): 2" in lines
    assert "My paste (Pasted by you): 1" in lines


def test_the_criteria_are_in_words() -> None:
    query = WorkQuery(view="saved", text="python", bands=frozenset({"strong"}), company="Acme")
    lines = describe_query(query)
    assert lines[0] == "List: Saved"
    assert "Words: python" in lines and "Company: Acme" in lines and "Fit: Strong match" in lines


def test_the_report_says_when_it_was_made_and_where_jobs_came_from() -> None:
    report = build_report(data(job()))
    summary = dict((a, b) for a, b in report.summary)
    assert summary["Made on"] == "2026-11-05 09:30 UTC"
    assert any(label == "Source" and "Acme careers" in value for label, value in report.summary)
    assert any(label == "Chosen by" for label, _ in report.summary)
    assert report.sentence in summary["In short"]


def test_the_same_data_gives_the_same_report_and_the_same_bytes() -> None:
    one = write_xlsx(build_report(data(job())))
    two = write_xlsx(build_report(data(job())))
    assert one == two
    assert write_docx(build_report(data(job()))) == write_docx(build_report(data(job())))


def test_a_truncated_report_says_so_and_leaving_quotes_out_says_so() -> None:
    report = build_report(data(job(), quotes=False, truncated=True))
    assert any("first 500" in n for n in report.notes)
    assert any("quotes are left out" in n.lower() for n in report.notes)
    assert all(not e[-1] for e in report.tables[2].rows) or report.tables[2].rows == ()


def test_the_file_name_has_the_date_and_only_safe_characters() -> None:
    assert export_filename("xlsx", WHEN) == "Provenance opportunities 2026-11-05.xlsx"


# ------------------------------------------------------------------ CSV


def test_csv_has_a_byte_order_mark_and_reads_back() -> None:
    raw = write_csv(build_report(data(job(title="Café engineer, senior"))))
    assert raw.startswith(b"\xef\xbb\xbf")
    rows = list(csv.reader(io.StringIO(raw.decode("utf-8-sig"))))
    assert tuple(rows[0]) == JOB_HEADERS
    assert rows[1][1] == "Café engineer, senior" and rows[1][0] == "Acme"
    assert len(rows) == 2


@pytest.mark.parametrize("attack", ATTACKS)
def test_csv_neutralizes_every_formula_start(attack: str) -> None:
    raw = write_csv(build_report(data(job(title=attack, company=attack, note=attack))))
    rows = list(csv.reader(io.StringIO(raw.decode("utf-8-sig"))))
    for cell in rows[1]:
        assert not cell.startswith(("=", "+", "-", "@", "\t", "\r"))
    assert rows[1][0].startswith("'")


def test_csv_with_no_jobs_is_a_header_only() -> None:
    rows = list(csv.reader(io.StringIO(write_csv(build_report(data())).decode("utf-8-sig"))))
    assert len(rows) == 1


def test_our_own_reader_reads_the_csv_we_write() -> None:
    kind, rows = read_table(write_csv(build_report(data(job()))))
    assert kind == "csv" and rows[0][0] == "Company" and rows[1][0] == "Acme"


# ------------------------------------------------------------------ XLSX


def test_xlsx_opens_with_a_real_reader_and_has_the_four_sheets() -> None:
    book = load_workbook(io.BytesIO(write_xlsx(build_report(data(job())))))
    assert book.sheetnames == ["Summary", "Opportunities", "Requirements", "Evidence"]
    opportunities = book["Opportunities"]
    assert [c.value for c in opportunities[1]] == list(JOB_HEADERS)
    assert opportunities["A2"].value == "Acme" and opportunities["B2"].value == "Backend Engineer"
    assert opportunities["K2"].value == BAND_LABELS["strong"]
    assert opportunities.freeze_panes == "A2"
    assert book["Requirements"]["C2"].value == "5 years of Python"
    assert book["Evidence"]["F2"].value == "Built billing services in Python."


def test_the_workbook_summary_has_the_time_the_sources_and_the_sentence() -> None:
    book = load_workbook(io.BytesIO(write_xlsx(build_report(data(job())))))
    cells = [(r[0].value, r[1].value) for r in book["Summary"].iter_rows()]
    assert ("Made on", "2026-11-05 09:30 UTC") in cells
    assert any(a == "Source" and "Acme careers" in (b or "") for a, b in cells)
    assert any(a == "In short" and "1 opportunity." in (b or "") for a, b in cells)


@pytest.mark.parametrize("attack", ATTACKS)
def test_the_workbook_never_holds_a_formula(attack: str) -> None:
    raw = write_xlsx(build_report(data(job(title=attack, company=attack, note=attack))))
    book = load_workbook(io.BytesIO(raw))
    for sheet in book:
        for row in sheet.iter_rows():
            for cell in row:
                assert cell.data_type != "f"
                if isinstance(cell.value, str):
                    assert not cell.value.startswith(("=", "+", "-", "@"))
    assert book["Opportunities"]["A2"].value.startswith("'")  # type: ignore[union-attr]


def test_the_workbook_carries_no_macro_no_link_and_no_outside_reference() -> None:
    raw = write_xlsx(build_report(data(job(link="https://acme.example/x"))))
    names = zipfile.ZipFile(io.BytesIO(raw)).namelist()
    assert not any("vba" in n.lower() or "external" in n.lower() for n in names)
    for name in names:
        text = zipfile.ZipFile(io.BytesIO(raw)).read(name).decode()
        assert "TargetMode" not in text and "<f>" not in text


def test_our_own_xlsx_reader_reads_the_workbook_we_write() -> None:
    kind, rows = read_table(write_xlsx(build_report(data(job()))))
    assert kind == "xlsx" and rows and rows[0][0] == "Provenance opportunities report"


def test_odd_characters_do_not_break_the_workbook() -> None:
    odd = job(title='Engineer\x00\x0b <b>&</b> "quoted"', note="line one\nline two")
    book = load_workbook(io.BytesIO(write_xlsx(build_report(data(odd)))))
    assert book["Opportunities"]["B2"].value == 'Engineer <b>&</b> "quoted"'
    assert book["Opportunities"]["P2"].value == "line one\nline two"


def test_a_hundred_jobs_make_a_workbook_that_still_opens() -> None:
    many = tuple(job(id=str(i), title=f"Role {i}") for i in range(100))
    book = load_workbook(io.BytesIO(write_xlsx(build_report(data(*many)))))
    assert book["Opportunities"].max_row == 101
    assert book["Requirements"].max_row == 201


# ------------------------------------------------------------------ DOCX


def test_docx_opens_with_a_real_reader_and_reads_job_by_job() -> None:
    doc = Document(io.BytesIO(write_docx(build_report(data(job())))))
    text = "\n".join(p.text for p in doc.paragraphs)
    assert "Provenance opportunities report" in text
    assert "Made on: 2026-11-05 09:30 UTC" in text
    assert "Acme careers" in text
    assert "5 years of Python (required): Shown" in text
    assert "Built billing services in Python." in text
    assert "Nothing here was sent to anyone." in text
    headings = [p.text for p in doc.paragraphs if p.style.name.startswith("Heading")]
    assert "Jobs" in headings and "Acme, Backend Engineer" in headings
    table = doc.tables[0]
    assert [c.text for c in table.rows[0].cells] == [
        "Company", "Role", "Location", "Fit", "Eligibility"
    ]  # fmt: skip
    assert table.rows[1].cells[0].text == "Acme"


def test_docx_leaves_quotes_out_when_not_asked() -> None:
    plain = job(
        requirements=(
            ReportRequirement(
                "Python", "Required", "met", "ok", (ReportEvidence("Resume", "Experience", ""),)
            ),
        )
    )
    doc = Document(io.BytesIO(write_docx(build_report(data(plain, quotes=False)))))
    text = "\n".join(p.text for p in doc.paragraphs)
    assert "Evidence: Resume, Experience" in text and "Built billing" not in text


def test_docx_survives_odd_characters_and_has_no_outside_reference() -> None:
    raw = write_docx(build_report(data(job(title='A\x00B <&> "x"', note="=1+1"))))
    doc = Document(io.BytesIO(raw))
    assert any("A" in p.text and "B <&>" in p.text for p in doc.paragraphs)
    archive = zipfile.ZipFile(io.BytesIO(raw))
    assert not any("TargetMode" in archive.read(n).decode() for n in archive.namelist())
    assert not any(n.lower().endswith((".bin", ".vba")) for n in archive.namelist())


def test_docx_with_no_jobs_still_opens() -> None:
    doc = Document(io.BytesIO(write_docx(build_report(data()))))
    assert any("Provenance opportunities report" in p.text for p in doc.paragraphs)


def test_write_report_picks_the_format_and_refuses_an_unknown_one() -> None:
    report = build_report(data(job()))
    assert write_report(report, "csv").startswith(b"\xef\xbb\xbf")
    assert write_report(report, "xlsx")[:2] == b"PK" and write_report(report, "docx")[:2] == b"PK"
    with pytest.raises(ValueError):
        write_report(report, "pdf")
