"""The workbench rules: the decision state machine, and how the list is filtered, sorted and counted."""

from datetime import UTC, datetime, timedelta

import pytest

from pv_domain.pipeline import (
    ACTION_LABELS,
    REVERSE,
    STATE_LABELS,
    VIEWS,
    Action,
    DecisionState,
    TransitionError,
    WorkQuery,
    WorkRow,
    available_actions,
    clean_query,
    facets,
    matches,
    query_to_dict,
    select,
    sort_rows,
    transition,
)

S = DecisionState
A = Action
T0 = datetime(2026, 11, 1, 9, 0, tzinfo=UTC)


def row(id_: str, **kw: object) -> WorkRow:
    base: dict[str, object] = {
        "id": id_,
        "title": "Backend engineer",
        "company": "Acme",
        "source_name": "Wellfound",
        "acquisition_method": "user_paste",
        "work_mode": "remote",
        "location": "Pune, India",
        "employment_type": "full_time",
        "seniority": "mid",
        "eligibility": "eligible",
        "band": "good",
        "reading": "ready",
        "state": "new",
        "created_at": T0,
        "applied_at": None,
        "note": "",
    }
    base.update(kw)
    return WorkRow(**base)  # type: ignore[arg-type]


# --------------------------------------------------------------------- the state machine

ALLOWED = [
    (S.NEW, A.SAVE, S.SAVED),
    (S.SAVED, A.UNSAVE, S.NEW),
    (S.NEW, A.DISMISS, S.DISMISSED),
    (S.SAVED, A.DISMISS, S.DISMISSED),
    (S.APPROVED_FOR_PREP, A.DISMISS, S.DISMISSED),
    (S.DISMISSED, A.UNDO_DISMISS, S.NEW),
    (S.NEW, A.APPROVE, S.APPROVED_FOR_PREP),
    (S.SAVED, A.APPROVE, S.APPROVED_FOR_PREP),
    (S.NEW, A.MARK_APPLIED, S.APPLIED),
    (S.SAVED, A.MARK_APPLIED, S.APPLIED),
    (S.APPROVED_FOR_PREP, A.MARK_APPLIED, S.APPLIED),
    (S.APPLIED, A.UNDO_APPLIED, S.NEW),
    (S.APPLIED, A.ARCHIVE, S.ARCHIVED),
    (S.DISMISSED, A.ARCHIVE, S.ARCHIVED),
]


@pytest.mark.parametrize(("state", "action", "after"), ALLOWED)
def test_every_allowed_move(state: S, action: A, after: S) -> None:
    assert transition(state, action) is after


def test_every_other_move_is_refused_with_a_sentence() -> None:
    allowed = {(s, a) for s, a, _ in ALLOWED}
    refused = 0
    for state in S:
        for action in A:
            if (state, action) in allowed:
                continue
            with pytest.raises(TransitionError) as error:
                transition(state, action)
            assert error.value.code == "not_allowed"
            assert ACTION_LABELS[action] in error.value.message
            assert STATE_LABELS[state].lower() in error.value.message
            refused += 1
    assert refused == len(S) * len(A) - len(ALLOWED)


def test_there_is_no_submitted_state_anywhere() -> None:
    assert not any("submit" in s.value for s in S)
    assert not any("submit" in a.value for a in A)


def test_undo_applied_returns_the_job_to_where_it_was() -> None:
    for before in (S.NEW, S.SAVED, S.APPROVED_FOR_PREP):
        assert transition(S.APPLIED, A.UNDO_APPLIED, previous=before) is before


@pytest.mark.parametrize("previous", [None, S.DISMISSED, S.ARCHIVED, S.APPLIED])
def test_undo_applied_without_a_usable_past_falls_back_to_new(previous: S | None) -> None:
    assert transition(S.APPLIED, A.UNDO_APPLIED, previous=previous) is S.NEW


