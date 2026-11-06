"""The one place that talks to GitHub.

Rules this client keeps, because the other side of the connection is a third party and everything it
sends is untrusted:

  - it only ever contacts the two hosts the operator configured (the OAuth host and the API
    host). A request to any other address is refused before it is made, so a URL inside a
    response can never send it somewhere else;
  - it never follows a redirect;
  - it has a short timeout, and it reads at most a fixed number of bytes from any answer;
  - it sends the person's token only in the Authorization header, never in an address, and never
    logs it;
  - it turns every failure into a `GitHubError` with a plain code, so no raw answer, header or
    token reaches a log line or a person's screen.
"""

import json
import logging
from typing import Any
from urllib.parse import urlsplit

import httpx

from pv_domain.github import (
    MAX_REPOS_LISTED,
    README_MAX_BYTES,
    GitHubError,
    GitHubUser,
    RepoInfo,
    clean_text,
    valid_full_name,
    valid_repo_name,
)

logger = logging.getLogger("pv_github")

_API_VERSION = "2022-11-28"
_TIMEOUT = httpx.Timeout(10.0, connect=5.0)
_MAX_JSON_BYTES = 2_000_000


class HttpGitHubGateway:
    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        api_base: str,
        oauth_base: str,
        default_token: str = "",
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._default_token = default_token
        self._api_base = api_base.rstrip("/")
        self._oauth_base = oauth_base.rstrip("/")
        self._allowed = {urlsplit(self._api_base).netloc, urlsplit(self._oauth_base).netloc}
        self._http = httpx.Client(
            timeout=_TIMEOUT,
            follow_redirects=False,
            headers={"User-Agent": "Provenance", "X-GitHub-Api-Version": _API_VERSION},
            transport=transport,
        )

    # ------------------------------------------------------------ plumbing

    def _send(
        self,
        method: str,
        url: str,
        *,
        token: str | None = None,
        accept: str = "application/vnd.github+json",
        max_bytes: int = _MAX_JSON_BYTES,
        **kwargs: Any,
    ) -> tuple[int, bytes, httpx.Headers]:
        if urlsplit(url).netloc not in self._allowed:
            raise GitHubError("unavailable")
        headers = {"Accept": accept}
        # A person's own token wins. Otherwise the operator's token, if any, raises the limit.
        bearer = token or self._default_token
        if bearer:
            headers["Authorization"] = f"Bearer {bearer}"
        try:
            with self._http.stream(method, url, headers=headers, **kwargs) as response:
                body = bytearray()
                for chunk in response.iter_bytes():
                    body.extend(chunk)
                    if len(body) > max_bytes:
                        break
                status, answer_headers = response.status_code, response.headers
        except httpx.HTTPError as exc:
            logger.warning("github_unreachable", extra={"error": type(exc).__name__})
            raise GitHubError("unavailable") from exc
        return status, bytes(body[:max_bytes]), answer_headers

    @staticmethod
    def _check(status: int, headers: httpx.Headers) -> None:
        if status == 401:
            raise GitHubError("token_invalid")
        if status in (403, 429):
            retry = headers.get("retry-after")
            remaining = headers.get("x-ratelimit-remaining")
            if retry or remaining == "0" or status == 429:
                seconds = int(retry) if retry and retry.isdigit() else None
                raise GitHubError("rate_limited", seconds)
            raise GitHubError("token_invalid")
        if status >= 500:
            raise GitHubError("unavailable")

    @staticmethod
    def _json(body: bytes) -> Any:
        try:
            return json.loads(body)
        except ValueError as exc:
            raise GitHubError("unavailable") from exc

    # ------------------------------------------------------------ the calls

    def exchange_code(self, code: str, redirect_uri: str, code_verifier: str) -> str:
        status, body, headers = self._send(
            "POST",
            f"{self._oauth_base}/login/oauth/access_token",
            accept="application/json",
            data={
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
                "code_verifier": code_verifier,
            },
        )
        if status >= 500:
            raise GitHubError("unavailable")
        if status == 429:
            self._check(status, headers)
        data = self._json(body)
        token = data.get("access_token") if isinstance(data, dict) else None
        if status != 200 or not isinstance(token, str) or not token:
            raise GitHubError("invalid_code")
        return token

    def get_user(self, token: str) -> GitHubUser:
        status, body, headers = self._send("GET", f"{self._api_base}/user", token=token)
        self._check(status, headers)
        data = self._json(body)
        if status != 200 or not isinstance(data, dict):
            raise GitHubError("unavailable")
        user_id, login = data.get("id"), data.get("login")
        if not isinstance(user_id, int) or not isinstance(login, str) or not valid_repo_name(login):
            raise GitHubError("unavailable")
        return GitHubUser(id=user_id, login=login)

    def get_public_user(self, login: str) -> GitHubUser:
        """A person's public account by name. No sign-in: this is what makes pasting a link work."""
        if not valid_repo_name(login):
            raise GitHubError("bad_link")
        status, body, headers = self._send("GET", f"{self._api_base}/users/{login}")
        if status == 404:
            raise GitHubError("user_not_found")
        self._check(status, headers)
        data = self._json(body)
        if status != 200 or not isinstance(data, dict):
            raise GitHubError("unavailable")
        user_id, name = data.get("id"), data.get("login")
        if not isinstance(user_id, int) or not isinstance(name, str) or not valid_repo_name(name):
            raise GitHubError("unavailable")
        if data.get("type") != "User":
            raise GitHubError("not_a_person")
        return GitHubUser(id=user_id, login=name)

    def list_public_repos(self, token: str, login: str, limit: int) -> list[RepoInfo]:
        if not valid_repo_name(login):
            raise GitHubError("unavailable")
        per_page = min(limit, MAX_REPOS_LISTED)
        status, body, headers = self._send(
            "GET",
            f"{self._api_base}/users/{login}/repos?type=owner&sort=pushed&per_page={per_page}",
            token=token or None,
        )
        self._check(status, headers)
        data = self._json(body)
        if status != 200 or not isinstance(data, list):
            raise GitHubError("unavailable")
        repos: list[RepoInfo] = []
        for item in data[:per_page]:
            repo = _repo(item)
            if repo is not None:
                repos.append(repo)
        return repos

    def get_readme(self, token: str, full_name: str) -> str | None:
        if not valid_full_name(full_name):
            return None
        status, body, headers = self._send(
            "GET",
            f"{self._api_base}/repos/{full_name}/readme",
            token=token or None,
            accept="application/vnd.github.raw+json",
            max_bytes=README_MAX_BYTES,
        )
        if status == 404:
            return None
        self._check(status, headers)
        if status != 200:
            return None
        return body.decode("utf-8", errors="replace")

    def revoke(self, token: str) -> bool:
        if not self._client_id or not self._client_secret:
            return False
        try:
            response = self._http.request(
                "DELETE",
                f"{self._api_base}/applications/{self._client_id}/token",
                auth=(self._client_id, self._client_secret),
                headers={"Accept": "application/vnd.github+json"},
                json={"access_token": token},
            )
        except httpx.HTTPError:
            return False
        return response.status_code in (204, 404)


def _repo(item: Any) -> RepoInfo | None:
    """One repository from the list, or None when it is not what was expected. Nothing here is
    trusted: types are checked and text is cleaned before it can be stored."""
    if not isinstance(item, dict) or item.get("private") is True:
        return None
    repo_id, full_name, name = item.get("id"), item.get("full_name"), item.get("name")
    if not isinstance(repo_id, int) or not valid_full_name(full_name) or not valid_repo_name(name):
        return None
    html_url = item.get("html_url")
    topics = item.get("topics")
    return RepoInfo(
        id=repo_id,
        full_name=str(full_name),
        name=str(name),
        description=clean_text(item.get("description"), 400),
        html_url=html_url
        if isinstance(html_url, str) and html_url.startswith("https://github.com/")
        else "",
        language=clean_text(item.get("language"), 40),
        topics=tuple(clean_text(t, 40) for t in topics[:8] if isinstance(t, str))
        if isinstance(topics, list)
        else (),
        stars=item["stargazers_count"] if isinstance(item.get("stargazers_count"), int) else 0,
        fork=item.get("fork") is True,
        archived=item.get("archived") is True,
        created_at=str(item.get("created_at") or ""),
        pushed_at=str(item.get("pushed_at") or ""),
    )
