"""Private storage and untrusted-document extraction."""

import io
import zipfile
from pathlib import Path

import pytest
from documents import RESUME_TEXT, make_docx, make_pdf, resume_docx, resume_pdf

from pv_domain.resume import MAX_PAGES, MAX_TEXT_CHARS, ParseErrorCode
from pv_files import (
    ExtractionError,
    LocalDiskStorage,
    StorageError,
    check_upload,
    extract_text,
    new_resume_key,
)


class TestStorage:
    def test_round_trip_and_delete(self, tmp_path: Path) -> None:
        storage = LocalDiskStorage(tmp_path)
        key = new_resume_key()
        storage.put(key, b"hello")
        assert storage.exists(key)
        assert storage.get(key) == b"hello"
        storage.delete(key)
        assert not storage.exists(key)
        storage.delete(key)  # deleting twice is fine

    def test_missing_file_is_a_storage_error(self, tmp_path: Path) -> None:
        with pytest.raises(StorageError):
            LocalDiskStorage(tmp_path).get(new_resume_key())

    @pytest.mark.parametrize(
        "key",
        [
            "../escape",
            "resumes/../../escape",
            "/etc/passwd",
            "resumes/ABC",
            "resumes/",
            "x",
            "a/b/c",
        ],
    )
    def test_keys_that_could_leave_the_folder_are_refused(self, tmp_path: Path, key: str) -> None:
        storage = LocalDiskStorage(tmp_path)
        for action in (
            lambda: storage.put(key, b"x"),
            lambda: storage.get(key),
            lambda: storage.delete(key),
        ):
            with pytest.raises(StorageError):
                action()

    def test_generated_keys_are_unpredictable_and_well_formed(self) -> None:
        keys = {new_resume_key() for _ in range(50)}
        assert len(keys) == 50
        assert all(k.startswith("resumes/") and len(k) == len("resumes/") + 32 for k in keys)

    def test_no_partial_file_is_left_behind(self, tmp_path: Path) -> None:
        storage = LocalDiskStorage(tmp_path)
        storage.put(new_resume_key(), b"x" * 1000)
        assert list(tmp_path.rglob("*.part")) == []


class TestPdf:
    def test_text_and_page_count_are_extracted(self) -> None:
        extracted = extract_text("pdf", resume_pdf())
        assert extracted.pages == 1
        assert "BMS College of Engineering" in extracted.text
        assert "Delivery delay report" in extracted.text

    def test_too_many_pages(self) -> None:
        pages = [[f"Page {n} " + "text " * 60] for n in range(MAX_PAGES + 1)]
        with pytest.raises(ExtractionError) as caught:
            extract_text("pdf", make_pdf(pages))
        assert caught.value.code is ParseErrorCode.TOO_MANY_PAGES

    def test_a_page_with_no_text_is_reported_as_no_text(self) -> None:
        with pytest.raises(ExtractionError) as caught:
            extract_text("pdf", make_pdf([["x"]]))
        assert caught.value.code is ParseErrorCode.NO_TEXT

    def test_garbage_after_the_header_is_unreadable(self) -> None:
        with pytest.raises(ExtractionError) as caught:
            extract_text("pdf", b"%PDF-1.4\nthis is not a pdf at all")
        assert caught.value.code is ParseErrorCode.FILE_UNREADABLE

    def test_too_much_text(self) -> None:
        line = "word " * 90
        pages = [[line] * 40 for _ in range(10)]
        with pytest.raises(ExtractionError) as caught:
            extract_text("pdf", make_pdf(pages))
        assert caught.value.code in (ParseErrorCode.TOO_LONG, ParseErrorCode.NO_TEXT)
        assert MAX_TEXT_CHARS > 0


class TestDocx:
    def test_text_is_extracted_in_order(self) -> None:
        extracted = extract_text("docx", resume_docx())
        assert extracted.pages is None
        assert extracted.text.startswith("Asha Verma")
        assert extracted.text.index("EDUCATION") < extracted.text.index("SKILLS")

    def test_check_upload_accepts_a_real_docx_and_pdf(self) -> None:
        assert check_upload(resume_docx()) == "docx"
        assert check_upload(resume_pdf()) == "pdf"

    def test_a_zip_that_is_not_a_docx_is_refused(self) -> None:
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w") as archive:
            archive.writestr("notes.txt", "hello")
        assert check_upload(out.getvalue()) is None

    def test_not_a_zip_at_all(self) -> None:
        assert check_upload(b"PK\x03\x04 this is not a zip") is None
        assert check_upload(b"just text") is None

    def test_a_decompression_bomb_is_refused_before_parsing(self) -> None:
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("[Content_Types].xml", "<Types/>")
            archive.writestr("word/document.xml", "<w:document/>")
            archive.writestr("word/bomb.bin", b"\x00" * (60 * 1024 * 1024))
        assert len(out.getvalue()) < 200_000  # tiny on disk, huge when opened
        assert check_upload(out.getvalue()) is None
        with pytest.raises(ExtractionError) as caught:
            extract_text("docx", out.getvalue())
        assert caught.value.code is ParseErrorCode.UNSAFE_ARCHIVE

    def test_too_many_entries_is_refused(self) -> None:
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w") as archive:
            archive.writestr("[Content_Types].xml", "<Types/>")
            archive.writestr("word/document.xml", "<d/>")
            for n in range(600):
                archive.writestr(f"word/part{n}.xml", "x")
        assert check_upload(out.getvalue()) is None

    def test_path_traversal_member_names_are_refused(self) -> None:
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w") as archive:
            archive.writestr("[Content_Types].xml", "<Types/>")
            archive.writestr("word/document.xml", "<d/>")
            archive.writestr("../evil.txt", "x")
        assert check_upload(out.getvalue()) is None

    def test_external_entities_are_not_expanded(self) -> None:
        secret = "TOP-SECRET-FILE-CONTENT"
        xml = (
            '<?xml version="1.0"?><!DOCTYPE d [<!ENTITY x SYSTEM "file:///etc/hostname">]>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            "<w:body><w:p><w:r><w:t>&x;</w:t></w:r></w:p></w:body></w:document>"
        )
        with pytest.raises(ExtractionError) as caught:
            extract_text("docx", make_docx([], document_xml=xml))
        assert caught.value.code is ParseErrorCode.FILE_UNREADABLE
        assert secret not in str(caught.value)

    def test_billion_laughs_is_refused(self) -> None:
        xml = (
            '<?xml version="1.0"?><!DOCTYPE d [<!ENTITY a "aaaaaaaaaa">'
            '<!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;">]>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            "<w:body><w:p><w:r><w:t>&b;</w:t></w:r></w:p></w:body></w:document>"
        )
        with pytest.raises(ExtractionError):
            extract_text("docx", make_docx([], document_xml=xml))


def test_unknown_kind_is_unreadable() -> None:
    with pytest.raises(ExtractionError):
        extract_text("txt", RESUME_TEXT.encode())
