"""Row rules for imports: which column is which, what a row needs, and the sentence when it fails."""

import pytest
from table_helpers import LONG

from pv_domain.job_import import (
    FILE_MESSAGES,
    MAX_IMPORT_ROWS,
    ROW_MESSAGES,
    ImportFileError,
    build_draft,
    clean_link,
    compose_posting_text,
    map_columns,
    plan_rows,
    source_label,
)

HEADER = ["Job title", "Company", "Location", "Link", "Description"]


def row(title: str = "Backend engineer", description: str = LONG, **kw: str) -> list[str]:
    return [
        title,
        kw.get("company", "Acme"),
        kw.get("location", "Pune, India"),
        kw.get("link", "https://acme.example/jobs/1"),
        description,
    ]


def test_headers_are_matched_by_meaning_not_by_exact_spelling() -> None:
    mapping = map_columns(
        ["  JOB_TITLE ", "Employer", "City", "Job URL", "Job Description", "Notes"]
    )
    assert mapping.columns == {"title": 0, "company": 1, "location": 2, "link": 3, "description": 4}
    assert mapping.ignored == ("Notes",)


def test_the_first_column_for_a_field_wins() -> None:
    mapping = map_columns(["Description", "Details", "Title"])
    assert mapping.columns["description"] == 0
    assert mapping.ignored == ("Details",)


def test_a_good_file_becomes_drafts() -> None:
    plan = plan_rows(
        [HEADER, row(), row("Data engineer", LONG + " Spark.")], default_source="Other"
    )
    assert [r.row_number for r in plan.rows] == [2, 3]
    assert all(r.problem is None and r.draft is not None for r in plan.rows)
    draft = plan.rows[0].draft
    assert draft is not None
    assert draft.title == "Backend engineer" and draft.company == "Acme"
    assert draft.link == "https://acme.example/jobs/1"
    assert draft.text.startswith(
        "Title: Backend engineer\nCompany: Acme\nLocation: Pune, India\n\n"
    )
    assert LONG in draft.text
    assert len(draft.content_hash) == 64


def test_the_description_is_the_only_required_column() -> None:
    plan = plan_rows([["Description"], [LONG]], default_source="Other")
    draft = plan.rows[0].draft
    assert draft is not None and draft.title is None and draft.text == LONG


def test_no_description_column_is_a_file_problem() -> None:
    with pytest.raises(ImportFileError) as error:
        plan_rows([["Title", "Company"], ["a", "b"]], default_source="Other")
    assert error.value.code == "no_description_column"
    assert error.value.message == FILE_MESSAGES["no_description_column"]


@pytest.mark.parametrize(
    ("table", "code"),
    [
        ([], "empty"),
        ([[], ["", " "]], "empty"),
        ([["", ""], [LONG]], "no_header"),
        ([["Description"]], "no_rows"),
        ([["Description"], ["", ""], [""]], "no_rows"),
    ],
)
def test_files_that_cannot_be_used(table: list[list[str]], code: str) -> None:
    with pytest.raises(ImportFileError) as error:
        plan_rows(table, default_source="Other")
    assert error.value.code == code


def test_too_many_rows_is_a_file_problem() -> None:
    table = [["Description"]] + [[f"{LONG} {i}"] for i in range(MAX_IMPORT_ROWS + 1)]
    with pytest.raises(ImportFileError) as error:
        plan_rows(table, default_source="Other")
    assert error.value.code == "too_many_rows"


def test_exactly_the_limit_is_accepted() -> None:
    table = [["Description"]] + [[f"{LONG} {i}"] for i in range(MAX_IMPORT_ROWS)]
    assert len(plan_rows(table, default_source="Other").rows) == MAX_IMPORT_ROWS