def test_a_job_a_hard_rule_rules_out_cannot_be_approved_but_can_be_saved_dismissed_or_marked() -> (
    None
):
    with pytest.raises(TransitionError) as error:
        transition(S.NEW, A.APPROVE, eligibility="not_eligible")
    assert error.value.code == "not_eligible"
    assert "hard requirement" in error.value.message
    assert transition(S.NEW, A.SAVE, eligibility="not_eligible") is S.SAVED
    assert transition(S.NEW, A.DISMISS, eligibility="not_eligible") is S.DISMISSED
    assert transition(S.NEW, A.MARK_APPLIED, eligibility="not_eligible") is S.APPLIED


@pytest.mark.parametrize("eligibility", [None, "eligible", "uncertain", "requires_user_input"])
def test_other_eligibility_states_do_not_block_approval(eligibility: str | None) -> None:
    assert transition(S.NEW, A.APPROVE, eligibility=eligibility) is S.APPROVED_FOR_PREP


def test_each_reversible_action_has_a_reverse_that_undoes_it() -> None:
    assert set(REVERSE) == {A.SAVE, A.DISMISS, A.MARK_APPLIED}
    for action, reverse in REVERSE.items():
        after = transition(S.NEW, action)
        back = transition(after, reverse, previous=S.NEW)
        assert back is S.NEW


def test_approve_and_archive_are_not_reversible() -> None:
    assert A.APPROVE not in REVERSE and A.ARCHIVE not in REVERSE


def test_the_actions_offered_are_exactly_the_allowed_ones_in_a_fixed_order() -> None:
    assert available_actions(S.NEW) == [A.SAVE, A.APPROVE, A.MARK_APPLIED, A.DISMISS]
    assert available_actions(S.SAVED) == [A.UNSAVE, A.APPROVE, A.MARK_APPLIED, A.DISMISS]
    assert available_actions(S.APPROVED_FOR_PREP) == [A.MARK_APPLIED, A.DISMISS]
    assert available_actions(S.DISMISSED) == [A.UNDO_DISMISS, A.ARCHIVE]
    assert available_actions(S.APPLIED) == [A.UNDO_APPLIED, A.ARCHIVE]
    assert available_actions(S.ARCHIVED) == []
    assert A.APPROVE not in available_actions(S.NEW, "not_eligible")
    for state in S:
        for action in available_actions(state):
            transition(state, action)  # never offers something that would be refused


def test_every_state_and_action_has_a_label() -> None:
    assert set(STATE_LABELS) == set(S) and set(ACTION_LABELS) == set(A)
    assert all(label for label in [*STATE_LABELS.values(), *ACTION_LABELS.values()])


# --------------------------------------------------------------------- the list


def sample() -> list[WorkRow]:
    return [
        row(
            "a",
            title="Backend engineer",
            company="Acme",
            created_at=T0,
            band="strong",
            eligibility="eligible",
        ),
        row(
            "b",
            title="Data analyst",
            company="Beta Labs",
            created_at=T0 + timedelta(days=1),
            band="review",
            work_mode="hybrid",
            location="Bengaluru, India",
            seniority="entry",
            employment_type="internship",
            source_name="Naukri",
            eligibility="uncertain",
        ),
        row(
            "c",
            title="Frontend developer",
            company="",
            created_at=T0 + timedelta(days=2),
            band=None,
            work_mode=None,
            eligibility=None,
            reading="reading",
            state="saved",
        ),
        row(
            "d",
            title="Platform engineer",
            company="Acme",
            created_at=T0 + timedelta(days=3),
            band="not_eligible",
            eligibility="not_eligible",
            state="dismissed",
        ),
        row(
            "e",
            title="SRE",
            company="Gamma",
            created_at=T0 + timedelta(days=4),
            state="applied",
            applied_at=T0 + timedelta(days=5),
        ),
        row(
            "f",
            title="Old role",
            company="Gamma",
            created_at=T0 - timedelta(days=9),
            state="archived",
        ),
        row(
            "g",
            title="Staff engineer",
            company="Acme",
            created_at=T0 + timedelta(days=6),
            state="approved_for_prep",
            note="Referred by Priya",
        ),
    ]


def ids(rows: list[WorkRow]) -> list[str]:
    return [r.id for r in rows]


