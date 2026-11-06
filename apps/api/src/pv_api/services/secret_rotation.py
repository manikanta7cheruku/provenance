"""Finish a token key rotation: re-seal every stored connector token with the newest key.

Rotation (see pv_config.secretbox): put the new key first in TOKEN_ENCRYPTION_KEYS and keep the old
one behind it, restart, run this, then remove the old key. A token that cannot be opened (it was
sealed with a key that is gone, or it was changed) is counted and left alone. The person reconnects
when it is next needed; nothing is deleted here and no token is ever printed.

Tokens belong to people and Row Level Security hides them from everyone else, so each person is
visited in turn with their own tenant set. People are taken in batches of a few hundred per
transaction (the tenant is set again for each), so a large user table is not a large number of
transactions.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from pv_config import SecretBox, SecretBoxError, Settings
from pv_persistence.models import GitHubConnection, User
from pv_persistence.tenancy import set_tenant

BATCH = 300


@dataclass(frozen=True)
class ResealResult:
    resealed: int
    already_current: int
    unreadable: int


def reseal_github_tokens(engine: Engine, settings: Settings) -> ResealResult:
    box = SecretBox.for_settings(settings)
    with Session(engine) as db:
        user_ids: list[uuid.UUID] = list(db.execute(select(User.id)).scalars())
    resealed = current = unreadable = 0
    for start in range(0, len(user_ids), BATCH):
        with Session(engine, expire_on_commit=False) as db, db.begin():
            for user_id in user_ids[start : start + BATCH]:
                set_tenant(db, user_id)
                row = db.execute(
                    select(GitHubConnection).where(GitHubConnection.owner_user_id == user_id)
                ).scalar_one_or_none()
                if row is None:
                    continue
                if not box.needs_resealing(row.token_sealed):
                    current += 1
                    continue
                context = f"github-token:{user_id}"
                try:
                    plain = box.open(row.token_sealed, context=context)
                except SecretBoxError:
                    unreadable += 1
                    continue
                row.token_sealed = box.seal(plain, context=context)
                resealed += 1
    return ResealResult(resealed, current, unreadable)
