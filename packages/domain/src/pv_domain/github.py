"""The GitHub connection, as pure rules.

A person may connect GitHub so their public repositories can become evidence in their profile. The
rules that keep that safe live here, with no network and no framework:

  - **Least permission.** No OAuth scope is requested at all. With no scope GitHub gives read access
    to public information only. Private repositories are never reachable, and the product says so.
  - **A guarded sign-in.** A random `state` (checked on return, used once, expires in ten minutes)
    and PKCE (S256) so a stolen code is useless.
  - **Untrusted content.** Everything that comes from a repository (names, descriptions, topics, the
    README) is text written by someone else. It is cleaned, capped and stored as data. It is never
    treated as an instruction and never rendered as markup.
  - **Evidence, not decoration.** A selected repository becomes a project entry the person can read
    and edit, with its source shown. Editing it keeps the edit on every later sync.

The gateway is a protocol so the API and the worker use the same rules with a real HTTP client in
production and a test double in tests.
"""

import base64
import hashlib
import re
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol
from urllib.parse import urlencode

from pv_domain.profile import validate_entry

# The scope sent to GitHub. Empty on purpose: public information only.
OAUTH_SCOPE = ""
STATE_TTL = timedelta(minutes=10)

MAX_REPOS_LISTED = 100
MAX_REPOS_SELECTED = 12
SUGGESTED_COUNT = 6
README_MAX_BYTES = 16_000
README_EXCERPT_CHARS = 700
DESCRIPTION_MAX = 1000
NAME_MAX = 120
MAX_TOPICS = 8
TOPIC_MAX = 40

SOURCE = "github"
SOURCE_KEY_PREFIX = "github:"

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f​-‏‪-‮⁦-⁩]")
_SPACES = re.compile(r"[ \t\r\f\v]+")
_BLANK_LINES = re.compile(r"\n{3,}")
_TAG = re.compile(r"<[^>]{0,200}>")
_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_BADGE_LINK = re.compile(r"\[!\[[^\]]*\]\([^)]*\)\]\([^)]*\)")
_LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")
_FENCE = re.compile(r"```.*?```", re.S)
_INLINE_CODE = re.compile(r"`([^`]*)`")
_HEADING = re.compile(r"^#{1,6}\s*", re.M)
_EMPHASIS = re.compile(r"(\*\*|__|\*|_)(?=\S)(.+?)(?<=\S)\1")
_REPO_NAME = re.compile(r"^[A-Za-z0-9._-]{1,100}$")
_FULL_NAME = re.compile(r"^[A-Za-z0-9-]{1,39}/[A-Za-z0-9._-]{1,100}$")


# ---------------------------------------------------------------- what the gateway returns


@dataclass(frozen=True)
class GitHubUser:
    id: int
    login: str


@dataclass(frozen=True)
class RepoInfo:
    id: int
    full_name: str
    name: str
    description: str
    html_url: str
    language: str
    topics: tuple[str, ...]
    stars: int
    fork: bool
    archived: bool
    created_at: str
    pushed_at: str


class GitHubError(Exception):
    """Something the person can be told in one plain sentence. `code` is for the program."""

    def __init__(self, code: str, retry_after_seconds: int | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.retry_after_seconds = retry_after_seconds


ERRORS: dict[str, str] = {
    "not_configured": "GitHub is not set up on this server yet, so it cannot be connected. Nothing was changed.",
    "invalid_code": "GitHub did not accept that sign-in. Start again from the Connect GitHub button.",
    "bad_state": "That sign-in did not match the one that was started, or it took too long. Start again from the Connect GitHub button.",
    "token_invalid": "GitHub says the connection is no longer valid. Connect GitHub again to continue.",
    "rate_limited": "GitHub is asking us to wait before asking again. Your repositories will be read again shortly.",
    "unavailable": "GitHub could not be reached just now. Nothing was changed. Try again in a few minutes.",
    "not_connected": "GitHub is not connected.",
    "too_many_selected": f"Choose at most {MAX_REPOS_SELECTED} repositories. Fewer, better chosen ones read better.",
    "unknown_repo": "One of those repositories is not in your list. Read your repositories again, then choose.",
}


class GitHubGateway(Protocol):
    """Everything the product asks of GitHub. Every call uses the person's access token."""

    def exchange_code(self, code: str, redirect_uri: str, code_verifier: str) -> str: ...

    def get_user(self, token: str) -> GitHubUser: ...

    def list_public_repos(self, token: str, login: str, limit: int) -> list[RepoInfo]: ...

    def get_readme(self, token: str, full_name: str) -> str | None: ...

    def revoke(self, token: str) -> bool: ...


# ---------------------------------------------------------------- the sign-in


def new_state() -> tuple[str, str]:
    """A random state and a PKCE verifier, both unguessable."""
    return secrets.token_urlsafe(32), secrets.token_urlsafe(48)


def state_hash(state: str) -> str:
    """What is stored. The state itself is only ever in the person's browser and on the way back."""
    return hashlib.sha256(state.encode("utf-8")).hexdigest()


def code_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def authorize_url(
    *, oauth_base: str, client_id: str, redirect_uri: str, state: str, verifier: str
) -> str:
    query = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "state": state,
        "code_challenge": code_challenge(verifier),
        "code_challenge_method": "S256",
        "allow_signup": "false",
    }
    if OAUTH_SCOPE:  # never true today. Kept so a scope can only be added here, on purpose.
        query["scope"] = OAUTH_SCOPE
    return f"{oauth_base.rstrip('/')}/login/oauth/authorize?{urlencode(query)}"


