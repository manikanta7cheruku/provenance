"""Matching a job title to the roles a person wants, and the Best match order."""

from datetime import UTC, datetime, timedelta

import pytest
from test_pipeline import row

from pv_domain.pipeline import WorkQuery, sort_rows
from pv_domain.roles import role_matches


@pytest.mark.parametrize(
    ("title", "roles", "expected"),
    [
        ("Backend Developer", ["Backend developer"], True),
        ("Senior Back-end Engineer", ["Backend developer"], True),
        ("SDE 2", ["Software engineer"], True),
        ("Data Analyst Intern", ["Data analyst"], True),
        ("Machine Learning Engineer", ["ML engineer"], True),
        ("UX Designer", ["UI/UX designer"], True),
        ("Sales Manager", ["Data analyst", "Backend developer"], False),
        ("Frontend Developer", ["Backend developer"], False),
        ("Anything", [], None),
        ("Anything", ["  "], None),
    ],
)
def test_a_title_fits_a_wanted_role(title: str, roles: list[str], expected: bool | None) -> None:
    assert role_matches(title, roles) is expected


def test_best_match_puts_takeable_matching_strong_jobs_first_and_blockers_last() -> None:
    t0 = datetime(2026, 11, 1, tzinfo=UTC)
    rows = [
        row("blocked", eligibility="not_eligible", role_match=True, band="not_eligible"),
        row("other-role", role_match=False, band="strong"),
        row("match-review", role_match=True, band="review"),
        row("match-strong-old", role_match=True, band="strong", created_at=t0),
        row("match-strong-new", role_match=True, band="strong", created_at=t0 + timedelta(days=2)),
        row("no-roles", role_match=None, band="good"),
    ]
    order = [r.id for r in sort_rows(rows, WorkQuery(sort="best"))]
    assert order == [
        "match-strong-new",
        "match-strong-old",
        "match-review",
        "no-roles",
        "other-role",
        "blocked",
    ]
