"""The eligibility gates, one rule at a time, and how they combine."""

from typing import Any

import pytest

from pv_domain.eligibility import (
    RULES_VERSION,
    EligibilityState,
    Fact,
    PostingFacts,
    SeekerPreferences,
    evaluate_eligibility,
)

E = EligibilityState
TEXT = "Fernlight Systems is hiring in Bengaluru. We build analytics for retailers."


def facts(**kw: Any) -> PostingFacts:
    return PostingFacts(raw_text=kw.pop("raw_text", TEXT), **kw)


def f(value: Any, quote: str = "quote") -> Fact:
    return Fact(value, quote)


def gate(result: Any, name: str) -> Any:
    return next(g for g in result.gates if g.gate == name)


def run(
    posting: PostingFacts, prefs: SeekerPreferences | None = None, years: float | None = 1.0
) -> Any:
    return evaluate_eligibility(posting, prefs or SeekerPreferences(), years)


class TestAuthorization:
    def test_no_requirement_and_no_need_is_fine(self) -> None:
        assert gate(run(facts()), "authorization").state is E.ELIGIBLE

    def test_no_sponsorship_blocks_someone_who_needs_it(self) -> None:
        result = run(
            facts(sponsorship=f("not_offered", "We do not sponsor visas")),
            SeekerPreferences(needs_sponsorship=True),
        )
        g = gate(result, "authorization")
        assert g.state is E.NOT_ELIGIBLE and g.posting_quote == "We do not sponsor visas"
        assert result.state is E.NOT_ELIGIBLE

    def test_no_sponsorship_with_an_unanswered_question_asks(self) -> None:
        result = run(facts(sponsorship=f("not_offered")), SeekerPreferences(needs_sponsorship=None))
        assert gate(result, "authorization").state is E.REQUIRES_USER_INPUT

    def test_required_country_with_no_answer_asks(self) -> None:
        result = run(facts(authorization_countries=f(("India",))))
        assert gate(result, "authorization").state is E.REQUIRES_USER_INPUT

    @pytest.mark.parametrize(
        ("required", "mine"),
        [("India", "india"), ("IN", "India"), ("USA", "United States"), ("UK", "united kingdom")],
    )
    def test_country_names_and_short_forms_match(self, required: str, mine: str) -> None:
        result = run(
            facts(authorization_countries=f((required,))),
            SeekerPreferences(authorized_countries=(mine,)),
        )
        assert gate(result, "authorization").state is E.ELIGIBLE

    def test_not_authorized_and_no_sponsorship_blocks(self) -> None:
        prefs = SeekerPreferences(authorized_countries=("India",), needs_sponsorship=True)
        result = run(
            facts(authorization_countries=f(("Canada",)), sponsorship=f("not_offered")), prefs
        )
        assert gate(result, "authorization").state is E.NOT_ELIGIBLE

    def test_not_authorized_with_sponsorship_offered_is_worth_a_look(self) -> None:
        prefs = SeekerPreferences(authorized_countries=("India",), needs_sponsorship=True)
        result = run(facts(authorization_countries=f(("Canada",)), sponsorship=f("offered")), prefs)
        assert gate(result, "authorization").state is E.UNCERTAIN

    def test_not_authorized_and_silent_about_sponsorship_is_uncertain_not_blocked(self) -> None:
        result = run(
            facts(authorization_countries=f(("Canada",))),
            SeekerPreferences(authorized_countries=("India",)),
        )
        assert gate(result, "authorization").state is E.UNCERTAIN

    def test_needing_sponsorship_when_the_posting_is_silent_is_uncertain(self) -> None:
        result = run(facts(), SeekerPreferences(needs_sponsorship=True))
        assert gate(result, "authorization").state is E.UNCERTAIN

    def test_needing_sponsorship_when_offered_is_fine(self) -> None:
        result = run(facts(sponsorship=f("offered")), SeekerPreferences(needs_sponsorship=True))
        assert gate(result, "authorization").state is E.ELIGIBLE