def test_each_view_shows_the_right_states() -> None:
    rows = sample()
    assert set(ids(select(rows, WorkQuery(view="active")))) == {"a", "b", "c", "g"}
    assert set(ids(select(rows, WorkQuery(view="saved")))) == {"c", "g"}
    assert ids(select(rows, WorkQuery(view="applications"))) == ["e"]
    assert ids(select(rows, WorkQuery(view="dismissed"))) == ["d"]
    assert ids(select(rows, WorkQuery(view="archived"))) == ["f"]
    assert len(select(rows, WorkQuery(view="all"))) == len(rows)
    assert set(VIEWS) == {"active", "saved", "applications", "dismissed", "archived", "all"}


def test_explicit_states_replace_the_view() -> None:
    assert set(
        ids(select(sample(), WorkQuery(view="active", states=frozenset({"dismissed", "applied"}))))
    ) == {"d", "e"}


def test_text_search_needs_every_word_in_title_company_place_source_or_note() -> None:
    rows = sample()
    assert ids(select(rows, WorkQuery(view="all", text="acme backend"))) == ["a"]
    assert ids(select(rows, WorkQuery(view="all", text="BENGALURU"))) == ["b"]
    assert ids(select(rows, WorkQuery(view="all", text="naukri analyst"))) == ["b"]
    assert ids(select(rows, WorkQuery(view="all", text="priya"))) == ["g"]
    assert select(rows, WorkQuery(view="all", text="acme nonsense")) == []


def test_within_a_filter_any_value_matches_and_across_filters_all_must() -> None:
    rows = sample()
    q = WorkQuery(view="all", work_modes=frozenset({"remote", "hybrid"}))
    assert set(ids(select(rows, q))) == {"a", "b", "d", "e", "f", "g"}
    q = WorkQuery(
        view="all", work_modes=frozenset({"remote", "hybrid"}), eligibility=frozenset({"eligible"})
    )
    assert set(ids(select(rows, q))) == {"a", "e", "f", "g"}


def test_a_job_with_no_value_for_a_filtered_field_does_not_match_it() -> None:
    rows = sample()
    assert "c" not in ids(
        select(rows, WorkQuery(view="all", work_modes=frozenset({"remote", "hybrid", "onsite"})))
    )
    assert "c" not in ids(
        select(rows, WorkQuery(view="all", bands=frozenset({"strong", "good", "review"})))
    )
    assert "c" not in ids(
        select(rows, WorkQuery(view="all", eligibility=frozenset({"eligible", "uncertain"})))
    )


def test_company_and_place_filters_match_part_of_the_name_without_case() -> None:
    rows = sample()
    assert set(ids(select(rows, WorkQuery(view="all", company="acm")))) == {"a", "d", "g"}
    assert ids(select(rows, WorkQuery(view="all", location="bengal"))) == ["b"]


def test_filters_for_level_kind_of_work_and_source() -> None:
    rows = sample()
    assert ids(select(rows, WorkQuery(view="all", seniorities=frozenset({"entry"})))) == ["b"]
    assert ids(select(rows, WorkQuery(view="all", employment_types=frozenset({"internship"})))) == [
        "b"
    ]
    assert ids(select(rows, WorkQuery(view="all", sources=frozenset({"Naukri"})))) == ["b"]
    assert matches(rows[0], WorkQuery(view="all", bands=frozenset({"strong"})))


def test_sorting_in_each_direction_keeps_missing_values_last() -> None:
    rows = [r for r in sample() if r.state in ("new", "saved", "approved_for_prep")]
    assert ids(sort_rows(rows, WorkQuery(sort="added"))) == ["g", "c", "b", "a"]  # newest first
    assert ids(sort_rows(rows, WorkQuery(sort="added", descending=False))) == ["a", "b", "c", "g"]
    assert [r.title for r in sort_rows(rows, WorkQuery(sort="title"))] == [
        "Backend engineer", "Data analyst", "Frontend developer", "Staff engineer",
    ]  # fmt: skip
    assert [r.title for r in sort_rows(rows, WorkQuery(sort="title", descending=True))][
        0
    ] == "Staff engineer"
    fit = sort_rows(rows, WorkQuery(sort="fit"))
    assert ids(fit) == ["a", "g", "b", "c"]  # strong, good, review, then no band yet
    fit_reverse = sort_rows(rows, WorkQuery(sort="fit", descending=True))
    assert ids(fit_reverse)[-1] == "c"  # still last when reversed


