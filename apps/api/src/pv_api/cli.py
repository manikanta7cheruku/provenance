"""Operator commands. Run with: python -m pv_api.cli <command>

  create-invite --email someone@example.com --days 7
  promote-admin --email someone@example.com

Invite codes are printed once and stored only as hashes.
"""

import argparse
import sys
from datetime import UTC, datetime, timedelta

from sqlalchemy import update
from sqlalchemy.orm import Session

from pv_config import get_settings
from pv_domain.auth import generate_token, hash_token, normalize_email
from pv_persistence.audit import record_audit
from pv_persistence.engine import create_db_engine
from pv_persistence.models import Invite, User


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pv_api.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    invite = sub.add_parser("create-invite", help="create a single-use signup invite code")
    invite.add_argument("--email", default=None, help="bind the invite to one email address")
    invite.add_argument("--days", type=int, default=7, help="days until the invite expires")
    promote = sub.add_parser("promote-admin", help="give an existing user the ADMIN role")
    promote.add_argument("--email", required=True)
    args = parser.parse_args(argv)

    engine = create_db_engine(get_settings().database_url.get_secret_value())
    if args.command == "create-invite":
        code = generate_token()
        email = normalize_email(args.email) if args.email else None
        with Session(engine) as db, db.begin():
            db.add(
                Invite(
                    code_hash=hash_token(code),
                    email=email,
                    expires_at=datetime.now(UTC) + timedelta(days=args.days),
                )
            )
        record_audit(
            engine,
            category="audit",
            action="admin.invite_created",
            metadata={"bound": email is not None},
        )
        print(f"Invite code (shown once): {code}")
        return 0

    email = normalize_email(args.email)
    with Session(engine) as db, db.begin():
        updated = db.execute(
            update(User).where(User.email == email).values(role="ADMIN").returning(User.id)
        ).first()
    if updated is None:
        print("No user with that email.", file=sys.stderr)
        return 1
    record_audit(
        engine,
        category="audit",
        action="admin.role_granted",
        target_type="user",
        target_id=str(updated[0]),
    )
    print("Role updated to ADMIN.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
