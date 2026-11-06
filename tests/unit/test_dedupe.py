"""Checkpoint 2.7: deciding that two postings are the same job, in layers, with no model."""

import pytest

from pv_domain.dedupe import (
    JobFacts,
    Level,
    compare,
    components,
    normalize_title,
    normalize_url,
    ordered_pair,
    place_agreement,
    shingles,
    text_agreement,
)

TEXT = (
    "You will build data pipelines for our analytics team. You work with SQL and Python every day, "
    "partner with product managers, and ship dashboards that leaders use to decide. We offer remote "
    "friendly work, learning budget and a supportive team of engineers who care about quality."
)


def job(**over: str) -> JobFacts:
    base = {
        "url": "https://jobs.lever.co/acme/1",
        "company": "Acme",
        "title": "Data Engineer",
        "location": "London, United Kingdom",
        "description": TEXT,
        "source_key": "lever",
        "board_id": "acme",
        "external_id": "1",
        "content_hash": "h1",
    }
    base.update(over)
    return JobFacts(**base)  # type: ignore[arg-type]


class TestNormalising:
    def test_tracking_noise_is_removed_and_job_identity_kept(self) -> None:
        a = normalize_url("https://www.Example.com/jobs/12/?utm_source=x&gh_src=y&fbclid=z")
        assert a == "example.com/jobs/12"
        assert (
            normalize_url("https://boards.x.com/acme?gh_jid=77&utm_medium=m")
            == "boards.x.com/acme?gh_jid=77"
        )
        assert normalize_url("https://jobs.lever.co/acme/1/apply") == normalize_url(
            "https://jobs.lever.co/acme/1"
        )
        assert (
            normalize_url("not a url") is None
            and normalize_url(None) is None
            and normalize_url("") is None
        )

    def test_a_title_loses_brackets_noise_and_short_forms(self) -> None:
        assert normalize_title("Sr. Data Engineer (m/f/d) - Remote") == "senior data engineer"
        assert (
            normalize_title("Software Engineer & Architect [Hybrid]")
            == "software engineer and architect"
        )
        assert normalize_title("Data Engineer") != normalize_title("Senior Data Engineer")

    @pytest.mark.parametrize(
        ("a", "b", "expected"),
        [
            ("London, United Kingdom", "London, UK", "same"),
            ("New York, NY", "New York City", "same"),
            ("London, UK", "Berlin, Germany", "different"),
            ("Remote", "London, UK", "different"),
            ("Remote", "Remote", "same"),
            ("Remote, United States", "Remote, Canada", "different"),
            ("Remote", "Remote, United States", "unknown"),
            ("", "London", "unknown"),
            ("Bengaluru, India", "Bangalore", "same"),
            ("Bombay, India", "Mumbai", "same"),
            ("New Delhi", "Delhi, India", "same"),
            ("Bangalore", "Chennai", "different"),
        ],
    )
    def test_places_agree_differ_or_are_unknown(self, a: str, b: str, expected: str) -> None:
        assert place_agreement(a, b) == expected

    def test_wording_is_compared_by_shared_five_word_runs(self) -> None:
        assert text_agreement(TEXT, TEXT) == 1.0
        assert (
            text_agreement(
                TEXT,
                "A completely different description about warehouse safety and forklift driving in Leeds today",
            )
            < 0.1
        )
        assert text_agreement("", TEXT) is None and text_agreement(TEXT, "  ") is None
        assert len(shingles("a b c")) == 1