def test_sorting_by_company_leaves_rows_with_no_company_last() -> None:
    rows = sample()
    assert sort_rows(rows, WorkQuery(sort="company"))[-1].company == ""


def test_sorting_by_applied_date_uses_the_applied_rows_first() -> None:
    rows = [
        row("x", state="applied", applied_at=T0),
        row("y", state="applied", applied_at=T0 + timedelta(days=3)),
        row("z"),
    ]
    assert ids(sort_rows(rows, WorkQuery(sort="applied"))) == ["y", "x", "z"]


def test_the_order_is_stable_when_values_tie() -> None:
    rows = [row("b"), row("a"), row("c")]
    once = ids(sort_rows(rows, WorkQuery(sort="title")))
    assert once == ids(sort_rows(list(reversed(rows)), WorkQuery(sort="title")))


def test_counts_for_the_views_and_filters() -> None:
    rows = sample()
    f = facets(rows, WorkQuery(view="active"))
    assert f.views == {
        "active": 4,
        "saved": 2,
        "applications": 1,
        "dismissed": 1,
        "archived": 1,
        "all": 7,
    }
    assert f.work_modes == {"remote": 2, "hybrid": 1}  # only the active rows are counted
    assert f.bands["strong"] == 1 and "not_eligible" not in f.bands
    assert f.sources == {"Wellfound": 3, "Naukri": 1}
    assert f.eligibility == {"eligible": 2, "uncertain": 1}


def test_counts_do_not_change_when_other_filters_are_set() -> None:
    rows = sample()
    assert facets(rows, WorkQuery(view="active")) == facets(
        rows, WorkQuery(view="active", work_modes=frozenset({"hybrid"}), text="data")
    )


# --------------------------------------------------------------------- untrusted queries


def test_a_clean_query_drops_what_it_does_not_know_and_never_raises() -> None:
    q = clean_query(
        {
            "view": "everything",
            "text": "  spaced   out  " + "x" * 500,
            "states": ["saved", "bogus", 3],
            "eligibility": ["eligible", "<script>"],
            "bands": "strong",
            "work_modes": ["remote", "moon"],
            "employment_types": ["full_time", "", "  "],
            "sort": "random",
            "descending": "yes",
            "company": ["not", "a", "string"],
        }
    )
    assert q.view == "active" and q.sort == "best" and q.descending is None
    assert q.states == frozenset({"saved"}) and q.eligibility == frozenset({"eligible"})
    assert q.bands == frozenset() and q.work_modes == frozenset({"remote"})
    assert q.employment_types == frozenset({"full_time"})
    assert q.text.startswith("spaced out ") and len(q.text) == 200 and q.company == ""


def test_a_clean_query_caps_how_many_values_each_filter_keeps() -> None:
    q = clean_query({"sources": [f"s{i:02d}" for i in range(60)]})
    assert len(q.sources) == 20


def test_an_empty_query_is_the_default_view() -> None:
    assert clean_query({}) == WorkQuery()


def test_a_query_survives_being_stored_and_read_back() -> None:
    q = WorkQuery(
        view="saved", text="data", states=frozenset({"saved"}), eligibility=frozenset({"eligible"}),
        bands=frozenset({"strong", "good"}), work_modes=frozenset({"remote"}), employment_types=frozenset({"full_time"}),
        seniorities=frozenset({"mid"}), sources=frozenset({"Naukri"}), company="acme", location="pune",
        sort="fit", descending=True,
    )  # fmt: skip
    stored = query_to_dict(q)
    assert clean_query(stored) == q
    assert clean_query(query_to_dict(WorkQuery())) == WorkQuery()
