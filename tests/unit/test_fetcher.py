"""Checkpoint 2.6: the one place that talks to a job source. Every limit is tested without a network."""

import httpx
import pytest

from pv_worker.fetcher import USER_AGENT, FetchError, HttpxFetcher, check_url

HOSTS = ("api.lever.co",)
URL = "https://api.lever.co/v0/postings/demo?mode=json"


def fetcher(handler: httpx.MockTransport | None = None, **kw: int) -> HttpxFetcher:
    return HttpxFetcher(
        transport=handler or httpx.MockTransport(lambda r: httpx.Response(200, json=[])), **kw
    )


class TestWhereItMayAsk:
    @pytest.mark.parametrize(
        "url",
        [
            "http://api.lever.co/v0/postings/x",
            "https://evil.example/v0/postings/x",
            "https://api.lever.co.evil.example/x",
            "https://api.lever.co:8443/x",
            "https://user:pw@api.lever.co/x",
            "ftp://api.lever.co/x",
            "file:///etc/passwd",
            "https://127.0.0.1/x",
            "//api.lever.co/x",
            "",
        ],
    )
    def test_only_https_to_an_allowed_host_on_the_default_port(self, url: str) -> None:
        with pytest.raises(FetchError) as caught:
            check_url(url, HOSTS)
        assert caught.value.kind == "blocked"

    def test_an_allowed_address_passes(self) -> None:
        check_url(URL, HOSTS)
        check_url("https://api.lever.co:443/x", HOSTS)

    def test_a_blocked_address_never_reaches_the_network(self) -> None:
        calls: list[str] = []
        transport = httpx.MockTransport(lambda r: calls.append(str(r.url)) or httpx.Response(200))
        with pytest.raises(FetchError):
            fetcher(transport).get("https://evil.example/x", hosts=HOSTS)
        assert calls == []


class TestWhatItAccepts:
    def test_a_normal_answer_comes_back_with_lowercase_headers(self) -> None:
        transport = httpx.MockTransport(
            lambda r: httpx.Response(200, json=[{"a": 1}], headers={"Retry-After": "5"})
        )
        response = fetcher(transport).get(URL, hosts=HOSTS)
        assert response.status == 200 and response.headers["retry-after"] == "5"
        assert response.body == b'[{"a":1}]'

    def test_it_says_who_it_is_and_sends_no_cookies(self) -> None:
        seen: list[httpx.Request] = []

        def handle(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return httpx.Response(200, json=[], headers={"Set-Cookie": "a=b"})

        client = fetcher(httpx.MockTransport(handle))
        client.get(URL, hosts=HOSTS)
        client.get(URL, hosts=HOSTS)
        assert seen[0].headers["user-agent"] == USER_AGENT and "Provenance" in USER_AGENT
        assert "cookie" not in seen[1].headers and "authorization" not in seen[1].headers

    @pytest.mark.parametrize("status", [301, 302, 307, 308])
    def test_a_redirect_is_refused_not_followed(self, status: int) -> None:
        calls: list[str] = []

        def handle(request: httpx.Request) -> httpx.Response:
            calls.append(str(request.url))
            return httpx.Response(status, headers={"Location": "https://evil.example/steal"})

        with pytest.raises(FetchError) as caught:
            fetcher(httpx.MockTransport(handle)).get(URL, hosts=HOSTS)
        assert caught.value.kind == "redirect" and calls == [URL]

    def test_an_answer_that_declares_itself_too_large_is_refused_before_reading(self) -> None:
        transport = httpx.MockTransport(
            lambda r: httpx.Response(200, headers={"Content-Length": "999999"}, content=b"x")
        )
        with pytest.raises(FetchError) as caught:
            fetcher(transport, max_bytes=1000).get(URL, hosts=HOSTS)
        assert caught.value.kind == "too_large"

    def test_an_answer_that_grows_past_the_limit_is_stopped_while_reading(self) -> None:
        def body():
            for _ in range(100):
                yield b"x" * 100

        transport = httpx.MockTransport(lambda r: httpx.Response(200, content=body()))
        with pytest.raises(FetchError) as caught:
            fetcher(transport, max_bytes=2000).get(URL, hosts=HOSTS)
        assert caught.value.kind == "too_large"

    def test_a_network_failure_is_one_clean_error_without_the_address_in_it(self) -> None:
        def handle(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("boom", request=request)

        with pytest.raises(FetchError) as caught:
            fetcher(httpx.MockTransport(handle)).get(URL, hosts=HOSTS)
        assert caught.value.kind == "network" and "lever" not in str(caught.value)

    def test_a_timeout_is_a_network_error(self) -> None:
        def handle(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("slow", request=request)

        with pytest.raises(FetchError) as caught:
            fetcher(httpx.MockTransport(handle)).get(URL, hosts=HOSTS)
        assert caught.value.kind == "network"

    def test_error_statuses_are_returned_for_the_caller_to_judge(self) -> None:
        for status in (404, 429, 500):
            transport = httpx.MockTransport(lambda r, s=status: httpx.Response(s))
            assert fetcher(transport).get(URL, hosts=HOSTS).status == status
