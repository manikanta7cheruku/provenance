"""Checkpoint 3.1: the GitHub gateway against a fake GitHub. No network: httpx's mock transport answers.
What matters here is what it refuses to do."""

import json

import httpx
import pytest

from pv_domain.github import GitHubError
from pv_github import HttpGitHubGateway, build_gateway

API = "https://api.github.com"
OAUTH = "https://github.com"


def gateway(handler) -> HttpGitHubGateway:  # type: ignore[no-untyped-def]
    return HttpGitHubGateway(
        client_id="cid",
        client_secret="csecret",
        api_base=API,
        oauth_base=OAUTH,
        transport=httpx.MockTransport(handler),
    )


def test_the_code_is_exchanged_with_pkce_and_the_token_is_returned() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = request.content.decode()
        return httpx.Response(
            200, json={"access_token": "gho_abc", "token_type": "bearer", "scope": ""}
        )

    token = gateway(handler).exchange_code("thecode", "http://localhost:5173/cb", "theverifier")
    assert token == "gho_abc"
    assert seen["url"] == f"{OAUTH}/login/oauth/access_token"
    body = str(seen["body"])
    assert (
        "code_verifier=theverifier" in body
        and "code=thecode" in body
        and "client_secret=csecret" in body
    )


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, json={"error": "bad_verification_code"}),
        httpx.Response(200, json={"access_token": ""}),
        httpx.Response(200, text="not json"),
        httpx.Response(400, json={"error": "x"}),
    ],
)
def test_a_refused_or_odd_exchange_is_an_invalid_code(response: httpx.Response) -> None:
    with pytest.raises(GitHubError) as caught:
        gateway(lambda r: response).exchange_code("c", "u", "v")
    assert caught.value.code in {"invalid_code", "unavailable"}


def test_the_token_goes_only_in_the_authorization_header() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"id": 7, "login": "asha"})

    user = gateway(handler).get_user("gho_secret")
    assert user.id == 7 and user.login == "asha"
    assert seen[0].headers["authorization"] == "Bearer gho_secret"
    assert "gho_secret" not in str(seen[0].url)
    assert seen[0].headers["x-github-api-version"] == "2022-11-28"


def test_only_public_repositories_are_listed_and_the_answer_is_cleaned() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/users/asha/repos"
        assert request.url.params["type"] == "owner"
        return httpx.Response(
            200,
            json=[
                {
                    "id": 1,
                    "full_name": "asha/pipeline",
                    "name": "pipeline",
                    "private": False,
                    "description": "A <b>pipeline</b>\x00",
                    "html_url": "https://github.com/asha/pipeline",
                    "language": "Python",
                    "topics": ["etl", 5, "x" * 90],
                    "stargazers_count": 3,
                    "fork": False,
                    "archived": False,
                    "created_at": "2025-01-01T00:00:00Z",
                    "pushed_at": "2026-10-01T00:00:00Z",
                },
                {"id": 2, "full_name": "asha/secret", "name": "secret", "private": True},
                {"id": "x", "full_name": "asha/bad", "name": "bad"},
                {"id": 3, "full_name": "../../etc/passwd", "name": "passwd"},
                {
                    "id": 4,
                    "full_name": "asha/evil",
                    "name": "evil",
                    "html_url": "https://evil.example/x",
                },
                "not a repo",
            ],
        )

    repos = gateway(handler).list_public_repos("tok", "asha", 100)
    assert [r.full_name for r in repos] == ["asha/pipeline", "asha/evil"]
    assert repos[0].description == "A pipeline" and repos[0].topics[0] == "etl"
    assert all(len(t) <= 40 for t in repos[0].topics)
    assert repos[1].html_url == ""  # an address outside github.com is dropped


def test_a_login_that_could_change_the_address_is_refused() -> None:
    for bad in ("../x", "a b", "a/b", "a?b", ""):
        with pytest.raises(GitHubError):
            gateway(lambda r: httpx.Response(200, json=[])).list_public_repos("t", bad, 10)


def test_the_readme_is_capped_and_a_missing_one_is_none() -> None:
    big = "x" * 100_000
    got = gateway(lambda r: httpx.Response(200, text=big)).get_readme("t", "asha/pipeline")
    assert got is not None and len(got) <= 16_000
    assert gateway(lambda r: httpx.Response(404, json={})).get_readme("t", "asha/pipeline") is None
    assert gateway(lambda r: httpx.Response(200, text="x")).get_readme("t", "../etc") is None


