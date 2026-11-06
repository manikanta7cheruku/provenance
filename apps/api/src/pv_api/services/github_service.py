"""The GitHub connection: start a sign-in, finish it, choose repositories, read again, disconnect.

Everything runs in one tenant session (Row Level Security) and filters by the signed-in person. The
rules (no scope, state and PKCE, what a repository may become) are in pv_domain.github. This module
is the order of things and the sentences the person reads.

What it guarantees:
  - the person's token is sealed before it is stored and is never in a response, a log or an audit
    record;
  - a sign-in return is accepted once, only for the person who started it, and only within ten
    minutes. The state is checked before GitHub is asked for anything;
  - disconnecting deletes the token, tells GitHub to revoke it (best effort, and the answer is
    reported honestly), and removes what came from GitHub unless the person asks to keep it.
"""

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from pv_api.errors import ApiError
from pv_api.schemas import (
    GitHubDisconnectOut,
    GitHubFinishOut,
    GitHubOut,
    GitHubRepoOut,
    GitHubStartOut,
    PlatformOut,
)
from pv_config import SecretBox, SecretBoxError, Settings
from pv_domain.failures import FailureClass
from pv_domain.github import (
    ERRORS,
    LINK_ONLY,
    MAX_REPOS_SELECTED,
    OAUTH_SCOPE,
    SOURCE,
    GitHubError,
    GitHubGateway,
    authorize_url,
    new_state,
    parse_github_login,
    state_hash,
)
from pv_domain.tasks import TASK_SYNC_GITHUB
from pv_github import oauth_configured
from pv_persistence.audit import record_audit
from pv_persistence.github import (
    choose_repos,
    get_connection,
    list_repos,
    remove_connection,
    save_connection,
    set_sync_state,
    start_state,
    take_state,
)
from pv_persistence.models import GitHubRepo, ProfileEntry
from pv_persistence.queue import enqueue
from pv_persistence.tenancy import tenant_session

logger = logging.getLogger("pv_api")

CALLBACK_PATH = "/connect/github/callback"

SCOPE_SENTENCE = (
    "Provenance asks GitHub for no permissions at all. That gives it read access to public "
    "information only: your public repositories and their README files. It cannot see private "
    "repositories, cannot change anything on GitHub, and never sees your password."
)

# Places a person has evidence that cannot be connected, and what to do instead. These platforms do
# not allow automated access, so the honest path is to give us what you can export or copy yourself.
PLATFORMS: list[PlatformOut] = [
    PlatformOut(
        name="LinkedIn",
        why="LinkedIn does not allow other products to read your profile.",
        what="Download your profile as a PDF from LinkedIn (More, Save to PDF) and upload it under Your resume. You check every entry before it counts.",
    ),
    PlatformOut(
        name="Naukri",
        why="Naukri does not offer a way for other products to read your profile.",
        what="Download your resume from Naukri and upload it under Your resume, or add an entry by hand.",
    ),
    PlatformOut(
        name="Wellfound",
        why="Wellfound does not allow automated reading of profiles.",
        what="Copy the experience and projects you want counted and add them as entries by hand.",
    ),
    PlatformOut(
        name="Anywhere else",
        why="A portfolio, a paper, a certificate or a talk is evidence too.",
        what="Add it as an entry by hand with its link. Nothing is fetched from the link. It is kept for you to open.",
    ),
]


def _not_found() -> ApiError:
    return ApiError(404, "NOT_FOUND", "Not found.", failure_class=FailureClass.PERMANENT)


def _redirect_uri(settings: Settings) -> str:
    return f"{settings.public_base_url.rstrip('/')}{CALLBACK_PATH}"


def _box(settings: Settings) -> SecretBox:
    return SecretBox.for_settings(settings)


def _error(code: str) -> ApiError:
    message = ERRORS.get(code, ERRORS["unavailable"])
    status = {"not_configured": 503, "unavailable": 503, "rate_limited": 429}.get(code, 400)
    return ApiError(
        status,
        f"GITHUB_{code.upper()}",
        message,
        failure_class=FailureClass.TRANSIENT
        if status in (429, 503)
        else FailureClass.VALIDATION_FAILED,
    )


