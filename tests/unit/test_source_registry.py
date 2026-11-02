"""Checkpoint 2.5: the source registry rules, company resolution, search intent and the resolver.

Everything here runs without a model and without a database, as the requirements demand."""

from datetime import date, timedelta
from typing import Any

import pytest

from pv_domain.company import (
    Company,
    CompanyMatch,
    normalize,
    resolve_company,
    similarity,
)
from pv_domain.resolver import Outcome, Route, decide_source, plan_search
from pv_domain.search_intent import (
    ALL_PERMITTED,
    SearchIntent,
    clean_intent,
    clean_query,
    countries_in,
    intent_to_dict,
)
from pv_domain.sources import (
    ComplianceStatus,
    SourceError,
    SourceRecord,
    SourceType,
    enable_blocker,
    parse_source,
    review_expired,
    unavailable_reason,
)
from pv_persistence.registry import seed_companies, seed_sources

TODAY = date(2026, 11, 2)
WINDOW = 180
CAPS = {
    "can_search": True,
    "can_enumerate": True,
    "supports_full_description": True,
    "supports_company_filter": True,
    "supports_location_filter": True,
    "requires_auth": False,
    "requires_attribution": False,
}


def raw_source(**over: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "key": "demo",
        "display_name": "Demo Jobs",
        "source_type": "job_api",
        "adapter": "demo_adapter",
        "endpoint_or_feed": "https://example.com/jobs",
        "capabilities": dict(CAPS),
        "compliance_status": "verified",
        "terms_checked_at": TODAY.isoformat(),
        "terms_url": "https://example.com/terms",
        "verification_owner": "Owner",
        "min_poll_interval_seconds": 3600,
        "geographic_coverage": [],
        "enabled": True,
    }
    base.update(over)
    return base


def source(**over: Any) -> SourceRecord:
    raw = raw_source(**over)
    raw["enabled"] = over.get("enabled", True)
    return parse_source(raw)


def import_only(key: str = "linkedin", name: str = "LinkedIn") -> SourceRecord:
    return parse_source(
        raw_source(
            key=key,
            display_name=name,
            source_type="user_import_only",
            adapter=None,
            capabilities={},
            compliance_status="prohibited",
            enabled=False,
        )
    )


COMPANIES = [
    Company("google", "Google", ("Google LLC", "Alphabet"), ats_platform=None),
    Company("stripe", "Stripe", ("Stripe Inc",), ats_platform="demo", ats_board_id="stripe"),
    Company("tcs", "Tata Consultancy Services", ("TCS",)),
    Company("tata-motors", "Tata Motors", ()),
    Company("tata-steel", "Tata Steel", ()),
    Company("flipkart", "Flipkart", ("Flipkart Internet",)),
]


class TestSourceRules:
    def test_a_verified_source_in_date_can_be_enabled(self) -> None:
        assert enable_blocker(source(), TODAY, WINDOW) is None

    @pytest.mark.parametrize("status", ["unverified", "restricted", "prohibited"])
    def test_only_a_verified_source_can_be_enabled(self, status: str) -> None:
        with pytest.raises(SourceError) as caught:
            source(compliance_status=status)
        assert "enabled" in caught.value.problems

    def test_the_review_expires(self) -> None:
        old = TODAY - timedelta(days=WINDOW + 1)
        record = source(terms_checked_at=old.isoformat(), enabled=False)
        assert review_expired(record.terms_checked_at, TODAY, WINDOW)
        assert "not checked in the last 180 days" in str(enable_blocker(record, TODAY, WINDOW))
        assert not review_expired(TODAY - timedelta(days=WINDOW), TODAY, WINDOW)
        assert review_expired(None, TODAY, WINDOW)

    def test_a_reviewer_and_a_terms_address_are_required_to_enable(self) -> None:
        for field in ("terms_url", "verification_owner"):
            with pytest.raises(SourceError):
                source(**{field: None})

    def test_an_import_only_platform_has_no_adapter_and_cannot_be_enabled(self) -> None:
        with pytest.raises(SourceError) as caught:
            parse_source(raw_source(source_type="user_import_only", compliance_status="prohibited"))
        assert "adapter" in caught.value.problems
        record = import_only()
        assert "import only" in str(
            enable_blocker(
                parse_source(
                    {
                        **raw_source(
                            source_type="user_import_only",
                            adapter=None,
                            capabilities={},
                            enabled=False,
                        )
                    }
                ),
                TODAY,
                WINDOW,
            )
        )
        assert record.adapter is None

    def test_a_source_that_needs_attribution_must_say_how(self) -> None:
        with pytest.raises(SourceError) as caught:
            source(capabilities={**CAPS, "requires_attribution": True})
        assert "attribution_text" in caught.value.problems
        assert source(
            capabilities={**CAPS, "requires_attribution": True}, attribution_text="Source: Demo"
        )

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("key", "bad key!"),
            ("source_type", "scraper"),
            ("compliance_status", "maybe"),
            ("terms_checked_at", "yesterday"),
            ("min_poll_interval_seconds", -1),
            ("capabilities", {"can_fly": True}),
            ("geographic_coverage", "India"),
        ],
    )
    def test_bad_values_are_refused_next_to_the_field(self, field: str, value: Any) -> None:
        with pytest.raises(SourceError) as caught:
            parse_source(raw_source(enabled=False, **{field: value}))
        assert any(k.startswith(field) for k in caught.value.problems)

    def test_the_reason_a_source_is_unavailable_is_in_words(self) -> None:
        assert unavailable_reason(source(), TODAY, WINDOW) is None
        off = source(enabled=False)
        assert unavailable_reason(off, TODAY, WINDOW) == "It is switched off."
        for status, text in (
            ("unverified", "not been verified"),
            ("restricted", "restrict"),
            ("prohibited", "do not allow"),
        ):
            assert text in str(
                unavailable_reason(source(compliance_status=status, enabled=False), TODAY, WINDOW)
            )