def test_a_redirect_is_never_followed() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if request.url.host == "api.github.com":
            return httpx.Response(302, headers={"location": "https://evil.example/steal"})
        return httpx.Response(200, json={})

    with pytest.raises(GitHubError):
        gateway(handler).get_user("tok")
    assert calls == [f"{API}/user"]


def test_a_request_to_another_host_is_refused_before_it_is_made() -> None:
    called: list[str] = []
    gw = gateway(lambda r: called.append(str(r.url)) or httpx.Response(200, json={}))
    with pytest.raises(GitHubError):
        gw._send("GET", "https://evil.example/x", token="tok")
    assert called == []


def test_failures_become_plain_codes() -> None:
    cases = [
        (401, {}, "token_invalid"),
        (403, {"x-ratelimit-remaining": "0"}, "rate_limited"),
        (403, {"retry-after": "30"}, "rate_limited"),
        (429, {}, "rate_limited"),
        (403, {}, "token_invalid"),
        (500, {}, "unavailable"),
        (503, {}, "unavailable"),
    ]
    for status, headers, code in cases:
        with pytest.raises(GitHubError) as caught:
            gateway(lambda r, s=status, h=headers: httpx.Response(s, headers=h, json={})).get_user(
                "t"
            )
        assert caught.value.code == code, (status, headers)
    with pytest.raises(GitHubError) as caught:
        gateway(lambda r: httpx.Response(403, headers={"retry-after": "30"})).get_user("t")
    assert caught.value.retry_after_seconds == 30


def test_a_network_failure_is_unavailable_and_never_leaks_the_token(
    caplog: pytest.LogCaptureFixture,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom gho_secret")

    with pytest.raises(GitHubError) as caught, caplog.at_level("DEBUG"):
        gateway(handler).get_user("gho_secret")
    assert caught.value.code == "unavailable"
    assert "gho_secret" not in caplog.text


def test_an_odd_user_answer_is_refused() -> None:
    for answer in ({"id": "7", "login": "asha"}, {"id": 7, "login": "../x"}, {"id": 7}, [1, 2]):
        with pytest.raises(GitHubError):
            gateway(lambda r, a=answer: httpx.Response(200, content=json.dumps(a))).get_user("t")


def test_revoking_uses_the_app_credentials_and_a_missing_token_counts() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(204)

    assert gateway(handler).revoke("gho_abc") is True
    assert seen[0].method == "DELETE" and seen[0].url.path == "/applications/cid/token"
    assert seen[0].headers["authorization"].startswith("Basic ")
    assert gateway(lambda r: httpx.Response(404)).revoke("t") is True
    assert gateway(lambda r: httpx.Response(500)).revoke("t") is False

    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("x")

    assert gateway(boom).revoke("t") is False


def test_a_gateway_exists_without_an_oauth_app_but_sign_in_is_off() -> None:
    from pv_config import Settings
    from pv_github import oauth_configured

    settings = Settings(
        environment="test",
        database_url="postgresql+psycopg://u:p@h/d",
        migration_database_url="postgresql+psycopg://owner:p@h/d",
        secret_key="k" * 40,
    )
    assert build_gateway(settings) is not None
    assert oauth_configured(settings) is False


def test_a_public_account_is_read_without_any_token() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={"id": 7, "login": "asha-rao", "type": "User"})

    user = gateway(handler).get_public_user("asha-rao")
    assert user.id == 7 and user.login == "asha-rao"
    assert seen["url"] == f"{API}/users/asha-rao" and seen["auth"] is None


@pytest.mark.parametrize(
    ("response", "code"),
    [
        (httpx.Response(404, json={}), "user_not_found"),
        (
            httpx.Response(200, json={"id": 1, "login": "acme", "type": "Organization"}),
            "not_a_person",
        ),
        (httpx.Response(200, text="nope"), "unavailable"),
        (httpx.Response(403, headers={"x-ratelimit-remaining": "0"}), "rate_limited"),
    ],
)
def test_a_public_account_lookup_fails_with_a_plain_code(
    response: httpx.Response, code: str
) -> None:
    with pytest.raises(GitHubError) as caught:
        gateway(lambda r: response).get_public_user("someone")
    assert caught.value.code == code
