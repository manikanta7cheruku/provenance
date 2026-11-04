"""Reading uploaded spreadsheets. Every file here is hostile until proven otherwise."""

import io
import zipfile

import pytest
from table_helpers import LONG, csv_bytes, make_xlsx

from pv_domain.job_import import MAX_IMPORT_BYTES, ImportFileError
from pv_files.tabular import check_table_upload, read_csv, read_table, read_xlsx, sniff_table_kind

ROWS = [["Title", "Description"], ["Engineer", LONG], ["Analyst, senior", 'Says "hello"\nand more']]


def code_of(data: bytes) -> str:
    with pytest.raises(ImportFileError) as error:
        read_table(data)
    return error.value.code


# ---- csv


def test_a_csv_is_read_with_quotes_commas_and_line_breaks_inside_cells() -> None:
    kind, rows = read_table(csv_bytes(ROWS))
    assert kind == "csv" and rows == ROWS


@pytest.mark.parametrize("delimiter", [";", "\t", "|"])
def test_other_delimiters_are_found(delimiter: str) -> None:
    assert read_table(csv_bytes(ROWS, delimiter))[1] == ROWS


def test_a_byte_order_mark_is_not_part_of_the_first_header() -> None:
    data = b"\xef\xbb\xbf" + csv_bytes(ROWS)
    assert read_table(data)[1][0][0] == "Title"


def test_utf16_exports_are_read() -> None:
    data = csv_bytes(ROWS).decode().encode("utf-16")  # Python writes the byte order mark itself
    assert read_table(data)[1] == ROWS


def test_windows_text_is_read_when_it_is_not_utf8() -> None:
    data = csv_bytes([["Title", "Description"], ["Caf\xe9 manager", LONG]], encoding="cp1252")
    assert read_table(data)[1][1][0] == "Café manager"


def test_a_csv_with_a_null_byte_is_not_a_table() -> None:
    assert code_of(b"Title,Description\n\x00\x00binary,stuff") == "not_a_table"


@pytest.mark.parametrize("data", [b"%PDF-1.7\n1 0 obj", b"MZ\x90\x00\x03", b"\x7fELF\x02\x01"])
def test_programs_and_pdfs_are_not_tables(data: bytes) -> None:
    assert code_of(data) == "not_a_table"


def test_an_empty_file_and_a_blank_file() -> None:
    assert code_of(b"") == "empty"
    assert code_of(b"   \n \r\n") == "empty"


def test_a_huge_cell_is_cut_not_trusted() -> None:
    rows = read_csv(csv_bytes([["Description"], ["x" * 200_000]]))
    assert len(rows[1][0]) < 30_000


def test_far_too_many_rows_stop_the_read() -> None:
    data = ("Description\n" + "a\n" * 5000).encode()
    assert code_of(data) == "too_many_rows"


