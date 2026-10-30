"""Profile entry rules, grounding and the resume state mapping (pure code)."""

import pytest

from pv_domain.profile import (
    ENTRY_SPECS,
    ENTRY_TYPES,
    entry_key,
    flagged_fields,
    is_grounded,
    resume_token_set,
    significant_tokens,
    specs_as_dicts,
    validate_entry,
)
from pv_domain.resume import (
    MAX_UPLOAD_BYTES,
    ParseErrorCode,
    detect_kind,
    resume_ui_state,
    safe_display_filename,
)
from pv_domain.states import ResumeUiState


def test_every_entry_type_in_the_database_check_has_a_spec() -> None:
    assert set(ENTRY_TYPES) == {
        "education", "work", "internship", "project",
        "skill", "certification", "achievement", "link",
    }  # fmt: skip


def test_every_spec_has_a_required_primary_field() -> None:
    for spec in ENTRY_SPECS.values():
        primary = next(f for f in spec.fields if f.name == spec.primary_field)
        assert primary.required, spec.entry_type
        assert set(spec.key_fields) <= spec.field_names


def test_specs_are_json_friendly_and_complete() -> None:
    dumped = specs_as_dicts()
    assert [s["entry_type"] for s in dumped] == list(ENTRY_TYPES)
    assert all({"name", "label", "kind", "required"} <= set(f) for s in dumped for f in s["fields"])


class TestStrictValidation:
    def test_clean_entry_is_normalised(self) -> None:
        check = validate_entry(
            "work",
            {
                "company": "  Kestrel   Analytics ",
                "title": "Data Intern",
                "start_date": "2024-06",
                "end_date": "present",
                "highlights": "Cleaned data\n\n  Built a report  ",
                "ignored": "dropped",
            },
        )
        assert check.errors == {}
        assert check.clean == {
            "company": "Kestrel Analytics",
            "title": "Data Intern",
            "start_date": "2024-06",
            "end_date": "present",
            "highlights": ["Cleaned data", "Built a report"],
        }

    def test_missing_required_fields_are_errors(self) -> None:
        check = validate_entry("work", {"company": "Kestrel"})
        assert check.errors == {"title": "This is required."}

    @pytest.mark.parametrize("bad", ["2024-13", "June 2024", "24", "2024-6"])
    def test_bad_dates_are_rejected_with_advice(self, bad: str) -> None:
        check = validate_entry("project", {"name": "Report", "start_date": bad})
        assert "YYYY" in check.errors["start_date"]

    @pytest.mark.parametrize(
        "bad",
        ["javascript:alert(1)", "ftp://example.com/x", "example.com", "https://", "http://a b.c"],
    )
    def test_only_http_and_https_links_are_accepted(self, bad: str) -> None:
        assert "url" in validate_entry("link", {"label": "Site", "url": bad}).errors

    def test_https_link_is_kept_as_written(self) -> None:
        check = validate_entry("link", {"label": "GitHub", "url": "https://github.com/asha"})
        assert check.clean["url"] == "https://github.com/asha"

    def test_too_long_value_is_an_error(self) -> None:
        check = validate_entry("skill", {"name": "x" * 81})
        assert "name" in check.errors

    def test_control_characters_are_removed(self) -> None:
        check = validate_entry("skill", {"name": "Py\x00thon\x07"})
        assert check.clean["name"] == "Python"

    def test_unknown_type_is_an_error(self) -> None:
        assert validate_entry("hobby", {"name": "x"}).errors

    def test_non_dict_data_is_treated_as_empty(self) -> None:
        assert validate_entry("skill", "Python").errors == {"name": "This is required."}


class TestLenientValidation:
    def test_invalid_optional_values_are_dropped_and_listed(self) -> None:
        check = validate_entry(
            "work",
            {"company": "Kestrel", "title": "Intern", "start_date": "last summer", "location": 5},
            lenient=True,
        )
        assert check.errors == {}
        assert set(check.dropped_fields) == {"start_date", "location"}
        assert check.clean == {"company": "Kestrel", "title": "Intern"}

    def test_invalid_required_value_still_fails(self) -> None:
        check = validate_entry("skill", {"name": 42}, lenient=True)
        assert check.errors == {"name": "This is required."}


def test_flags_list_recommended_fields_that_are_empty() -> None:
    assert flagged_fields("work", {"company": "K", "title": "Intern"}) == [
        "start_date",
        "highlights",
    ]
    assert flagged_fields("skill", {"name": "Python"}) == []
    assert flagged_fields("hobby", {}) == []