def state_expired(created_at: datetime, now: datetime) -> bool:
    return now - created_at > STATE_TTL


# ---------------------------------------------------------------- untrusted text


def clean_text(value: Any, limit: int, *, multiline: bool = False) -> str:
    """Text from a repository, made safe to store and show: no control or direction characters, no
    markup, tidy spaces, and a hard length cap."""
    if not isinstance(value, str):
        return ""
    text = _CONTROL.sub("", value.replace("\r\n", "\n").replace("\r", "\n"))
    text = _TAG.sub("", text)
    text = _SPACES.sub(" ", text)
    if multiline:
        text = _BLANK_LINES.sub("\n\n", "\n".join(line.strip() for line in text.split("\n")))
    else:
        text = " ".join(text.split())
    return text.strip()[:limit].rstrip()


def readme_excerpt(raw: str | None) -> str:
    """The opening of a README as plain prose: badges, images, code blocks, tags and markdown marks
    removed, the first few paragraphs kept, and a hard length cap. It is a summary for the person to
    read and edit, never an instruction."""
    if not raw:
        return ""
    text = raw[:README_MAX_BYTES]
    text = _FENCE.sub("", text)
    text = _BADGE_LINK.sub("", text)
    text = _IMAGE.sub("", text)
    text = _LINK.sub(r"\1", text)
    text = _INLINE_CODE.sub(r"\1", text)
    text = _HEADING.sub("", text)
    text = _EMPHASIS.sub(r"\2", text)
    text = clean_text(text, README_MAX_BYTES, multiline=True)
    paragraphs = [p.replace("\n", " ").strip() for p in text.split("\n\n")]
    kept: list[str] = []
    total = 0
    for paragraph in paragraphs:
        # A real sentence, not a title, a table row or a list of links.
        if len(paragraph) < 40 or paragraph.count("|") > 2:
            continue
        kept.append(paragraph)
        total += len(paragraph)
        if total >= README_EXCERPT_CHARS:
            break
    return " ".join(kept)[:README_EXCERPT_CHARS].rstrip()


def valid_full_name(value: Any) -> bool:
    return isinstance(value, str) and bool(_FULL_NAME.match(value))


def valid_repo_name(value: Any) -> bool:
    return isinstance(value, str) and bool(_REPO_NAME.match(value))


# ---------------------------------------------------------------- from a repository to evidence


def _month(timestamp: str) -> str | None:
    try:
        return datetime.fromisoformat(timestamp.replace("Z", "+00:00")).strftime("%Y-%m")
    except ValueError:
        return None


def _is_recent(timestamp: str, now: datetime) -> bool:
    try:
        pushed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        return False
    return now - pushed < timedelta(days=365)


def repo_to_project(repo: RepoInfo, readme: str, *, now: datetime | None = None) -> dict[str, Any]:
    """The data of a project entry for a repository. Checked by the same rules as an entry the
    person types, so it can never hold more than a person could."""
    now = now or datetime.now(UTC)
    description = clean_text(repo.description, DESCRIPTION_MAX)
    summary = readme_excerpt(readme)
    if description and summary and summary[:60].lower() not in description.lower():
        description = f"{description} {summary}"[:DESCRIPTION_MAX].rstrip()
    elif not description:
        description = summary
    technologies: list[str] = []
    for value in (repo.language, *repo.topics):
        item = clean_text(value, TOPIC_MAX)
        if item and item.lower() not in {t.lower() for t in technologies}:
            technologies.append(item)
        if len(technologies) >= MAX_TOPICS:
            break
    data: dict[str, Any] = {
        "name": clean_text(repo.name, NAME_MAX),
        "description": description,
        "technologies": technologies,
        "url": repo.html_url if repo.html_url.startswith("https://github.com/") else "",
        "start_date": _month(repo.created_at),
        "end_date": "present" if _is_recent(repo.pushed_at, now) else _month(repo.pushed_at),
    }
    return validate_entry("project", data, lenient=True).clean


def source_key(repo_id: int) -> str:
    return f"{SOURCE_KEY_PREFIX}{repo_id}"


# ---------------------------------------------------------------- which repositories to suggest


def suggest_score(repo: RepoInfo, now: datetime) -> float:
    """A rough ordering of how likely a repository is to be worth showing an employer. A hint only,
    the person decides."""
    if repo.fork or repo.archived:
        return -1.0
    score = 1.0
    if repo.description:
        score += 2.0
    if repo.topics:
        score += 0.5
    score += min(repo.stars, 50) / 25
    if _is_recent(repo.pushed_at, now):
        score += 1.5
    return score


def suggest(repos: list[RepoInfo], *, now: datetime | None = None) -> list[int]:
    """The ids of the repositories to tick by default, best first."""
    now = now or datetime.now(UTC)
    ranked = sorted(
        (r for r in repos if suggest_score(r, now) > 0),
        key=lambda r: (-suggest_score(r, now), r.full_name.lower()),
    )
    return [r.id for r in ranked[:SUGGESTED_COUNT]]
