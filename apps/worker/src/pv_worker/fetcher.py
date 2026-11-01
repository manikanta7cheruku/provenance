"""The only code that talks to a job source over the network.

Everything a poll does goes through here, so the limits live in one place and every caller gets them:

  - HTTPS only, to a host the adapter names, on the default port. Nothing a person types ever reaches
    this module: addresses are built from the registry and checked again here
  - no redirects are followed (a redirect to another host is refused, not trusted)
  - a limit on the size of an answer, read as it arrives, and a timeout
  - a plain, honest User-Agent that says what this is
  - no cookies and no credentials: only sources that need none are fetched in this checkpoint

How often to ask, and when to stop, are decided by pv_domain.fetching and the poll handler.
"""

from dataclasses import dataclass, field
from typing import Protocol
from urllib.parse import urlsplit

import httpx

MAX_BYTES = 25 * 1024 * 1024
CONNECT_SECONDS = 5.0
READ_SECONDS = 30.0
USER_AGENT = (
    "Provenance/0.1 (job research tool; polite polling; contact via the project repository)"
)


class FetchError(Exception):
    """The request could not be made or its answer could not be accepted.

    kind is one of: blocked, redirect, too_large, network."""

    def __init__(self, kind: str, message: str) -> None:
        super().__init__(message)
        self.kind = kind


@dataclass(frozen=True)
class FetchResponse:
    status: int
    body: bytes
    headers: dict[str, str] = field(default_factory=dict)


class Fetcher(Protocol):
    def get(self, url: str, *, hosts: tuple[str, ...]) -> FetchResponse: ...


def check_url(url: str, hosts: tuple[str, ...]) -> None:
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.hostname not in hosts or parts.port not in (None, 443):
        raise FetchError("blocked", "That address is not one this source may be asked for.")
    if parts.username or parts.password:
        raise FetchError("blocked", "Addresses with credentials are not used.")


class HttpxFetcher:
    def __init__(
        self,
        *,
        max_bytes: int = MAX_BYTES,
        transport: httpx.BaseTransport | None = None,
        user_agent: str = USER_AGENT,
    ) -> None:
        self._max = max_bytes
        self._client = httpx.Client(
            transport=transport,
            timeout=httpx.Timeout(READ_SECONDS, connect=CONNECT_SECONDS),
            follow_redirects=False,
            headers={"User-Agent": user_agent, "Accept": "application/json"},
            cookies=None,
        )

    def get(self, url: str, *, hosts: tuple[str, ...]) -> FetchResponse:
        check_url(url, hosts)
        try:
            with self._client.stream("GET", url) as response:
                if 300 <= response.status_code < 400:
                    raise FetchError(
                        "redirect", "The source answered with a redirect, which is not followed."
                    )
                declared = response.headers.get("content-length")
                if declared and declared.isdigit() and int(declared) > self._max:
                    raise FetchError("too_large", "The answer is larger than the limit.")
                chunks: list[bytes] = []
                total = 0
                for chunk in response.iter_bytes():
                    total += len(chunk)
                    if total > self._max:
                        raise FetchError("too_large", "The answer is larger than the limit.")
                    chunks.append(chunk)
                return FetchResponse(
                    response.status_code,
                    b"".join(chunks),
                    {k.lower(): v for k, v in response.headers.items()},
                )
        except FetchError:
            raise
        except httpx.HTTPError as exc:
            raise FetchError("network", f"The request failed ({type(exc).__name__}).") from exc
        finally:
            self._client.cookies.clear()  # a source cannot make us carry a cookie to the next request

    def close(self) -> None:
        self._client.close()
