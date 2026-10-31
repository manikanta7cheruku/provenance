"""Job posting rules: cleaning, fingerprints, finding quotes, states, and experience years."""

from datetime import date

import pytest

from pv_domain.experience import years_of_experience
from pv_domain.job import (
    JOB_ERROR_MESSAGES,
    MAX_QUOTE_CHARS,
    JobErrorCode,
    clean_posting_text,
    find_quote,
    job_ui_state,
    posting_content_hash,
)
from pv_domain.states import JobUiState

POSTING = """Data Analyst, Early Careers
Fernlight Systems  |  Bengaluru, India (Hybrid)

You will write SQL to answer questions from product teams.
We'd like you to have 1-2 years of experience -- freshers are welcome.
Must be authorized to work in India.
"""


class TestCleaning:
    def test_newlines_control_characters_and_blank_runs_are_normalised(self) -> None:
        raw = "a\r\nb\rc\x00\x07\n\n\n\n\nd  "
        assert clean_posting_text(raw) == "a\nb\nc\n\nd"

    def test_equal_postings_with_different_spacing_and_case_share_a_hash(self) -> None:
        a = posting_content_hash(clean_posting_text("Data  Analyst\nSQL required"))
        b = posting_content_hash(clean_posting_text("data analyst sql   REQUIRED"))
        assert a == b and len(a) == 64
        assert a != posting_content_hash(clean_posting_text("Data Analyst\nPython required"))


class TestFindQuote:
    def test_a_quote_is_found_and_the_span_is_real_text(self) -> None:
        span = find_quote(POSTING, "write SQL to answer questions")
        assert span is not None
        assert POSTING[span[0] : span[1]] == "write SQL to answer questions"

    def test_whitespace_and_case_may_differ_but_the_words_may_not(self) -> None:
        assert find_quote(POSTING, "WRITE   sql to\nanswer questions") is not None
        assert find_quote(POSTING, "write Python to answer questions") is None
        assert find_quote(POSTING, "questions answer to SQL write") is None

    def test_quote_marks_and_dashes_are_forgiving(self) -> None:
        assert (
            find_quote(
                POSTING,
                "We" + chr(0x2019) + "d like you to have 1" + chr(0x2013) + "2 years of experience",
            )
            is not None
        )
        assert (
            find_quote(POSTING, "experience " + chr(0x2014) + " freshers are welcome") is not None
        )

    def test_regex_characters_in_a_quote_are_just_text(self) -> None:
        assert find_quote("Needs C++ (or C#) skills.", "C++ (or C#)") is not None
        assert find_quote("Needs C skills.", "C++ (or C#)") is None
        assert find_quote(POSTING, ".*") is None

    @pytest.mark.parametrize("quote", ["", "   ", "x" * (MAX_QUOTE_CHARS + 1)])
    def test_empty_or_oversized_quotes_are_refused(self, quote: str) -> None:
        assert find_quote(POSTING, quote) is None

    def test_a_quote_cannot_be_invented_across_far_apart_places(self) -> None:
        assert find_quote(POSTING, "Data Analyst written in India") is None


class TestStates:
    @pytest.mark.parametrize(
        ("status", "expected"),
        [
            ("queued", JobUiState.READING),
            ("extracting", JobUiState.READING),
            ("extracted", JobUiState.READY),
            ("failed", JobUiState.FAILED),
        ],
    )
    def test_mapping(self, status: str, expected: JobUiState) -> None:
        assert job_ui_state(status) is expected

    def test_every_error_code_has_a_plain_message(self) -> None:
        assert set(JOB_ERROR_MESSAGES) == {code.value for code in JobErrorCode}
        assert all(chr(0x2014) not in m for m in JOB_ERROR_MESSAGES.values())


class TestExperience:
    TODAY = date(2026, 10, 30)

    def years(self, *entries: tuple[str, dict[str, str]]) -> float | None:
        return years_of_experience(list(entries), self.TODAY)

    def test_an_internship_in_months(self) -> None:
        assert self.years(("internship", {"start_date": "2024-06", "end_date": "2024-08"})) == 0.2

    def test_a_bare_year_runs_from_january_to_december(self) -> None:
        assert self.years(("work", {"start_date": "2022", "end_date": "2023"})) == 2.0

    def test_present_counts_up_to_today(self) -> None:
        assert self.years(("work", {"start_date": "2025-11", "end_date": "present"})) == 1.0

    def test_overlapping_jobs_count_once(self) -> None:
        both = self.years(
            ("work", {"start_date": "2023-01", "end_date": "2023-12"}),
            ("internship", {"start_date": "2023-06", "end_date": "2024-05"}),
        )
        assert both == 1.4  # 17 months, not 24

    def test_other_entry_types_and_unusable_dates_are_ignored(self) -> None:
        assert self.years(("education", {"start_date": "2021", "end_date": "2025"})) is None
        assert self.years(("work", {"company": "K", "title": "T"})) is None
        assert self.years(("work", {"start_date": "last year"})) is None

    def test_unknown_is_not_zero(self) -> None:
        assert years_of_experience([], self.TODAY) is None

    def test_an_end_before_the_start_is_ignored(self) -> None:
        assert self.years(("work", {"start_date": "2024-06", "end_date": "2023-01"})) is None

    def test_a_start_with_no_end_counts_one_month_only(self) -> None:
        assert self.years(("work", {"start_date": "2020"})) == 0.1