@pytest.mark.parametrize(
    ("changes", "code"),
    [
        ({"description": "Too short."}, "too_short"),
        ({"description": ""}, "no_description"),
        ({"description": "x" * 25_000}, "too_long"),
        ({"link": "javascript:alert(1)"}, "bad_link"),
        ({"link": "ftp://acme.example/x"}, "bad_link"),
        ({"link": "https://exa mple.com"}, "bad_link"),
        ({"link": "not a link"}, "bad_link"),
        ({"link": "https://acme.example/" + "a" * 600}, "bad_link"),
        ({"title": "T" * 201}, "title_too_long"),
        ({"company": "C" * 201}, "company_too_long"),
        ({"location": "L" * 201}, "location_too_long"),
    ],
    ids=[
        "short",
        "empty",
        "long",
        "javascript-link",
        "ftp-link",
        "link-with-space",
        "not-a-link",
        "long-link",
        "long-title",
        "long-company",
        "long-location",
    ],
)
def test_a_bad_row_is_rejected_with_its_reason_and_the_others_still_load(
    changes: dict[str, str], code: str
) -> None:
    bad = row(**{k: v for k, v in changes.items() if k != "description" and k != "title"})
    if "description" in changes:
        bad[4] = changes["description"]
    if "title" in changes:
        bad[0] = changes["title"]
    plan = plan_rows([HEADER, bad, row("Good one", LONG + " Good.")], default_source="Other")
    rejected, accepted = plan.rows
    assert rejected.draft is None and rejected.problem is not None
    assert rejected.problem.code == code
    assert rejected.problem.message == ROW_MESSAGES[code]
    assert accepted.draft is not None and accepted.problem is None


def test_a_row_repeated_in_the_file_is_kept_once() -> None:
    plan = plan_rows([HEADER, row(), row("backend ENGINEER ")], default_source="Other")
    first, second = plan.rows
    assert first.draft is not None
    assert second.draft is None and second.problem is not None
    assert second.problem.code == "duplicate_in_file"


def test_blank_rows_are_skipped_and_counted_and_numbers_stay_true_to_the_file() -> None:
    plan = plan_rows(
        [HEADER, [], row(), ["", "", "", "", ""], row("Other job", LONG + " b")],
        default_source="Other",
    )
    assert [r.row_number for r in plan.rows] == [3, 5]
    assert plan.blank_rows == 2


def test_short_rows_are_padded_not_crashed_on() -> None:
    plan = plan_rows([["Title", "Description"], ["Engineer"]], default_source="Other")
    assert plan.rows[0].problem is not None and plan.rows[0].problem.code == "no_description"


def test_a_spreadsheet_formula_is_stored_as_the_text_it_is() -> None:
    plan = plan_rows(
        [HEADER, row('=HYPERLINK("http://evil","x")', LONG, company="+cmd|' /C calc'!A0")],
        default_source="Other",
    )
    draft = plan.rows[0].draft
    assert draft is not None
    assert draft.title == '=HYPERLINK("http://evil","x")'
    assert draft.company == "+cmd|' /C calc'!A0"


def test_control_characters_in_cells_are_removed() -> None:
    plan = plan_rows([HEADER, row("Back\x00end\x07 engineer")], default_source="Other")
    draft = plan.rows[0].draft
    assert draft is not None and draft.title == "Backend engineer"


def test_the_source_cell_is_used_only_when_it_is_a_known_label() -> None:
    table = [[*HEADER, "Source"], [*row(), "naukri"], [*row("B", LONG + " b"), "Some Random Site"]]
    plan = plan_rows(table, default_source="Message or referral")
    assert [r.draft.source_name for r in plan.rows if r.draft] == ["Naukri", "Message or referral"]


def test_title_is_kept_in_the_report_even_when_the_row_is_rejected() -> None:
    plan = plan_rows([HEADER, row("Shown anyway", "short")], default_source="Other")
    assert plan.rows[0].title == "Shown anyway"


@pytest.mark.parametrize(
    "link", ["https://a.example/x", "http://a.example/x", "  https://a.example/ "]
)
def test_good_links(link: str) -> None:
    assert clean_link(link) == link.strip()


def test_no_link_is_fine() -> None:
    assert clean_link("") is None and clean_link(None) is None and clean_link("   ") is None


def test_compose_leaves_out_empty_fields() -> None:
    assert (
        compose_posting_text(title="T", company=None, location=None, description="D")
        == "Title: T\n\nD"
    )
    assert compose_posting_text(title=None, company=None, location=None, description="D") == "D"


def test_the_same_job_gives_the_same_hash_whatever_the_spacing_or_case() -> None:
    a = build_draft(
        title="Engineer",
        company="Acme",
        location="",
        link="",
        source=None,
        description=LONG,
        default_source="Other",
    )
    b = build_draft(
        title="engineer ",
        company="ACME",
        location="",
        link="",
        source=None,
        description=LONG.upper(),
        default_source="Other",
    )
    assert a.content_hash == b.content_hash


def test_source_label_falls_back_to_the_default() -> None:
    assert source_label("indeed", "Other") == "Indeed"
    assert source_label("", "Other") == "Other"
    assert source_label("zzz", "Company career page") == "Company career page"