def _repo_out(row: GitHubRepo) -> GitHubRepoOut:
    return GitHubRepoOut(
        id=row.repo_id,
        full_name=row.full_name,
        name=row.name,
        description=row.description,
        language=row.language,
        topics=list(row.topics or []),
        stars=row.stars,
        fork=row.fork,
        archived=row.archived,
        url=row.html_url,
        selected=row.selected,
        suggested=row.suggested,
        has_excerpt=bool(row.readme_excerpt),
    )


def status(engine: Engine, settings: Settings, available: bool, user_id: uuid.UUID) -> GitHubOut:
    with tenant_session(engine, user_id) as db:
        connection = get_connection(db, user_id)
        repos = list_repos(db, user_id) if connection else []
        count = int(
            db.execute(
                select(func.count())
                .select_from(ProfileEntry)
                .where(ProfileEntry.owner_user_id == user_id, ProfileEntry.source == SOURCE)
            ).scalar_one()
        )
        return GitHubOut(
            available=available,
            connected=connection is not None,
            verified=connection is not None and connection.token_sealed != LINK_ONLY,
            login=connection.login if connection else None,
            profile_url=f"https://github.com/{connection.login}" if connection else None,
            scope=OAUTH_SCOPE,
            scope_sentence=SCOPE_SENTENCE,
            sync_state=connection.sync_state if connection else "idle",
            sync_error=connection.sync_error if connection else None,
            connected_at=connection.connected_at if connection else None,
            last_synced_at=connection.last_synced_at if connection else None,
            repos=[_repo_out(r) for r in repos],
            max_selected=MAX_REPOS_SELECTED,
            entries_from_github=count,
            platforms=PLATFORMS,
        )


def start(
    engine: Engine,
    settings: Settings,
    gateway: GitHubGateway | None,
    user_id: uuid.UUID,
    ip_hash: str | None,
) -> GitHubStartOut:
    if gateway is None or not oauth_configured(settings):
        raise _error("not_configured")
    state, verifier = new_state()
    sealed = _box(settings).seal(verifier, context=f"github-verifier:{user_id}")
    with tenant_session(engine, user_id) as db:
        start_state(db, user_id, state_hash(state), sealed)
    record_audit(
        engine, category="audit", action="github.sign_in_started", actor_user_id=user_id,
        target_type="github", target_id=str(user_id), ip_hash=ip_hash,
    )  # fmt: skip
    return GitHubStartOut(
        authorize_url=authorize_url(
            oauth_base=settings.github_oauth_base,
            client_id=settings.github_client_id,
            redirect_uri=_redirect_uri(settings),
            state=state,
            verifier=verifier,
        )
    )


def finish(
    engine: Engine,
    settings: Settings,
    gateway: GitHubGateway | None,
    user_id: uuid.UUID,
    code: str,
    state: str,
    ip_hash: str | None,
) -> GitHubFinishOut:
    if gateway is None or not oauth_configured(settings):
        raise _error("not_configured")
    now = datetime.now(UTC)
    box = _box(settings)
    # The state is used up before GitHub is asked for anything, so a second return with it finds
    # nothing, and a failed exchange means starting again.
    with tenant_session(engine, user_id) as db:
        sealed_verifier = take_state(db, user_id, state_hash(state), now)
    if sealed_verifier is None:
        raise _error("bad_state")
    try:
        verifier = box.open(sealed_verifier, context=f"github-verifier:{user_id}")
    except SecretBoxError as exc:
        raise _error("bad_state") from exc
    try:
        token = gateway.exchange_code(code, _redirect_uri(settings), verifier)
        user = gateway.get_user(token)
    except GitHubError as exc:
        raise _error(exc.code) from exc
    sealed_token = box.seal(token, context=f"github-token:{user_id}")
    with tenant_session(engine, user_id) as db:
        connection = save_connection(
            db,
            owner_id=user_id,
            github_user_id=user.id,
            login=user.login,
            token_sealed=sealed_token,
        )
        set_sync_state(db, user_id, "queued")
        _queue_sync(db, user_id)
        login = connection.login
    record_audit(
        engine, category="audit", action="github.connected", actor_user_id=user_id,
        target_type="github", target_id=str(user_id), ip_hash=ip_hash,
        metadata={"scope": OAUTH_SCOPE or "none"},
    )  # fmt: skip
    return GitHubFinishOut(login=login)