class TestLocation:
    def test_remote_is_fine(self) -> None:
        assert gate(run(facts(work_mode=f("remote"))), "location").state is E.ELIGIBLE

    def test_nothing_stated_is_uncertain(self) -> None:
        assert gate(run(facts()), "location").state is E.UNCERTAIN

    @pytest.mark.parametrize(
        ("posting", "wanted"),
        [
            ("Bengaluru, India", "Bengaluru"),
            ("Bengaluru", "Bengaluru, India"),
            ("Pune, India", "India"),
            ("Bengaluru, Karnataka", "Bengaluru"),
        ],
    )
    def test_a_listed_place_matches_in_either_direction(self, posting: str, wanted: str) -> None:
        result = run(
            facts(work_mode=f("onsite"), location=f(posting)),
            SeekerPreferences(locations=(wanted,)),
        )
        assert gate(result, "location").state is E.ELIGIBLE

    def test_a_different_city_in_the_same_country_is_not_a_match(self) -> None:
        result = run(
            facts(work_mode=f("onsite"), location=f("Pune, India")),
            SeekerPreferences(locations=("Hyderabad, India",), open_to_relocate=False),
        )
        assert gate(result, "location").state is E.NOT_ELIGIBLE

    def test_openness_to_relocating_makes_it_fine(self) -> None:
        result = run(
            facts(work_mode=f("hybrid"), location=f("Toronto, Canada")),
            SeekerPreferences(open_to_relocate=True),
        )
        assert gate(result, "location").state is E.ELIGIBLE

    def test_no_places_and_no_answer_asks(self) -> None:
        result = run(facts(work_mode=f("onsite"), location=f("Toronto, Canada")))
        assert gate(result, "location").state is E.REQUIRES_USER_INPUT

    def test_a_remote_preference_makes_an_in_person_role_a_review_not_a_block(self) -> None:
        result = run(
            facts(work_mode=f("hybrid"), location=f("Bengaluru")),
            SeekerPreferences(locations=("Bengaluru",), remote_preference="remote"),
        )
        assert gate(result, "location").state is E.UNCERTAIN

    def test_in_person_without_a_place_is_uncertain(self) -> None:
        assert gate(run(facts(work_mode=f("onsite"))), "location").state is E.UNCERTAIN


class TestExclusions:
    def test_none_listed_is_fine(self) -> None:
        assert gate(run(facts()), "exclusions").state is E.ELIGIBLE

    def test_a_match_blocks_and_shows_where_it_was_found(self) -> None:
        text = "We build tools for the online gambling industry and need a data analyst."
        result = run(facts(raw_text=text), SeekerPreferences(exclusions=("Gambling",)))
        g = gate(result, "exclusions")
        assert g.state is E.NOT_ELIGIBLE and "gambling" in (g.posting_quote or "").lower()
        assert "online gambling industry" in (g.posting_quote or "")

    def test_only_whole_words_match(self) -> None:
        result = run(
            facts(raw_text="We love bingeing on data."), SeekerPreferences(exclusions=("binge",))
        )
        assert gate(result, "exclusions").state is E.ELIGIBLE

    def test_company_and_title_are_checked(self) -> None:
        by_company = run(
            facts(company="Acme Tobacco Ltd"), SeekerPreferences(exclusions=("Tobacco",))
        )
        assert "company name" in gate(by_company, "exclusions").reason
        by_title = run(facts(title="Crypto Analyst"), SeekerPreferences(exclusions=("crypto",)))
        assert "job title" in gate(by_title, "exclusions").reason

    def test_regex_characters_in_an_exclusion_are_just_text(self) -> None:
        result = run(
            facts(raw_text="Knowledge of C++ needed"),
            SeekerPreferences(exclusions=("C++", ".*", "(")),
        )
        assert gate(result, "exclusions").state is E.NOT_ELIGIBLE


class TestEmploymentType:
    def test_no_preference_means_anything_goes(self) -> None:
        assert gate(run(facts(employment_type=f("contract"))), "employment").state is E.ELIGIBLE

    def test_a_kind_you_accept(self) -> None:
        result = run(
            facts(employment_type=f("internship")),
            SeekerPreferences(employment_types=("internship", "full_time")),
        )
        assert gate(result, "employment").state is E.ELIGIBLE

    def test_a_kind_you_did_not_list_blocks(self) -> None:
        result = run(
            facts(employment_type=f("contract")),
            SeekerPreferences(employment_types=("internship", "full_time")),
        )
        g = gate(result, "employment")
        assert g.state is E.NOT_ELIGIBLE and "an internship and full time" in g.reason

    def test_an_unstated_kind_is_uncertain_when_you_have_a_preference(self) -> None:
        result = run(facts(), SeekerPreferences(employment_types=("full_time",)))
        assert gate(result, "employment").state is E.UNCERTAIN