class TestTheSeedFiles:
    def test_every_seed_source_passes_the_same_rules_as_an_admin_edit(self) -> None:
        sources = seed_sources()
        assert {s.key for s in sources} >= {
            "greenhouse",
            "lever",
            "ashby",
            "remotive",
            "adzuna",
            "linkedin",
            "indeed",
            "wellfound",
            "naukri",
        }
        assert len({s.key for s in sources}) == len(sources)

    def test_nothing_is_switched_on_before_an_adapter_exists(self) -> None:
        for s in seed_sources():
            assert s.enabled is False, s.key
            assert (s.adapter is not None) == (s.key in ("lever", "greenhouse", "ashby")), s.key

    def test_every_platform_without_a_permitted_feed_is_import_only(self) -> None:
        by_key = {s.key: s for s in seed_sources()}
        for key in ("linkedin", "indeed", "wellfound", "naukri"):
            assert by_key[key].source_type == SourceType.USER_IMPORT_ONLY
            assert by_key[key].supports_user_import is True
            assert not any(by_key[key].capabilities.values())

    def test_a_platform_whose_terms_forbid_automation_is_marked_prohibited(self) -> None:
        by_key = {s.key: s for s in seed_sources()}
        for key in ("linkedin", "indeed", "wellfound"):
            assert by_key[key].compliance_status == ComplianceStatus.PROHIBITED
            assert by_key[key].terms_url and by_key[key].terms_checked_at

    def test_what_could_not_be_read_is_not_called_verified(self) -> None:
        by_key = {s.key: s for s in seed_sources()}
        assert by_key["naukri"].compliance_status == ComplianceStatus.UNVERIFIED
        assert by_key["naukri"].terms_checked_at is None
        assert "403" in by_key["naukri"].compliance_notes
        for key in ("greenhouse", "ashby"):
            assert by_key[key].compliance_status == ComplianceStatus.UNVERIFIED
            assert (
                "could not be located" in by_key[key].compliance_notes
                or "not read in full" in by_key[key].compliance_notes
            )

    def test_a_source_with_a_conflict_with_the_product_is_restricted_with_the_reason(self) -> None:
        by_key = {s.key: s for s in seed_sources()}
        assert by_key["remotive"].compliance_status == ComplianceStatus.RESTRICTED
        assert "sign-ups" in by_key["remotive"].compliance_notes
        assert by_key["remotive"].min_poll_interval_seconds >= 6 * 3600  # at most four a day
        assert by_key["remotive"].attribution_text
        assert by_key["adzuna"].compliance_status == ComplianceStatus.RESTRICTED
        assert "licence" in by_key["adzuna"].compliance_notes

    def test_only_verified_sources_carry_a_reviewer_and_every_record_says_what_was_read(
        self,
    ) -> None:
        for s in seed_sources():
            assert s.compliance_notes, s.key
            if s.compliance_status == ComplianceStatus.VERIFIED:
                assert s.verification_owner and s.terms_url and s.terms_checked_at

    def test_companies_are_consistent_with_the_sources(self) -> None:
        keys = {s.key for s in seed_sources()}
        companies = seed_companies()
        assert len({c["key"] for c in companies}) == len(companies) >= 20
        names: dict[str, str] = {}
        for c in companies:
            if c["ats_platform"]:
                assert c["ats_platform"] in keys and c["ats_board_id"] and c["last_verified_at"], c[
                    "key"
                ]
            for n in (c["canonical_name"], *c["aliases"]):
                assert names.setdefault(n.lower(), c["key"]) == c["key"], (
                    f"{n} belongs to two companies"
                )


