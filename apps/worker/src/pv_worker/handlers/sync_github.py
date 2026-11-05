"""Read the person's public repositories from GitHub and make the chosen ones evidence.

Idempotent by design (the queue delivers at least once): the work is "make the profile match the
chosen repositories", so running it twice, or after a crash, finds nothing more to do.

  - a task for a person who disconnected does nothing
  - the list of repositories is replaced as a whole, keeping the person's choices
  - an entry the person has edited is never overwritten, and a repository that is no longer chosen
    takes its untouched entry with it
  - a connection GitHub no longer accepts is a RESULT (the connection says "connect again"), not a
    task failure to retry
  - only trouble that may pass (GitHub busy, rate limited, unreachable) raises TaskFailure and is
    retried; on the last attempt it becomes a visible failure too

Everything read from a repository is untrusted text. It is cleaned and capped before it is stored
(pv_domain.github) and it is stored as data for the person to read and edit. The token is opened
only here, only for the calls, and never logged.
"""

import logging
import uuid
from collections.abc import Callable

from pv_config import SecretBox, SecretBoxError
from pv_domain.github import (
    ERRORS,
    MAX_REPOS_LISTED,
    GitHubError,
    GitHubGateway,
    RepoInfo,
    readme_excerpt,
    repo_to_project,
    suggest,
)
from pv_github import build_gateway
from pv_persistence.github import (
    apply_entries,
    get_connection,
    list_repos,
    replace_repos,
    set_excerpt,
    set_sync_state,
)
from pv_persistence.models import GitHubRepo
from pv_persistence.tenancy import tenant_session
from pv_worker.contract import TaskContext, TaskFailure

logger = logging.getLogger("pv_worker")

GatewayFactory = Callable[[], GitHubGateway | None]


def handle_sync_github(ctx: TaskContext) -> None:
    run_sync(ctx, gateway_factory=lambda: build_gateway(ctx.settings))


def run_sync(ctx: TaskContext, *, gateway_factory: GatewayFactory) -> None:
    owner = ctx.owner_user_id
    if owner is None:
        raise TaskFailure("The GitHub task has no owner.", retryable=False)
    gateway = gateway_factory()
    if gateway is None:
        _fail(ctx, owner, "not_configured")
        return
    box = SecretBox(ctx.settings.secret_key.get_secret_value())

    with tenant_session(ctx.engine, owner) as db:
        connection = get_connection(db, owner)
        if connection is None:
            return  # disconnected while the task waited
        sealed, login = connection.token_sealed, connection.login
        set_sync_state(db, owner, "syncing")
    try:
        token = box.open(sealed, context=f"github-token:{owner}")
    except SecretBoxError:
        _fail(ctx, owner, "token_invalid")
        return

    try:
        repos = gateway.list_public_repos(token, login, MAX_REPOS_LISTED)
        with tenant_session(ctx.engine, owner) as db:
            replace_repos(db, owner, repos, set(suggest(repos)))
            rows = list_repos(db, owner)
            chosen = {r.repo_id: r for r in rows if r.selected}
            missing = [r for r in chosen.values() if not r.readme_excerpt]
            names = {r.repo_id: r.full_name for r in missing}
        for repo_id, full_name in names.items():
            raw = gateway.get_readme(token, full_name)
            with tenant_session(ctx.engine, owner) as db:
                set_excerpt(db, owner, repo_id, readme_excerpt(raw))
        with tenant_session(ctx.engine, owner) as db:
            rows = [r for r in list_repos(db, owner) if r.selected]
            projects = {r.repo_id: repo_to_project(_info(r), r.readme_excerpt) for r in rows}
            apply_entries(db, owner, projects)
            set_sync_state(db, owner, "idle", done=True)
    except GitHubError as error:
        if error.code == "token_invalid":
            _fail(ctx, owner, "token_invalid")
            return
        if ctx.attempt >= ctx.max_attempts:
            _fail(ctx, owner, error.code)
            return
        with tenant_session(ctx.engine, owner) as db:
            set_sync_state(db, owner, "queued")
        raise TaskFailure(f"GitHub: {error.code}", retryable=True) from error


def _fail(ctx: TaskContext, owner: uuid.UUID, code: str) -> None:
    with tenant_session(ctx.engine, owner) as db:
        set_sync_state(db, owner, "failed", error=ERRORS.get(code, ERRORS["unavailable"]))
    logger.info("github_sync_failed", extra={"reason": code})


def _info(row: GitHubRepo) -> RepoInfo:
    return RepoInfo(
        id=row.repo_id,
        full_name=row.full_name,
        name=row.name,
        description=row.description,
        html_url=row.html_url,
        language=row.language,
        topics=tuple(row.topics or []),
        stars=row.stars,
        fork=row.fork,
        archived=row.archived,
        created_at=row.created_remote,
        pushed_at=row.pushed_remote,
    )