class TestExperienceAsked:
    @pytest.mark.parametrize(
        ("asked", "have", "expected"),
        [
            (1, 0.0, E.ELIGIBLE),
            (2, 0.5, E.ELIGIBLE),
            (3, 0.5, E.UNCERTAIN),
            (4, 1.0, E.UNCERTAIN),
            (5, 0.0, E.NOT_ELIGIBLE),
            (8, 2.0, E.NOT_ELIGIBLE),
            (8, 3.5, E.UNCERTAIN),
            (3, 5.0, E.ELIGIBLE),
        ],
    )
    def test_the_gap_decides(self, asked: int, have: float, expected: EligibilityState) -> None:
        assert (
            gate(run(facts(min_years=f(asked, f"{asked}+ years")), years=have), "seniority").state
            is expected
        )

    def test_unknown_experience_asks_only_when_it_matters(self) -> None:
        assert (
            gate(run(facts(min_years=f(5)), years=None), "seniority").state is E.REQUIRES_USER_INPUT
        )
        assert gate(run(facts(min_years=f(1)), years=None), "seniority").state is E.ELIGIBLE

    def test_a_senior_title_with_little_experience_is_a_review(self) -> None:
        assert gate(run(facts(seniority=f("senior")), years=1.0), "seniority").state is E.UNCERTAIN
        assert gate(run(facts(seniority=f("senior")), years=6.0), "seniority").state is E.ELIGIBLE

    def test_nothing_stated_is_fine(self) -> None:
        assert gate(run(facts()), "seniority").state is E.ELIGIBLE


class TestCombining:
    def test_the_most_serious_gate_decides_the_overall_state(self) -> None:
        posting = facts(
            work_mode=f("onsite"),
            location=f("Toronto, Canada"),
            min_years=f(3),
            employment_type=f("contract"),
        )
        prefs = SeekerPreferences(employment_types=("full_time",))
        result = run(posting, prefs, years=0.5)
        states = {g.gate: g.state for g in result.gates}
        assert (
            states["employment"] is E.NOT_ELIGIBLE and states["location"] is E.REQUIRES_USER_INPUT
        )
        assert result.state is E.NOT_ELIGIBLE

    def test_questions_outrank_review_items(self) -> None:
        posting = facts(work_mode=f("onsite"), location=f("Toronto, Canada"), min_years=f(4))
        result = run(posting, years=1.0)
        assert result.state is E.REQUIRES_USER_INPUT

    def test_gates_are_listed_worst_first_and_every_reason_is_a_plain_sentence(self) -> None:
        posting = facts(work_mode=f("onsite"), location=f("Toronto"), employment_type=f("contract"))
        result = run(
            posting,
            SeekerPreferences(employment_types=("full_time",), open_to_relocate=False),
            years=0.0,
        )
        severities = [g.state for g in result.gates]
        assert severities[0] is E.NOT_ELIGIBLE
        assert all(
            g.reason.endswith((".", "...")) and chr(0x2014) not in g.reason for g in result.gates
        )
        assert result.rules_version == RULES_VERSION

    def test_five_gates_and_no_surprises_on_an_empty_posting(self) -> None:
        result = run(facts())
        assert [g.gate for g in result.gates].count("authorization") == 1
        assert len(result.gates) == 5

    def test_a_blocker_is_never_averaged_away(self) -> None:
        # Four passing gates do not rescue one blocker.
        posting = facts(raw_text="Join our casino analytics team.", work_mode=f("remote"))
        result = run(posting, SeekerPreferences(exclusions=("casino",)))
        assert sum(g.state is E.ELIGIBLE for g in result.gates) == 4
        assert result.state is E.NOT_ELIGIBLE