class TestCompanyResolution:
    def test_an_exact_alias_resolves_whatever_the_case(self) -> None:
        r = resolve_company("alphabet", COMPANIES)
        assert (r.status, r.chosen.key if r.chosen else None, r.method) == (
            CompanyMatch.RESOLVED,
            "google",
            "alias",
        )

    def test_legal_suffixes_and_punctuation_do_not_matter(self) -> None:
        r = resolve_company("Stripe, Inc.", COMPANIES)
        assert r.status == CompanyMatch.RESOLVED and r.chosen and r.chosen.key == "stripe"
        assert normalize("Flipkart Pvt. Ltd.") == "flipkart"

    def test_a_close_misspelling_resolves_when_one_company_is_clearly_ahead(self) -> None:
        r = resolve_company("Flipkartt", COMPANIES)
        assert r.status == CompanyMatch.RESOLVED and r.method == "similar"
        assert r.chosen and r.chosen.key == "flipkart"

    def test_a_looser_misspelling_is_offered_for_confirmation_not_chosen(self) -> None:
        r = resolve_company("Flipcart", COMPANIES)
        assert r.status == CompanyMatch.AMBIGUOUS and r.chosen is None
        assert r.candidates[0].company.key == "flipkart"

    def test_two_close_companies_go_back_to_the_person(self) -> None:
        r = resolve_company("Tata", COMPANIES)
        assert r.status == CompanyMatch.AMBIGUOUS and r.chosen is None
        assert {c.company.key for c in r.candidates} >= {"tata-motors", "tata-steel"}

    def test_an_unknown_company_is_unknown_and_never_guessed(self) -> None:
        r = resolve_company("Zyzzyva Quantum Holdings", COMPANIES)
        assert r.status == CompanyMatch.UNKNOWN and r.chosen is None and r.candidates == ()
        assert resolve_company("   ", COMPANIES).status == CompanyMatch.UNKNOWN

    def test_it_is_deterministic(self) -> None:
        first = resolve_company("Tata", COMPANIES)
        assert all(resolve_company("Tata", list(reversed(COMPANIES))) == first for _ in range(3))

    def test_similarity_is_between_zero_and_one(self) -> None:
        assert similarity("abc", "abc") == 1.0
        assert 0.0 <= similarity("stripe", "strike") < 1.0
        assert similarity("", "x") == 0.0


class TestSearchIntent:
    def test_a_good_answer_is_kept(self) -> None:
        intent = clean_intent(
            {
                "roles": ["AI Engineer"],
                "skills": ["Python", "python"],
                "min_years": 0,
                "max_years": 2,
                "locations": ["India"],
                "work_mode": "remote",
                "employment_types": ["full_time"],
                "compensation": {"min": 800000, "currency": "inr", "period": "year"},
                "companies": ["Google"],
                "sources": ["greenhouse"],
                "exclusions": ["staffing agencies"],
            }
        )
        assert intent.skills == ("Python",) and intent.notes == ()
        assert intent.compensation and intent.compensation.currency == "INR"
        assert (intent.min_years, intent.max_years, intent.work_mode) == (0, 2, "remote")
        assert intent_to_dict(intent)["sources"] == ["greenhouse"]

    def test_bad_parts_are_dropped_and_noted_and_the_rest_survives(self) -> None:
        intent = clean_intent(
            {
                "roles": ["Backend Engineer"],
                "min_years": 9,
                "max_years": 3,
                "work_mode": "teleport",
                "employment_types": ["full_time", "volunteer"],
                "compensation": {"min": "lots", "currency": "rupees"},
                "sources": "everything please",
            }
        )
        assert intent.roles == ("Backend Engineer",)
        assert intent.min_years is None and intent.max_years is None
        assert intent.work_mode == "any" and intent.employment_types == ("full_time",)
        assert intent.compensation is None and intent.all_sources
        assert len(intent.notes) >= 4

    def test_garbage_gives_an_empty_search_with_a_note(self) -> None:
        for raw in (None, "text", 5, []):
            intent = clean_intent(raw)
            assert intent.roles == () and intent.notes

    def test_a_long_list_is_cut_and_says_so(self) -> None:
        intent = clean_intent({"skills": [f"skill{i}" for i in range(30)]})
        assert len(intent.skills) == 12 and any("Kept the first 12" in n for n in intent.notes)

    def test_countries_come_from_a_lookup_not_a_model(self) -> None:
        assert countries_in(("Bengaluru",)) == ("India",)
        assert countries_in(("remote, USA", "London")) == ("United States", "United Kingdom")
        assert countries_in(("Atlantis",)) == ()

    def test_the_typed_search_is_tidied_or_refused(self) -> None:
        assert clean_query("  AI   engineer\n in India ") == "AI engineer in India"
        assert clean_query("") is None and clean_query("x" * 501) is None and clean_query(5) is None


