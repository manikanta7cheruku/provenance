"""The GitHub connection in the database.

Call everything here inside tenant_session (Row Level Security applies). Every statement also
filters by owner. What a repository may become is decided in pv_domain.github. This module
stores the connection (token sealed by the caller), the started sign-ins, the repositories last
read, and turns the chosen repositories into profile entries without ever overwriting what the
person edited.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from pv_domain.github import SOURCE, RepoInfo, source_key, state_expired
from pv_persistence.evidence import sync_evidence
from pv_persistence.models import GitHubConnection, GitHubOAuthState, GitHubRepo, ProfileEntry


def get_connection(db: Session, owner_id: uuid.UUID) -> GitHubConnection | None:
    return db.execute(
        select(GitHubConnection).where(GitHubConnection.owner_user_id == owner_id)
    ).scalar_one_or_none()


def save_connection(
    db: Session, *, owner_id: uuid.UUID, github_user_id: int, login: str, token_sealed: str
) -> GitHubConnection:
    """Create the connection, or replace the one there (a person connecting again)."""
    row = get_connection(db, owner_id)
    if row is None:
        row = GitHubConnection(
            owner_user_id=owner_id,
            github_user_id=github_user_id,
            login=login,
            token_sealed=token_sealed,
            scope="",
        )
        db.add(row)
    else:
        row.github_user_id = github_user_id
        row.login = login
        row.token_sealed = token_sealed
        row.sync_state = "idle"
        row.sync_error = None
    db.flush()
    return row


def set_sync_state(
    db: Session, owner_id: uuid.UUID, state: str, *, error: str | None = None, done: bool = False
) -> None:
    values: dict[str, Any] = {"sync_state": state, "sync_error": (error or None)}
    if done:
        values["last_synced_at"] = datetime.now(UTC)
    db.execute(
        update(GitHubConnection).where(GitHubConnection.owner_user_id == owner_id).values(**values)
    )


# ---------------------------------------------------------------- the sign-in


def start_state(db: Session, owner_id: uuid.UUID, state_digest: str, verifier_sealed: str) -> None:
    # One live sign-in per person: starting again replaces the earlier one.
    db.execute(
        delete(GitHubOAuthState).where(
            GitHubOAuthState.owner_user_id == owner_id, GitHubOAuthState.used_at.is_(None)
        )
    )
    db.add(
        GitHubOAuthState(
            owner_user_id=owner_id, state_hash=state_digest, verifier_sealed=verifier_sealed
        )
    )
    db.flush()


def take_state(db: Session, owner_id: uuid.UUID, state_digest: str, now: datetime) -> str | None:
    """Use a started sign-in once. Returns the sealed verifier, or None when the state is unknown,
    belongs to someone else, was used, or has expired. The row is marked used before anything else
    happens, so a second return with the same state finds nothing."""
    row = db.execute(
        select(GitHubOAuthState)
        .where(
            GitHubOAuthState.owner_user_id == owner_id,
            GitHubOAuthState.state_hash == state_digest,
        )
        .with_for_update()
    ).scalar_one_or_none()
    if row is None or row.used_at is not None or state_expired(row.created_at, now):
        return None
    row.used_at = now
    db.flush()
    return row.verifier_sealed


def purge_states(db: Session, owner_id: uuid.UUID) -> None:
    db.execute(delete(GitHubOAuthState).where(GitHubOAuthState.owner_user_id == owner_id))


# ---------------------------------------------------------------- repositories


def list_repos(db: Session, owner_id: uuid.UUID) -> list[GitHubRepo]:
    return list(
        db.execute(
            select(GitHubRepo)
            .where(GitHubRepo.owner_user_id == owner_id)
            .order_by(GitHubRepo.selected.desc(), GitHubRepo.pushed_remote.desc(), GitHubRepo.name)
        ).scalars()
    )


def replace_repos(
    db: Session, owner_id: uuid.UUID, repos: list[RepoInfo], suggested: set[int]
) -> int:
    """Store what GitHub listed. A repository already known keeps the person's choice. One that is
    no longer listed (deleted, or made private) is removed along with its entry, unless the person
    edited that entry."""
    existing = {r.repo_id: r for r in list_repos(db, owner_id)}
    listed = {r.id for r in repos}
    for repo in repos:
        row = existing.get(repo.id)
        if row is None:
            row = GitHubRepo(owner_user_id=owner_id, repo_id=repo.id)
            db.add(row)
        row.full_name = repo.full_name
        row.name = repo.name
        row.description = repo.description
        row.html_url = repo.html_url
        row.language = repo.language
        row.topics = list(repo.topics)
        row.stars = repo.stars
        row.fork = repo.fork
        row.archived = repo.archived
        row.created_remote = repo.created_at
        row.pushed_remote = repo.pushed_at
        row.suggested = repo.id in suggested
        row.seen_at = datetime.now(UTC)
    for repo_id, row in existing.items():
        if repo_id not in listed:
            _drop_entry(db, owner_id, repo_id)
            db.delete(row)
    db.flush()
    return len(repos)


def choose_repos(db: Session, owner_id: uuid.UUID, repo_ids: set[int]) -> bool:
    """Set which repositories are used as evidence. False when an id is not one of the person's."""
    rows = list_repos(db, owner_id)
    known = {r.repo_id for r in rows}
    if not repo_ids <= known:
        return False
    for row in rows:
        row.selected = row.repo_id in repo_ids
    db.flush()
    return True


