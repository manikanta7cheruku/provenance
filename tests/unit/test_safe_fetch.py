"""The fetch for an address a person typed: private networks, DNS rebinding, redirects, size, cookies.

No real network is used. The name server is a fake that returns what each test says, and the web
server is a fake transport that records exactly which address and which names the request carried.
"""

import gzip
from collections.abc import Callable

import httpx
import pytest

from pv_worker.safe_fetch import MAX_REDIRECTS, PageFetchError, SafePageFetcher

PUBLIC = "93.184.216.34"
OTHER_PUBLIC = "1.1.1.1"
PAGE = "<html><body><p>" + "Backend engineer wanted. " * 20 + "</p></body></html>"


class Names:
    """A fake name server that records every question."""

    def __init__(self, answers: dict[str, list[str]] | Callable[[str, int], list[str]]) -> None:
        self._answers = answers
        self.asked: list[str] = []

    def __call__(self, host: str) -> list[str]:
        self.asked.append(host)
        if callable(self._answers):
            return self._answers(host, len(self.asked))
        return self._answers.get(host, [])


class Web:
    """A fake web server. Records the requests it was sent."""

    def __init__(self, handler: Callable[[httpx.Request], httpx.Response]) -> None:
        self.requests: list[httpx.Request] = []
        self._handler = handler
        self.transport = httpx.MockTransport(self._serve)

    def _serve(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self._handler(request)


def html(status: int = 200, body: str = PAGE, **headers: str) -> httpx.Response:
    return httpx.Response(status, text=body, headers={"content-type": "text/html", **headers})


def fetcher(names: Names, web: Web, **kw: object) -> SafePageFetcher:
    return SafePageFetcher(resolver=names, transport=web.transport, **kw)  # type: ignore[arg-type]


def refused(fetch: SafePageFetcher, url: str) -> PageFetchError:
    with pytest.raises(PageFetchError) as error:
        fetch.fetch_page(url)
    return error.value


def test_a_page_is_read() -> None:
    web = Web(lambda _: html())
    page = fetcher(Names({"jobs.example.com": [PUBLIC]}), web).fetch_page(
        "https://jobs.example.com/a?b=1"
    )
    assert "Backend engineer wanted" in page.html
    assert page.url == "https://jobs.example.com/a?b=1"


def test_the_connection_goes_to_the_address_that_was_checked_not_to_the_name() -> None:
    web = Web(lambda _: html())
    fetcher(Names({"jobs.example.com": [PUBLIC]}), web).fetch_page("https://jobs.example.com/a")
    (request,) = web.requests
    assert request.url.host == PUBLIC  # the pinned address
    assert request.headers["host"] == "jobs.example.com"  # the name, for the site
    assert request.extensions["sni_hostname"] == "jobs.example.com"  # and for the certificate


def test_dns_rebinding_cannot_change_where_the_connection_goes() -> None:
    # The first answer is public. Any later question would get a private address. The fetch asks once
    # and connects to what it checked, so the second answer is never used.
    def answers(_: str, nth: int) -> list[str]:
        return [PUBLIC] if nth == 1 else ["169.254.169.254"]

    names = Names(answers)
    web = Web(lambda _: html())
    fetcher(names, web).fetch_page("https://rebind.example.com/")
    assert names.asked == ["rebind.example.com"]
    assert [r.url.host for r in web.requests] == [PUBLIC]


def test_a_name_that_resolves_to_a_private_address_is_refused_before_any_request() -> None:
    for private in (
        "10.0.0.5",
        "127.0.0.1",
        "169.254.169.254",
        "192.168.1.1",
        "::1",
        "fd00::1",
        "::ffff:10.0.0.1",
    ):
        web = Web(lambda _: html())
        error = refused(
            fetcher(Names({"evil.example.com": [private]}), web), "https://evil.example.com/"
        )
        assert error.code == "private_address", private
        assert web.requests == []


def test_one_private_address_among_public_ones_refuses_the_name() -> None:
    web = Web(lambda _: html())
    names = Names({"mixed.example.com": [PUBLIC, "10.1.1.1"]})
    assert refused(fetcher(names, web), "https://mixed.example.com/").code == "private_address"
    assert web.requests == []


def test_a_name_that_does_not_exist_is_a_clear_refusal() -> None:
    web = Web(lambda _: html())
    assert refused(fetcher(Names({}), web), "https://nothing.example.com/").code == "dns"
    assert web.requests == []


@pytest.mark.parametrize(
    "url",
    [
        "http://jobs.example.com/",
        "https://127.0.0.1/",
        "https://localhost/",
        "https://169.254.169.254/latest/meta-data/",
        "https://[::1]/",
        "https://jobs.example.com:8443/",
        "https://user:pw@jobs.example.com/",
        "https://www.linkedin.com/jobs/view/1",
        "file:///etc/passwd",
    ],
)
def test_addresses_refused_by_the_rules_never_reach_the_name_server_or_the_network(
    url: str,
) -> None:
    names = Names({"jobs.example.com": [PUBLIC]})
    web = Web(lambda _: html())
    refused(fetcher(names, web), url)
    assert names.asked == [] and web.requests == []


def test_a_redirect_to_another_public_site_is_followed_and_checked_again() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.headers["host"] == "short.example.com":
            return httpx.Response(302, headers={"location": "https://jobs.example.org/real"})
        return html()

    names = Names({"short.example.com": [PUBLIC], "jobs.example.org": [OTHER_PUBLIC]})
    web = Web(handler)
    page = fetcher(names, web).fetch_page("https://short.example.com/x")
    assert page.url == "https://jobs.example.org/real"
    assert names.asked == ["short.example.com", "jobs.example.org"]
    assert [r.url.host for r in web.requests] == [PUBLIC, OTHER_PUBLIC]


@pytest.mark.parametrize(
    ("location", "code"),
    [
        ("https://127.0.0.1/admin", "numeric_host"),
        ("https://169.254.169.254/latest/meta-data/", "numeric_host"),
        ("http://jobs.example.org/", "not_https"),
        ("https://localhost/", "internal_host"),
        ("https://internal.example.net/", "private_address"),  # a name that resolves inside
        ("https://www.linkedin.com/jobs/1", "paste_only"),
        ("https://jobs.example.org:8443/", "port"),
        ("file:///etc/passwd", "not_https"),
    ],
)
def test_a_redirect_into_a_private_or_forbidden_place_is_refused(location: str, code: str) -> None:
    web = Web(lambda _: httpx.Response(302, headers={"location": location}))
    names = Names({"start.example.com": [PUBLIC], "internal.example.net": ["10.9.9.9"]})
    error = refused(fetcher(names, web), "https://start.example.com/")
    assert error.code == code
    assert len(web.requests) == 1  # the second hop was never requested


def test_a_relative_redirect_stays_on_the_same_checked_host() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/old":
            return httpx.Response(301, headers={"location": "/new"})
        return html()

    web = Web(handler)
    page = fetcher(Names({"jobs.example.com": [PUBLIC]}), web).fetch_page(
        "https://jobs.example.com/old"
    )
    assert page.url == "https://jobs.example.com/new"


def test_too_many_redirects_stop() -> None:
    web = Web(lambda _: httpx.Response(302, headers={"location": "https://jobs.example.com/again"}))
    error = refused(
        fetcher(Names({"jobs.example.com": [PUBLIC]}), web), "https://jobs.example.com/"
    )
    assert error.code == "redirect"
    assert len(web.requests) == MAX_REDIRECTS + 1


def test_a_redirect_without_a_place_to_go_is_refused() -> None:
    web = Web(lambda _: httpx.Response(302))
    assert (
        refused(
            fetcher(Names({"jobs.example.com": [PUBLIC]}), web), "https://jobs.example.com/"
        ).code
        == "redirect"
    )


def test_a_page_over_the_size_limit_is_stopped_as_it_arrives() -> None:
    web = Web(lambda _: html(body="x" * 5000))
    fetch = fetcher(Names({"jobs.example.com": [PUBLIC]}), web, max_bytes=1000)
    assert refused(fetch, "https://jobs.example.com/").code == "too_large"


def test_a_page_that_lies_about_its_length_is_still_stopped() -> None:
    web = Web(lambda _: html(body="x" * 5000, **{"content-length": "10"}))
    fetch = fetcher(Names({"jobs.example.com": [PUBLIC]}), web, max_bytes=1000)
    with pytest.raises((PageFetchError, httpx.HTTPError)):
        fetch.fetch_page("https://jobs.example.com/")


def test_a_declared_size_over_the_limit_is_refused_without_reading() -> None:
    web = Web(lambda _: html(body="x", **{"content-length": "99999999"}))
    fetch = fetcher(Names({"jobs.example.com": [PUBLIC]}), web, max_bytes=1000)
    assert refused(fetch, "https://jobs.example.com/").code == "too_large"


def test_a_compressed_bomb_is_counted_after_it_is_expanded() -> None:
    bomb = gzip.compress(b"A" * 5_000_000)
    assert len(bomb) < 20_000
    web = Web(
        lambda _: httpx.Response(
            200, content=bomb, headers={"content-type": "text/html", "content-encoding": "gzip"}
        )
    )
    fetch = fetcher(Names({"jobs.example.com": [PUBLIC]}), web, max_bytes=100_000)
    assert refused(fetch, "https://jobs.example.com/").code == "too_large"


@pytest.mark.parametrize(
    "kind", ["application/pdf", "image/png", "application/json", "application/octet-stream", ""]
)
def test_only_pages_are_accepted(kind: str) -> None:
    web = Web(lambda _: httpx.Response(200, content=b"data", headers={"content-type": kind}))
    assert (
        refused(
            fetcher(Names({"jobs.example.com": [PUBLIC]}), web), "https://jobs.example.com/"
        ).code
        == "not_html"
    )


@pytest.mark.parametrize(
    "kind", ["text/html; charset=utf-8", "application/xhtml+xml", "TEXT/PLAIN"]
)
def test_page_types_are_accepted(kind: str) -> None:
    web = Web(lambda _: httpx.Response(200, content=b"hello", headers={"content-type": kind}))
    assert (
        fetcher(Names({"jobs.example.com": [PUBLIC]}), web)
        .fetch_page("https://jobs.example.com/")
        .html
        == "hello"
    )


@pytest.mark.parametrize(
    ("status", "code", "retryable"),
    [
        (401, "blocked_by_site", False),
        (403, "blocked_by_site", False),
        (429, "blocked_by_site", False),
        (451, "blocked_by_site", False),
        (404, "gone", False),
        (410, "gone", False),
        (500, "site_error", True),
        (503, "site_error", True),
        (204, "not_html", False),
        (418, "not_html", False),
    ],
)
def test_answers_that_are_not_a_page(status: int, code: str, retryable: bool) -> None:
    web = Web(lambda _: httpx.Response(status, text="no", headers={"content-type": "text/html"}))
    error = refused(
        fetcher(Names({"jobs.example.com": [PUBLIC]}), web), "https://jobs.example.com/"
    )
    assert (error.code, error.retryable) == (code, retryable)


def test_network_trouble_may_be_retried() -> None:
    def boom(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route")

    error = refused(
        fetcher(Names({"jobs.example.com": [PUBLIC]}), Web(boom)), "https://jobs.example.com/"
    )
    assert (error.code, error.retryable) == ("network", True)


def test_a_timeout_may_be_retried() -> None:
    def slow(_: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow")

    error = refused(
        fetcher(Names({"jobs.example.com": [PUBLIC]}), Web(slow)), "https://jobs.example.com/"
    )
    assert (error.code, error.retryable) == ("timeout", True)


def test_the_whole_request_has_a_deadline() -> None:
    ticks = iter([0.0, 0.0, 100.0, 200.0, 300.0])  # start, first hop, then past the deadline
    web = Web(lambda _: html())
    fetch = fetcher(Names({"jobs.example.com": [PUBLIC]}), web, clock=lambda: next(ticks))
    error = refused(fetch, "https://jobs.example.com/")
    assert (error.code, error.retryable) == ("timeout", True)


def test_no_cookie_is_kept_from_one_request_to_the_next() -> None:
    seen: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers.get("cookie"))
        return html(**{"set-cookie": "session=abc; Path=/"})

    web = Web(handler)
    fetch = fetcher(Names({"jobs.example.com": [PUBLIC]}), web)
    fetch.fetch_page("https://jobs.example.com/1")
    fetch.fetch_page("https://jobs.example.com/2")
    assert seen == [None, None]


def test_the_request_carries_an_honest_name_and_nothing_secret() -> None:
    web = Web(lambda _: html())
    fetcher(Names({"jobs.example.com": [PUBLIC]}), web).fetch_page("https://jobs.example.com/")
    headers = web.requests[0].headers
    assert headers["user-agent"].startswith("Provenance/")
    for name in ("authorization", "cookie", "proxy-authorization", "x-api-key"):
        assert name not in headers


def test_a_wrong_charset_name_does_not_crash() -> None:
    web = Web(
        lambda _: httpx.Response(
            200, content="café".encode(), headers={"content-type": "text/html; charset=nonsense"}
        )
    )
    assert (
        fetcher(Names({"jobs.example.com": [PUBLIC]}), web)
        .fetch_page("https://jobs.example.com/")
        .html
        == "café"
    )