def registry() -> list[SourceRecord]:
    return [
        source(
            key="ats",
            display_name="Demo ATS",
            source_type="ats_board",
            capabilities={**CAPS, "can_search": False},
        ),
        source(key="agg", display_name="Demo Aggregator"),
        source(key="india_only", display_name="India Jobs", geographic_coverage=["India"]),
        source(key="us_only", display_name="US Jobs", geographic_coverage=["United States"]),
        source(key="unbuilt", display_name="Unbuilt API", adapter=None),
        source(key="off", display_name="Switched Off", enabled=False),
        source(
            key="restricted",
            display_name="Restricted Feed",
            compliance_status="restricted",
            enabled=False,
        ),
        import_only(),
        import_only("naukri", "Naukri"),
    ]


def outcomes(intent: SearchIntent, sources: list[SourceRecord] | None = None) -> dict[str, Outcome]:
    plan = plan_search(intent, sources or registry(), COMPANIES, TODAY, WINDOW)
    return {d.key: d.outcome for d in plan.sources}


class TestTheDecisionTable:
    def test_a_verified_enabled_source_with_an_adapter_is_searched(self) -> None:
        d = decide_source(source(), SearchIntent(), TODAY, WINDOW)
        assert (d.outcome, d.message) == (Outcome.SEARCH, "Searching Demo Jobs")

    def test_a_source_without_search_but_with_import_asks_for_an_import(self) -> None:
        d = decide_source(import_only(), SearchIntent(), TODAY, WINDOW)
        assert d.outcome == Outcome.IMPORT_REQUIRED and d.import_available
        assert d.message == (
            "Automated search for LinkedIn is not available. "
            "Import jobs by URL, paste, or CSV/XLSX and we will analyze them."
        )

    def test_a_source_that_is_not_built_yet_is_an_import_not_a_pretend_search(self) -> None:
        d = decide_source(source(adapter=None), SearchIntent(), TODAY, WINDOW)
        assert d.outcome == Outcome.IMPORT_REQUIRED and "has not been built yet" in str(d.reason)

    def test_a_disabled_or_unverified_or_expired_source_is_unavailable_with_the_reason(
        self,
    ) -> None:
        old = (TODAY - timedelta(days=WINDOW + 5)).isoformat()
        for rec, reason in (
            (source(enabled=False), "switched off"),
            (source(compliance_status="unverified", enabled=False), "not been verified"),
            (source(terms_checked_at=old, enabled=False), "expired"),
        ):
            d = decide_source(rec, SearchIntent(), TODAY, WINDOW)
            assert (
                d.outcome == Outcome.UNAVAILABLE and reason in d.message and "Reason:" in d.message
            )
            assert "You can still import jobs" in d.message

    def test_a_source_that_does_not_cover_the_place_is_unavailable_for_that_search(self) -> None:
        d = decide_source(
            source(geographic_coverage=["United States"]),
            SearchIntent(locations=("Bengaluru",)),
            TODAY,
            WINDOW,
        )
        assert d.outcome == Outcome.UNAVAILABLE and "does not cover India" in d.message

    def test_what_a_source_cannot_filter_is_said_not_hidden(self) -> None:
        rec = source(
            capabilities={
                **CAPS,
                "supports_location_filter": False,
                "supports_company_filter": False,
                "can_enumerate": False,
            }
        )
        d = decide_source(
            rec, SearchIntent(locations=("India",), companies=("Google",)), TODAY, WINDOW
        )
        assert d.outcome == Outcome.SEARCH and len(d.notes) == 2


