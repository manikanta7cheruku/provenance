"""Read one web page a person pointed us at, safely.

This is the only code that requests an address a person typed. The fetch module for job sources only
ever asks hosts named in the registry; this one must be careful with any host at all.

The defences, in the order they apply:
  1. The address is checked by pv_domain.url_safety (https, standard port, no credentials, a name that
     can exist on the public internet, not a site that forbids automated reading)
  2. The name is resolved here, once. Every address in the answer must be public. One that is not
     refuses the whole request
  3. The connection is made to the address that was checked, not to the name, so the name cannot
     resolve to somewhere else between the check and the connection (DNS rebinding). The name is still
     sent for the certificate check and as the Host header
  4. Redirects are followed by hand, a few at most, and every hop goes through steps 1 to 3
  5. The answer must be a page (HTML or text), is read as it arrives and stopped at a size limit
     (compressed answers count after decompression), and the whole request has a deadline
  6. No cookies and no credentials are sent or kept

What the page says is untrusted text for the next step. Robots rules are not consulted: this is one
page a person chose to read, not a crawl, and the number of requests per person is limited upstream.
"""

import socket
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urljoin

import httpx

from pv_domain.url_safety import UrlRefused, check_import_url, check_resolved

MAX_PAGE_BYTES = 2 * 1024 * 1024
MAX_REDIRECTS = 3
CONNECT_SECONDS = 5.0
READ_SECONDS = 10.0
DEADLINE_SECONDS = 25.0
USER_AGENT = (
    "Provenance/0.1 (a person asked for this page; one request; contact via the project repository)"
)
_ALLOWED_TYPES = ("text/html", "application/xhtml+xml", "text/plain")


class PageFetchError(Exception):
    """The page could not be read. code is a key of pv_domain.job_import.PAGE_MESSAGES or one of the
    refusal codes of pv_domain.url_safety. retryable means a later attempt may work."""

    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


@dataclass(frozen=True)
class FetchedPage:
    url: str
    html: str


class Resolver(Protocol):
    def __call__(self, host: str) -> list[str]: ...


def system_resolver(host: str) -> list[str]:
    try:
        infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except (socket.gaierror, UnicodeError, OSError):
        return []
    return [str(info[4][0]) for info in infos]


class PageFetcher(Protocol):
    def fetch_page(self, url: str) -> FetchedPage: ...


def _charset(content_type: str) -> str:
    for part in content_type.split(";")[1:]:
        key, _, value = part.strip().partition("=")
        if key.lower() == "charset" and value:
            return value.strip("\"' ").lower()
    return "utf-8"


class SafePageFetcher:
    def __init__(
        self,
        *,
        resolver: Resolver = system_resolver,
        transport: httpx.BaseTransport | None = None,
        max_bytes: int = MAX_PAGE_BYTES,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._resolver = resolver
        self._max = max_bytes
        self._clock = clock
        self._client = httpx.Client(
            transport=transport,
            timeout=httpx.Timeout(READ_SECONDS, connect=CONNECT_SECONDS),
            follow_redirects=False,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml;q=0.9,text/plain;q=0.5",
            },
        )

    def close(self) -> None:
        self._client.close()

    def fetch_page(self, url: str) -> FetchedPage:
        deadline = self._clock() + DEADLINE_SECONDS
        current = url
        for _ in range(MAX_REDIRECTS + 1):
            if self._clock() > deadline:
                raise PageFetchError("timeout", "The site took too long.", retryable=True)
            try:
                safe = check_import_url(current)
                addresses = check_resolved(self._resolver(safe.host))
            except UrlRefused as refused:
                raise PageFetchError(refused.code, refused.message) from refused
            pinned = str(addresses[0])
            target = httpx.URL(safe.url).copy_with(host=pinned)
            request = self._client.build_request(
                "GET",
                target,
                headers={"Host": safe.host},
                extensions={"sni_hostname": safe.host},  # the certificate is checked for the name
            )
            try:
                response = self._send(request, deadline)
            finally:
                self._client.cookies.clear()
            if 300 <= response.status < 400:
                location = response.headers.get("location")
                if not location:
                    raise PageFetchError("redirect", "The page sent us somewhere we cannot follow.")
                current = urljoin(safe.url, location)
                continue
            return self._accept(safe.url, response)
        raise PageFetchError("redirect", "The page sent us on too many times.")

    def _send(self, request: httpx.Request, deadline: float) -> "_Answer":
        try:
            response = self._client.send(request, stream=True)
            try:
                status = response.status_code
                headers = {k.lower(): v for k, v in response.headers.items()}
                if 300 <= status < 400:
                    return _Answer(status, b"", headers)
                declared = headers.get("content-length")
                if declared and declared.isdigit() and int(declared) > self._max:
                    raise PageFetchError("too_large", "The page is larger than the limit.")
                chunks: list[bytes] = []
                total = 0
                for chunk in response.iter_bytes():
                    total += len(chunk)
                    if total > self._max:
                        raise PageFetchError("too_large", "The page is larger than the limit.")
                    if self._clock() > deadline:
                        raise PageFetchError("timeout", "The site took too long.", retryable=True)
                    chunks.append(chunk)
                return _Answer(status, b"".join(chunks), headers)
            finally:
                response.close()
        except PageFetchError:
            raise
        except httpx.TimeoutException as exc:
            raise PageFetchError("timeout", "The site took too long.", retryable=True) from exc
        except httpx.HTTPError as exc:
            raise PageFetchError(
                "network", f"The request failed ({type(exc).__name__}).", retryable=True
            ) from exc

    def _accept(self, url: str, answer: "_Answer") -> FetchedPage:
        status = answer.status
        if status in (404, 410):
            raise PageFetchError("gone", "The page was not found.")
        if status in (401, 403, 429, 451):
            raise PageFetchError("blocked_by_site", "The site did not allow this request.")
        if status >= 500:
            raise PageFetchError("site_error", "The site had a problem.", retryable=True)
        if status != 200:
            raise PageFetchError("not_html", "The address did not return a page.")
        content_type = answer.headers.get("content-type", "")
        if not content_type.lower().split(";")[0].strip().startswith(_ALLOWED_TYPES):
            raise PageFetchError("not_html", "The address did not return a web page.")
        try:
            html = answer.body.decode(_charset(content_type), errors="replace")
        except LookupError:
            html = answer.body.decode("utf-8", errors="replace")
        return FetchedPage(url=url, html=html)


@dataclass(frozen=True)
class _Answer:
    status: int
    body: bytes
    headers: dict[str, str]