class TestLayers:
    def test_the_same_address_is_the_same_job_whatever_else_differs(self) -> None:
        a = job(url="https://jobs.lever.co/acme/1?utm_source=a")
        b = job(
            url="https://jobs.lever.co/acme/1/apply",
            title="Totally Different",
            company="Other",
            location="Mars",
        )
        match = compare(a, b)
        assert (
            match
            and match.method == "same_address"
            and match.level == Level.AUTO
            and match.score == 1.0
        )

    def test_the_same_content_under_a_new_id_on_one_board_is_a_repost(self) -> None:
        a = job()
        b = job(
            url="https://jobs.lever.co/acme/2",
            external_id="2",
            title="Data Engineer II",
            location="Anywhere else",
        )
        match = compare(a, b)
        assert match and match.method == "same_content" and match.level == Level.AUTO

    def test_the_same_company_title_and_place_with_agreeing_text_is_linked(self) -> None:
        a = job()
        b = job(
            url="https://boards.greenhouse.io/acme/9",
            source_key="greenhouse",
            external_id="9",
            content_hash="h2",
            location="London, UK",
            title="Data Engineer (m/f/d)",
        )
        match = compare(a, b)
        assert match and match.method == "same_company_title_place" and match.level == Level.AUTO
        assert "same company, title and place" in match.reason.lower() and "%" in match.reason

    def test_the_same_title_and_place_with_different_text_is_only_suggested(self) -> None:
        other = "Drive a delivery van across the north of the city, load and unload parcels, keep the log, and report faults to the depot manager each evening without fail."
        match = compare(
            job(),
            job(
                url="https://x.com/2",
                source_key="greenhouse",
                external_id="2",
                content_hash="h2",
                description=other,
            ),
        )
        assert match and match.level == Level.SUGGESTED

    def test_no_text_is_never_taken_as_agreement(self) -> None:
        match = compare(
            job(),
            job(
                url="https://x.com/2",
                source_key="greenhouse",
                external_id="2",
                content_hash="h2",
                description="",
            ),
        )
        assert match and match.level == Level.SUGGESTED and "no text to compare" in match.reason

    def test_a_missing_place_needs_the_text_to_settle_it(self) -> None:
        same_text = compare(
            job(),
            job(
                url="https://x.com/2",
                source_key="greenhouse",
                external_id="2",
                content_hash="h2",
                location="",
            ),
        )
        assert (
            same_text
            and same_text.level == Level.AUTO
            and same_text.method == "same_company_title_text"
        )
        unclear = compare(
            job(description=""),
            job(
                url="https://x.com/2",
                source_key="greenhouse",
                external_id="2",
                content_hash="h2",
                location="",
                description="",
            ),
        )
        assert unclear and unclear.level == Level.SUGGESTED

    def test_a_very_close_title_with_nearly_the_same_text_is_linked_and_a_looser_one_suggested(
        self,
    ) -> None:
        near = compare(
            job(title="Senior Data Engineer"),
            job(
                url="https://x.com/2",
                source_key="greenhouse",
                external_id="2",
                content_hash="h2",
                title="Senior Data Engineers",
            ),
        )
        assert near and near.level == Level.AUTO and near.method == "near_identical"
        looser_text = TEXT.replace("data pipelines", "reports").replace(
            "SQL and Python", "Excel and Word"
        )
        loose = compare(
            job(title="Senior Data Engineer"),
            job(
                url="https://x.com/2",
                source_key="greenhouse",
                external_id="2",
                content_hash="h2",
                title="Senior Data Engineers",
                description=looser_text,
            ),
        )
        assert loose is None or loose.level == Level.SUGGESTED

    def test_different_places_are_different_jobs(self) -> None:
        assert (
            compare(
                job(),
                job(
                    url="https://x.com/2",
                    source_key="greenhouse",
                    external_id="2",
                    content_hash="h2",
                    location="Berlin, Germany",
                ),
            )
            is None
        )
        assert (
            compare(
                job(location="Remote"),
                job(
                    url="https://x.com/2",
                    source_key="greenhouse",
                    external_id="2",
                    content_hash="h2",
                    location="London",
                ),
            )
            is None
        )

    def test_different_companies_are_never_linked_even_with_the_same_text_and_title(self) -> None:
        assert (
            compare(
                job(),
                job(
                    url="https://x.com/2",
                    company="Globex",
                    source_key="greenhouse",
                    external_id="2",
                    content_hash="h2",
                ),
            )
            is None
        )

    def test_different_titles_are_not_linked(self) -> None:
        assert (
            compare(
                job(),
                job(
                    url="https://x.com/2",
                    title="Warehouse Operative",
                    source_key="greenhouse",
                    external_id="2",
                    content_hash="h2",
                ),
            )
            is None
        )
        assert (
            compare(
                job(title="Data Engineer"),
                job(
                    url="https://x.com/2",
                    title="Senior Data Engineer",
                    source_key="greenhouse",
                    external_id="2",
                    content_hash="h2",
                ),
            )
            is None
        )

    def test_a_missing_company_is_never_a_match(self) -> None:
        assert (
            compare(
                job(company=None),
                job(
                    url="https://x.com/2",
                    company=None,
                    source_key="greenhouse",
                    external_id="2",
                    content_hash="h2",
                ),
            )
            is None
        )

    def test_company_suffixes_do_not_matter(self) -> None:
        match = compare(
            job(company="Acme Inc."),
            job(
                url="https://x.com/2",
                company="ACME",
                source_key="greenhouse",
                external_id="2",
                content_hash="h2",
            ),
        )
        assert match and match.level == Level.AUTO

    def test_the_answer_is_the_same_both_ways_and_every_time(self) -> None:
        a = job()
        b = job(url="https://x.com/2", source_key="greenhouse", external_id="2", content_hash="h2")
        assert compare(a, b) == compare(b, a) == compare(a, b)


class TestGroups:
    def test_linked_postings_share_a_group_named_by_the_smallest_id(self) -> None:
        groups = components(["c", "a", "b", "d"], [("a", "b"), ("b", "c")])
        assert groups == {"a": "a", "b": "a", "c": "a", "d": "d"}

    def test_removing_the_only_link_between_two_halves_splits_the_group(self) -> None:
        nodes = ["a", "b", "c", "d"]
        both = [("a", "b"), ("b", "c"), ("c", "d")]
        assert len(set(components(nodes, both).values())) == 1
        split = components(nodes, [("a", "b"), ("c", "d")])
        assert split == {"a": "a", "b": "a", "c": "c", "d": "c"}

    def test_a_cycle_survives_losing_one_link(self) -> None:
        assert (
            len(set(components(["a", "b", "c"], [("a", "b"), ("b", "c"), ("a", "c")]).values()))
            == 1
        )
        assert len(set(components(["a", "b", "c"], [("a", "b"), ("a", "c")]).values())) == 1

    def test_unknown_nodes_in_an_edge_are_ignored(self) -> None:
        assert components(["a"], [("a", "zzz")]) == {"a": "a"}

    def test_a_pair_is_stored_once_smaller_first(self) -> None:
        assert ordered_pair("b", "a") == ordered_pair("a", "b") == ("a", "b")