class TestTheExamplesFromTheRequirements:
    """Section 3 of search-requirements.md. Each gives a plan with no model."""

    def test_ai_engineer_india_early_career(self) -> None:
        intent = SearchIntent(
            roles=("AI Engineer",), locations=("India",), min_years=0, max_years=2
        )
        got = outcomes(intent)
        assert got["agg"] == got["india_only"] == Outcome.SEARCH
        assert got["us_only"] == Outcome.UNAVAILABLE
        assert got["linkedin"] == Outcome.IMPORT_REQUIRED

    def test_ai_engineer_remote_any_company(self) -> None:
        plan = plan_search(
            SearchIntent(roles=("AI Engineer",), work_mode="remote"),
            registry(),
            COMPANIES,
            TODAY,
            WINDOW,
        )
        assert plan.companies == () and plan.can_search_now

    def test_backend_engineer_at_google_has_no_first_party_so_it_says_which_was_used(self) -> None:
        plan = plan_search(
            SearchIntent(roles=("Backend Engineer",), companies=("Google",), locations=("India",)),
            registry(),
            COMPANIES,
            TODAY,
            WINDOW,
        )
        (company,) = plan.companies
        assert company.status == CompanyMatch.RESOLVED and company.route == Route.AGGREGATOR
        assert "has no career system we can search" in company.message

    def test_a_company_with_its_own_career_system_uses_it(self) -> None:
        plan = plan_search(
            SearchIntent(companies=("Stripe",)),
            [source(key="demo", display_name="Demo ATS", source_type="ats_board")],
            COMPANIES,
            TODAY,
            WINDOW,
        )
        (company,) = plan.companies
        assert company.route == Route.FIRST_PARTY and company.source_key == "demo"
        assert company.message == "Using the company's own career system (Demo ATS)."

    def test_selected_companies_are_resolved_one_by_one(self) -> None:
        plan = plan_search(
            SearchIntent(companies=("Stripe", "Tata", "Nonexistent Corp")),
            registry(),
            COMPANIES,
            TODAY,
            WINDOW,
        )
        statuses = [c.status for c in plan.companies]
        assert statuses == [CompanyMatch.RESOLVED, CompanyMatch.AMBIGUOUS, CompanyMatch.UNKNOWN]
        assert plan.companies[1].route == Route.CHOOSE and plan.companies[1].candidates
        assert plan.companies[2].route == Route.IMPORT

    def test_a_company_with_no_permitted_source_falls_back_to_import(self) -> None:
        plan = plan_search(
            SearchIntent(companies=("Flipkart",)), [import_only()], COMPANIES, TODAY, WINDOW
        )
        assert (
            plan.companies[0].route == Route.IMPORT and "Import jobs" in plan.companies[0].message
        )

    def test_named_sources_are_checked_against_their_capabilities(self) -> None:
        got = outcomes(SearchIntent(sources=("agg", "restricted")))
        assert got == {"agg": Outcome.SEARCH, "restricted": Outcome.UNAVAILABLE}

    def test_a_named_platform_that_cannot_be_searched_is_never_replaced_silently(self) -> None:
        plan = plan_search(
            SearchIntent(sources=("linkedin",)), registry(), COMPANIES, TODAY, WINDOW
        )
        assert [d.key for d in plan.sources] == ["linkedin"]
        assert (
            plan.sources[0].outcome == Outcome.IMPORT_REQUIRED and plan.sources[0].named_by_person
        )
        assert (
            not plan.can_search_now and "No source can be searched automatically" in plan.headline
        )

    def test_an_unknown_source_name_is_ignored_with_a_note(self) -> None:
        plan = plan_search(SearchIntent(sources=("monster",)), registry(), COMPANIES, TODAY, WINDOW)
        assert plan.sources == () and any("monster" in n for n in plan.notes)

    def test_every_decision_is_explained_and_import_stays_available(self) -> None:
        plan = plan_search(
            SearchIntent(sources=(ALL_PERMITTED,)), registry(), COMPANIES, TODAY, WINDOW
        )
        assert len(plan.sources) == len(registry())
        assert all(d.message for d in plan.sources)
        assert all(d.import_available for d in plan.sources if d.outcome != Outcome.SEARCH)

    def test_searched_sources_come_first_and_the_plan_is_the_same_every_time(self) -> None:
        a = plan_search(SearchIntent(), registry(), COMPANIES, TODAY, WINDOW)
        b = plan_search(SearchIntent(), list(reversed(registry())), COMPANIES, TODAY, WINDOW)
        assert a == b
        order = [d.outcome for d in a.sources]
        assert order == sorted(
            order,
            key=lambda o: [Outcome.SEARCH, Outcome.IMPORT_REQUIRED, Outcome.UNAVAILABLE].index(o),
        )
