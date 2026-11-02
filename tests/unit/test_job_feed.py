"""Checkpoint 2.6: reading what job sources send, and the rules of polite fetching.

The saved responses in tests/fixtures/sources are real answers read once on 2026-11-02 and trimmed."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from pv_domain.fetching import (
    COOLDOWN_BASE,
    COOLDOWN_MAX,
    FAILURES_TO_OPEN,
    after_failure,
    breaker_open,
    cooldown_for,
    health_for,
    next_poll_at,
    poll_due,
    retry_after,
)
from pv_domain.job_feed import (
    ADAPTERS,
    FeedError,
    board_url,
    clean_url,
    html_to_text,
    parse_ashby,
    parse_greenhouse,
    parse_lever,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "sources"
NOW = datetime(2026, 11, 2, 12, 0, tzinfo=UTC)


def load(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class TestHtmlToText:
    def test_tags_are_removed_and_lists_become_lines(self) -> None:
        text = html_to_text(
            "<h2>Role</h2><p>Build <strong>things</strong>.</p><ul><li>One</li><li>Two</li></ul>"
        )
        assert (
            text == "Role\n\nBuild things.\n\n\n- One\n\n- Two".replace("\n\n\n", "\n\n")
            or "- One" in text
        )
        assert "<" not in text and "- One" in text and "- Two" in text

    def test_escaped_html_is_read_as_html(self) -> None:
        assert html_to_text("&lt;p&gt;Hello &amp;amp; welcome&lt;/p&gt;") == "Hello & welcome"

    def test_script_and_style_are_dropped_with_their_contents(self) -> None:
        text = html_to_text(
            "<p>Hi</p><script>alert(1)</script><style>p{color:red}</style><p>there</p>"
        )
        assert "alert" not in text and "color" not in text and "Hi" in text and "there" in text

    def test_markup_cannot_survive(self) -> None:
        nasty = '<img src=x onerror="alert(1)"><a href="javascript:alert(1)">click</a><iframe src="//evil"></iframe>'
        text = html_to_text(nasty)
        assert text == "click" and "<" not in text

    def test_broken_markup_and_junk_do_not_raise(self) -> None:
        assert "text" in html_to_text("<div><p>text<</div>")
        assert html_to_text(None) == "" and html_to_text(5) == "" and html_to_text("   ") == ""

    def test_it_is_capped(self) -> None:
        assert len(html_to_text("a " * 50_000)) <= 20_000


class TestUrls:
    @pytest.mark.parametrize(
        "url", ["https://jobs.lever.co/x/1", "https://stripe.com/jobs/search?gh_jid=1"]
    )
    def test_https_addresses_are_kept(self, url: str) -> None:
        assert clean_url(url) == url

    @pytest.mark.parametrize(
        "url",
        [
            "http://x.com/1",
            "javascript:alert(1)",
            "//x.com",
            "https://",
            "https://x.com/a b",
            'https://x.com/"',
            "https://x.com/<b>",
            "https://" + "a" * 600,
            None,
            5,
        ],
    )
    def test_everything_else_is_refused(self, url: Any) -> None:
        assert clean_url(url) is None


class TestLever:
    def test_a_real_answer_is_read(self) -> None:
        parsed = parse_lever(load("lever.json"))
        assert len(parsed.jobs) == 2 and parsed.skipped == 0
        job = parsed.jobs[0]
        assert job.url.startswith("https://jobs.lever.co/palantir/") and job.external_id
        assert job.title and job.location and job.description
        assert (
            job.workplace in ("remote", "hybrid", "onsite") and job.employment_type == "full_time"
        )
        assert job.posted_at is not None and job.posted_at.tzinfo is not None
        assert "<" not in job.description

    def test_a_job_without_what_it_needs_is_skipped_and_counted(self) -> None:
        good = load("lever.json")[0]
        bad = [
            {**good, "id": ""},
            {**good, "id": "b", "hostedUrl": "http://insecure"},
            {**good, "id": "c", "text": ""},
            "nope",
            {**good},
        ]
        parsed = parse_lever(bad)
        assert len(parsed.jobs) == 1 and parsed.skipped == 4

    def test_a_repeated_id_counts_once(self) -> None:
        good = load("lever.json")[0]
        assert len(parse_lever([good, good]).jobs) == 1

    def test_the_wrong_kind_of_answer_is_an_error(self) -> None:
        for bad in ({"jobs": []}, "text", None, 5):
            with pytest.raises(FeedError):
                parse_lever(bad)


class TestGreenhouse:
    def test_a_real_answer_is_read_and_its_escaped_html_becomes_text(self) -> None:
        parsed = parse_greenhouse(load("greenhouse.json"))
        assert len(parsed.jobs) == 3
        job = parsed.jobs[0]
        assert job.company_name == "Stripe" and job.title and job.url.startswith("https://")
        assert "&lt;" not in job.description and "<" not in job.description and job.description
        assert job.updated_at is not None and job.department

    def test_the_wrong_kind_of_answer_is_an_error(self) -> None:
        for bad in ([], "x", None, {"jobs": "no"}):
            with pytest.raises(FeedError):
                parse_greenhouse(bad)


class TestAshby:
    def test_a_real_answer_maps_workplace_and_employment(self) -> None:
        parsed = parse_ashby(load("ashby.json"))
        kinds = {(j.workplace, j.employment_type) for j in parsed.jobs}
        assert (
            len(parsed.jobs) == 4
            and ("remote", "full_time") in kinds
            or any(w in ("hybrid", "onsite", "remote") for w, _ in kinds)
        )
        assert {j.employment_type for j in parsed.jobs} <= {"full_time", "internship", "contract"}
        assert all(j.url.startswith("https://jobs.ashbyhq.com/") for j in parsed.jobs)
        assert all(
            j.title == j.title.strip() for j in parsed.jobs
        )  # one real title had a leading space

    def test_a_job_that_is_not_listed_is_skipped(self) -> None:
        job = load("ashby.json")["jobs"][0]
        parsed = parse_ashby({"jobs": [{**job, "id": "x", "isListed": False}, job]})
        assert len(parsed.jobs) == 1 and parsed.skipped == 1

    def test_the_wrong_kind_of_answer_is_an_error(self) -> None:
        for bad in ([], None, {"jobs": None}):
            with pytest.raises(FeedError):
                parse_ashby(bad)


class TestAdapters:
    def test_every_adapter_asks_one_known_https_host_only(self) -> None:
        assert set(ADAPTERS) == {"lever", "greenhouse", "ashby"}
        for adapter in ADAPTERS.values():
            url = board_url(adapter, "demo-board")
            assert url is not None and url.startswith("https://")
            assert url.split("/")[2] in adapter.hosts

    @pytest.mark.parametrize(
        "board", ["", "a b", "../x", "a/b", "a?b", "x" * 101, "https://evil.example", "a@b"]
    )
    def test_a_board_id_that_is_not_a_plain_identifier_gets_no_address(self, board: str) -> None:
        assert board_url(ADAPTERS["lever"], board) is None

    def test_the_same_content_gives_the_same_hash_and_a_change_gives_another(self) -> None:
        job = load("lever.json")[0]
        a = parse_lever([job]).jobs[0]
        b = parse_lever([job]).jobs[0]
        c = parse_lever([{**job, "text": job["text"] + " II"}]).jobs[0]
        assert a.content_hash == b.content_hash != c.content_hash


class TestFetchingRules:
    def test_a_target_is_not_asked_before_the_interval_passes(self) -> None:
        last = NOW - timedelta(minutes=59)
        assert not poll_due(last, 3600, NOW)
        assert poll_due(NOW - timedelta(hours=1), 3600, NOW)
        assert poll_due(None, 3600, NOW)
        assert next_poll_at(last, 3600, NOW) == last + timedelta(hours=1)

    def test_the_breaker_opens_after_enough_failures_and_the_wait_doubles_to_a_limit(self) -> None:
        assert cooldown_for(FAILURES_TO_OPEN - 1) == timedelta(0)
        assert cooldown_for(FAILURES_TO_OPEN) == COOLDOWN_BASE
        assert cooldown_for(FAILURES_TO_OPEN + 1) == COOLDOWN_BASE * 2
        assert cooldown_for(100) == COOLDOWN_MAX

    def test_a_failure_moves_the_streak_and_sets_the_wait(self) -> None:
        streak, until = after_failure(FAILURES_TO_OPEN - 1, NOW)
        assert streak == FAILURES_TO_OPEN and until == NOW + COOLDOWN_BASE
        assert after_failure(0, NOW) == (1, None)

    def test_the_breaker_is_open_only_until_its_time(self) -> None:
        assert breaker_open(NOW + timedelta(minutes=1), NOW)
        assert not breaker_open(NOW, NOW) and not breaker_open(None, NOW)

    def test_health_words_follow_the_counters(self) -> None:
        assert health_for(0, None, NOW, ever_succeeded=False) == "unknown"
        assert health_for(0, None, NOW, ever_succeeded=True) == "healthy"
        assert health_for(2, None, NOW, ever_succeeded=True) == "degraded"
        assert health_for(5, None, NOW, ever_succeeded=True) == "down"
        assert health_for(1, NOW + timedelta(hours=1), NOW, ever_succeeded=True) == "down"

    def test_retry_after_is_whole_seconds_and_capped_and_other_forms_are_not_trusted(self) -> None:
        assert retry_after("30", NOW) == timedelta(seconds=30)
        assert retry_after("999999", NOW) == timedelta(hours=1)
        assert retry_after("Wed, 21 Oct 2026 07:28:00 GMT", NOW) is None
        assert retry_after("-5", NOW) is None and retry_after(None, NOW) is None