class TestGrounding:
    TEXT = "Worked at Kestrel Analytics. B.E. in Computer Science at BMS College of Engineering."

    def test_entry_found_in_the_text_is_grounded(self) -> None:
        tokens = resume_token_set(self.TEXT)
        assert is_grounded("work", {"company": "Kestrel Analytics", "title": "x"}, tokens)
        assert is_grounded("education", {"institution": "BMS College of Engineering"}, tokens)

    def test_invented_entry_is_not_grounded(self) -> None:
        tokens = resume_token_set(self.TEXT)
        assert not is_grounded("work", {"company": "Globex Corporation", "title": "x"}, tokens)

    def test_one_missing_word_is_enough_to_drop(self) -> None:
        tokens = resume_token_set(self.TEXT)
        assert not is_grounded(
            "work", {"company": "Kestrel Analytics Europe", "title": "x"}, tokens
        )

    def test_case_punctuation_and_stop_words_do_not_matter(self) -> None:
        tokens = resume_token_set(self.TEXT)
        assert is_grounded("education", {"institution": "bms COLLEGE, of engineering!"}, tokens)

    def test_an_entry_with_no_meaningful_word_is_not_grounded(self) -> None:
        assert not is_grounded("skill", {"name": "the of"}, resume_token_set(self.TEXT))

    def test_url_scheme_is_ignored(self) -> None:
        tokens = resume_token_set("My code is at github.com/asha")
        assert is_grounded("link", {"label": "GitHub", "url": "https://github.com/asha"}, tokens)

    def test_tokens_ignore_stop_words_and_url_noise(self) -> None:
        assert significant_tokens("The Bank of https://www.Example.com") == [
            "bank",
            "example",
            "com",
        ]


def test_entry_key_ignores_case_and_noise_and_uses_key_fields() -> None:
    a = entry_key("work", {"company": "Kestrel Analytics", "title": "Data Intern"})
    b = entry_key(
        "work", {"company": "kestrel  analytics!", "title": "data intern", "location": "x"}
    )
    c = entry_key("work", {"company": "Kestrel Analytics", "title": "Analyst"})
    assert a == b
    assert a != c


class TestFileRules:
    def test_kind_comes_from_the_first_bytes_only(self) -> None:
        assert detect_kind(b"%PDF-1.7 rest") == "pdf"
        assert detect_kind(b"PK\x03\x04rest") == "docx"
        assert detect_kind(b"MZ\x90\x00 program") is None
        assert detect_kind(b"  %PDF-1.7") is None
        assert detect_kind(b"") is None

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("cv.pdf", "cv.pdf"),
            ("../../etc/passwd", "passwd"),
            ("C:\\Users\\a\\resume final.docx", "resume final.docx"),
            ('a";b.pdf', "a_b.pdf"),
            ("..", "resume"),
            ("", "resume"),
            ("x\x00\x1f.pdf", "x.pdf"),
        ],
    )
    def test_display_filename_is_safe(self, raw: str, expected: str) -> None:
        assert safe_display_filename(raw) == expected

    def test_display_filename_is_bounded(self) -> None:
        assert len(safe_display_filename("a" * 500 + ".pdf")) == 120

    def test_upload_limit_is_five_megabytes(self) -> None:
        assert MAX_UPLOAD_BYTES == 5 * 1024 * 1024

    def test_every_error_code_has_a_message_without_em_dashes(self) -> None:
        from pv_domain.resume import ERROR_MESSAGES

        assert set(ERROR_MESSAGES) == {code.value for code in ParseErrorCode}
        assert all("\u2014" not in message for message in ERROR_MESSAGES.values())


@pytest.mark.parametrize(
    ("parse", "review", "flagged", "expected"),
    [
        ("uploaded", "pending", 0, ResumeUiState.UPLOADED),
        ("parsing", "pending", 0, ResumeUiState.PARSING),
        ("parsed", "pending", 0, ResumeUiState.PARSED),
        ("parsed", "pending", 3, ResumeUiState.NEEDS_CORRECTION),
        ("parsed", "confirmed", 3, ResumeUiState.CONFIRMED),
        ("parse_failed", "pending", 0, ResumeUiState.FAILED),
        ("parse_failed", "confirmed", 2, ResumeUiState.FAILED),
    ],
)
def test_ui_state_mapping(parse: str, review: str, flagged: int, expected: ResumeUiState) -> None:
    assert resume_ui_state(parse, review, flagged) is expected