def set_excerpt(db: Session, owner_id: uuid.UUID, repo_id: int, excerpt: str) -> None:
    db.execute(
        update(GitHubRepo)
        .where(GitHubRepo.owner_user_id == owner_id, GitHubRepo.repo_id == repo_id)
        .values(readme_excerpt=excerpt[:800])
    )


# ---------------------------------------------------------------- repositories as evidence


def _entry_for(db: Session, owner_id: uuid.UUID, repo_id: int) -> ProfileEntry | None:
    return db.execute(
        select(ProfileEntry).where(
            ProfileEntry.owner_user_id == owner_id,
            ProfileEntry.source == SOURCE,
            ProfileEntry.source_key == source_key(repo_id),
        )
    ).scalar_one_or_none()


def _drop_entry(db: Session, owner_id: uuid.UUID, repo_id: int) -> None:
    """Remove the entry a repository made. An entry the person edited is kept and becomes theirs."""
    entry = _entry_for(db, owner_id, repo_id)
    if entry is None:
        return
    if entry.user_edited:
        entry.source = "user"
        entry.source_key = None
    else:
        db.delete(entry)


def apply_entries(
    db: Session, owner_id: uuid.UUID, projects: dict[int, dict[str, Any]]
) -> tuple[int, int, int]:
    """Make the profile match the chosen repositories. `projects` maps a repository id to the data
    of its project entry. Returns (added, updated, removed).

    A new entry is added. An entry the person has not touched is refreshed. An entry the person
    edited is left exactly as it is. An entry whose repository is no longer chosen is removed, or
    handed to the person when they had edited it."""
    added = updated = removed = 0
    position = (
        db.execute(
            select(ProfileEntry.position)
            .where(ProfileEntry.owner_user_id == owner_id)
            .order_by(ProfileEntry.position.desc())
            .limit(1)
        ).scalar_one_or_none()
        or 0
    )
    for repo_id, data in projects.items():
        entry = _entry_for(db, owner_id, repo_id)
        if entry is None:
            position += 1
            db.add(
                ProfileEntry(
                    owner_user_id=owner_id,
                    entry_type="project",
                    data=data,
                    user_edited=False,
                    source=SOURCE,
                    source_key=source_key(repo_id),
                    position=position,
                )
            )
            added += 1
        elif not entry.user_edited and entry.data != data:
            entry.data = data
            updated += 1
    chosen_keys = {source_key(i) for i in projects}
    stale = db.execute(
        select(ProfileEntry).where(
            ProfileEntry.owner_user_id == owner_id, ProfileEntry.source == SOURCE
        )
    ).scalars()
    for entry in list(stale):
        if entry.source_key not in chosen_keys:
            if entry.user_edited:
                entry.source = "user"
                entry.source_key = None
            else:
                db.delete(entry)
                removed += 1
    db.flush()
    sync_evidence(db, owner_id)
    return added, updated, removed


def remove_connection(db: Session, owner_id: uuid.UUID, *, keep_entries: bool) -> int:
    """Disconnect: delete the token, the sign-ins and the repository list. Entries made from
    repositories are removed unless asked to keep them (an entry the person edited is always kept
    and becomes theirs). Returns how many entries were removed."""
    removed = 0
    for entry in list(
        db.execute(
            select(ProfileEntry).where(
                ProfileEntry.owner_user_id == owner_id, ProfileEntry.source == SOURCE
            )
        ).scalars()
    ):
        if keep_entries or entry.user_edited:
            entry.source = "user"
            entry.source_key = None
        else:
            db.delete(entry)
            removed += 1
    db.execute(delete(GitHubRepo).where(GitHubRepo.owner_user_id == owner_id))
    purge_states(db, owner_id)
    db.execute(delete(GitHubConnection).where(GitHubConnection.owner_user_id == owner_id))
    db.flush()
    sync_evidence(db, owner_id)
    return removed


def save_connection_safe(
    db: Session, *, owner_id: uuid.UUID, github_user_id: int, login: str, token_sealed: str
) -> GitHubConnection | None:
    """Like save_connection but tolerant of two sign-ins finishing at once."""
    try:
        with db.begin_nested():
            return save_connection(
                db,
                owner_id=owner_id,
                github_user_id=github_user_id,
                login=login,
                token_sealed=token_sealed,
            )
    except IntegrityError:
        return get_connection(db, owner_id)