def link(
    engine: Engine,
    gateway: GitHubGateway | None,
    user_id: uuid.UUID,
    pasted: str,
    ip_hash: str | None,
) -> GitHubFinishOut:
    """Use a pasted GitHub link. Only public information is read, with no sign-in, so the
    connection is not proven to be the person's: it is stored with no token and shown as unverified.
    """
    if gateway is None:
        raise _error("unavailable")
    login = parse_github_login(pasted)
    if login is None:
        raise _error("bad_link")
    try:
        user = gateway.get_public_user(login)
    except GitHubError as exc:
        raise _error(exc.code) from exc
    with tenant_session(engine, user_id) as db:
        existing = get_connection(db, user_id)
        if (
            existing is not None
            and existing.token_sealed != LINK_ONLY
            and existing.github_user_id == user.id
        ):
            return GitHubFinishOut(login=existing.login)  # already verified for this account
        connection = save_connection(
            db, owner_id=user_id, github_user_id=user.id, login=user.login, token_sealed=LINK_ONLY
        )
        set_sync_state(db, user_id, "queued")
        _queue_sync(db, user_id)
        saved = connection.login
    record_audit(
        engine, category="audit", action="github.link_added", actor_user_id=user_id,
        target_type="github", target_id=str(user_id), ip_hash=ip_hash,
    )  # fmt: skip
    return GitHubFinishOut(login=saved)


def _queue_sync(db: Session, user_id: uuid.UUID) -> None:
    enqueue(
        db,
        task_type=TASK_SYNC_GITHUB,
        idempotency_key=f"{TASK_SYNC_GITHUB}:{user_id}:{uuid.uuid4().hex}",
        payload={},
        owner_user_id=user_id,
        max_attempts=4,
    )


def sync(engine: Engine, user_id: uuid.UUID) -> None:
    with tenant_session(engine, user_id) as db:
        connection = get_connection(db, user_id)
        if connection is None:
            raise _error("not_connected")
        if connection.sync_state in ("queued", "syncing"):
            return
        set_sync_state(db, user_id, "queued")
        _queue_sync(db, user_id)


def choose(engine: Engine, user_id: uuid.UUID, repo_ids: list[int], ip_hash: str | None) -> None:
    wanted = set(repo_ids)
    if len(wanted) > MAX_REPOS_SELECTED:
        raise _error("too_many_selected")
    with tenant_session(engine, user_id) as db:
        if get_connection(db, user_id) is None:
            raise _error("not_connected")
        if not choose_repos(db, user_id, wanted):
            raise _error("unknown_repo")
        set_sync_state(db, user_id, "queued")
        _queue_sync(db, user_id)
    record_audit(
        engine, category="audit", action="github.repos_chosen", actor_user_id=user_id,
        target_type="github", target_id=str(user_id), ip_hash=ip_hash,
        metadata={"count": len(wanted)},
    )  # fmt: skip


def disconnect(
    engine: Engine,
    settings: Settings,
    gateway: GitHubGateway | None,
    user_id: uuid.UUID,
    keep_entries: bool,
    ip_hash: str | None,
) -> GitHubDisconnectOut:
    sealed: str | None = None
    with tenant_session(engine, user_id) as db:
        connection = get_connection(db, user_id)
        if connection is None:
            raise _error("not_connected")
        sealed = connection.token_sealed
    revoked = sealed == LINK_ONLY  # a pasted link has no token, so there is nothing to revoke
    if gateway is not None and sealed and sealed != LINK_ONLY:
        try:
            token = _box(settings).open(sealed, context=f"github-token:{user_id}")
            revoked = gateway.revoke(token)
        except SecretBoxError:
            revoked = False
    # The token is deleted here whether or not GitHub confirmed.
    with tenant_session(engine, user_id) as db:
        removed = remove_connection(db, user_id, keep_entries=keep_entries)
    record_audit(
        engine, category="audit", action="github.disconnected", actor_user_id=user_id,
        target_type="github", target_id=str(user_id), ip_hash=ip_hash,
        metadata={"revoked": revoked, "entries_removed": removed, "kept": keep_entries},
    )  # fmt: skip
    return GitHubDisconnectOut(revoked=revoked, entries_removed=removed)