def test_the_size_limit_applies() -> None:
    assert code_of(b"a," * (MAX_IMPORT_BYTES // 2 + 10)) == "too_big"


def test_columns_beyond_the_limit_are_ignored() -> None:
    row = ",".join(str(i) for i in range(500))
    rows = read_csv(f"{row}\n{row}".encode())
    assert len(rows[0]) <= 40


# ---- xlsx


def test_an_xlsx_is_read_with_shared_and_inline_strings() -> None:
    assert read_table(make_xlsx(ROWS))[1] == ROWS
    assert read_table(make_xlsx(ROWS, inline=True))[1] == ROWS


def test_missing_cells_and_rows_are_blank_not_shifted() -> None:
    rows = read_xlsx(make_xlsx([["A", "", "C"], ["x", "y", "z"], ["p", "q", "r"]], skip_rows=(2,)))
    assert rows[0] == ["A", "", "C"]
    assert rows[1] == []  # a row the sheet leaves out is a blank row, so row numbers stay true
    assert rows[2] == ["p", "q", "r"]


def test_a_formula_cell_gives_its_stored_value_and_is_never_calculated() -> None:
    sheet = (
        '<?xml version="1.0"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<sheetData><row r="1"><c r="A1" t="str"><f>HYPERLINK("http://evil","x")</f><v>shown text</v></c>'
        '<c r="B1"><f>1+1</f><v>2</v></c><c r="C1" t="e"><v>#REF!</v></c></row></sheetData></worksheet>'
    )
    assert read_xlsx(make_xlsx([], sheet_xml=sheet))[0] == ["shown text", "2", ""]


def test_rich_text_cells_keep_their_words_and_drop_phonetic_hints() -> None:
    sheet = (
        '<?xml version="1.0"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<sheetData><row r="1"><c r="A1" t="inlineStr"><is><r><t>Back</t></r><r><t>end</t></r>'
        "<rPh><t>HINT</t></rPh></is></c></row></sheetData></worksheet>"
    )
    assert read_xlsx(make_xlsx([], sheet_xml=sheet))[0] == ["Backend"]


def test_a_workbook_with_macros_is_refused_and_never_opened() -> None:
    assert code_of(make_xlsx(ROWS, extra={"xl/vbaProject.bin": b"\x00macro"})) == "macros"


def test_an_old_binary_or_protected_workbook_is_refused() -> None:
    assert code_of(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 100) == "encrypted"


def test_a_zip_that_is_not_a_workbook_is_refused() -> None:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        z.writestr("readme.txt", "hello")
    assert code_of(out.getvalue()) == "not_a_table"


def test_a_damaged_zip_is_unreadable() -> None:
    assert code_of(b"PK\x03\x04" + b"junk" * 50) == "unreadable"


def test_a_path_that_climbs_out_of_the_archive_is_refused() -> None:
    assert code_of(make_xlsx(ROWS, extra={"../../evil.txt": b"x"})) == "unsafe_archive"
    assert code_of(make_xlsx(ROWS, extra={"/etc/passwd": b"x"})) == "unsafe_archive"


def test_a_zip_bomb_is_refused_before_anything_is_expanded() -> None:
    bomb = make_xlsx(ROWS, extra={"xl/media/big.bin": b"\x00" * (30 * 1024 * 1024)})
    assert len(bomb) < 200_000  # tiny on disk, huge when opened
    assert code_of(bomb) == "unsafe_archive"


def test_too_many_entries_are_refused() -> None:
    many = {f"xl/extra/{i}.xml": b"<a/>" for i in range(600)}
    assert code_of(make_xlsx(ROWS, extra=many)) == "unsafe_archive"


def test_an_entry_that_lies_about_its_size_is_stopped_by_the_read_cap() -> None:
    out = io.BytesIO()
    sheet = (
        b'<?xml version="1.0"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
        + b" " * (21 * 1024 * 1024)
        + b"</sheetData></worksheet>"
    )
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("xl/workbook.xml", "<workbook/>")
        z.writestr("xl/worksheets/sheet1.xml", sheet)
    assert code_of(out.getvalue()) in {"unsafe_archive"}


def test_an_encrypted_entry_is_refused() -> None:
    data = bytearray(make_xlsx(ROWS))
    # Set the "encrypted" bit in the first local header and in the central directory.
    first = data.index(b"PK\x03\x04")
    data[first + 6] |= 0x1
    for at in range(len(data) - 4):
        if data[at : at + 4] == b"PK\x01\x02":
            data[at + 8] |= 0x1
    assert code_of(bytes(data)) == "encrypted"


def test_an_external_entity_in_the_sheet_is_not_followed() -> None:
    hostile = (
        '<?xml version="1.0"?><!DOCTYPE x [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
        '<row r="1"><c r="A1" t="inlineStr"><is><t>&xxe;</t></is></c></row></sheetData></worksheet>'
    )
    assert code_of(make_xlsx([], sheet_xml=hostile)) == "unreadable"


def test_a_billion_laughs_document_is_not_expanded() -> None:
    hostile = (
        '<?xml version="1.0"?><!DOCTYPE lolz [<!ENTITY a "lol"><!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;">'
        '<!ENTITY c "&b;&b;&b;&b;&b;&b;&b;&b;">]><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>&c;</t></is></c></row></sheetData></worksheet>'
    )
    assert code_of(make_xlsx([], sheet_xml=hostile)) == "unreadable"


def test_far_too_many_rows_in_a_sheet_stop_the_read() -> None:
    sheet = (
        '<?xml version="1.0"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
        '<row r="1"><c r="A1" t="inlineStr"><is><t>Description</t></is></c></row>'
        '<row r="1048576"><c r="A1048576" t="inlineStr"><is><t>x</t></is></c></row></sheetData></worksheet>'
    )
    assert code_of(make_xlsx([], sheet_xml=sheet)) == "too_many_rows"


def test_a_sheet_that_is_not_xml_is_unreadable() -> None:
    assert code_of(make_xlsx([], sheet_xml="this is not xml at all")) == "unreadable"


# ---- the upload check


def test_the_upload_check_names_the_kind_without_reading_the_sheet() -> None:
    assert check_table_upload(csv_bytes(ROWS)) == "csv"
    assert check_table_upload(make_xlsx(ROWS)) == "xlsx"


@pytest.mark.parametrize(
    ("data", "code"),
    [
        (b"", "empty"),
        (b"%PDF-1.4", "not_a_table"),
        (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"x" * 20, "encrypted"),
        (b"a" * (MAX_IMPORT_BYTES + 1), "too_big"),
        (b"PK\x03\x04junk", "unreadable"),
        (make_xlsx(ROWS, extra={"xl/vbaProject.bin": b"x"}), "macros"),
    ],
    ids=["empty", "pdf", "old-binary", "too-big", "damaged-zip", "macros"],
)
def test_the_upload_check_refuses_early(data: bytes, code: str) -> None:
    with pytest.raises(ImportFileError) as error:
        check_table_upload(data)
    assert error.value.code == code


def test_the_kind_comes_from_the_bytes() -> None:
    assert sniff_table_kind(make_xlsx(ROWS)) == "xlsx"
    assert sniff_table_kind(b"a,b\n1,2") == "csv"
    assert sniff_table_kind(b"\x00\x01\x02") is None
