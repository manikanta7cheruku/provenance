"""Operator commands for the queue. Run with: python -m pv_worker.cli <command>

enqueue-demo --seconds 30    add a harmless task (used for the crash-recovery lab)
reindex-evidence             queue an embedding task for every active user (after adding an AI key,
                             changing the embedding model, or enabling evidence search)
"""

import argparse
import json
import sys
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from pv_config import get_settings
from pv_domain.tasks import TASK_DEMO
from pv_persistence.engine import create_db_engine
from pv_persistence.evidence import enqueue_embedding
from pv_persistence.models import User
from pv_persistence.queue import enqueue


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pv_worker.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    demo = sub.add_parser("enqueue-demo", help="enqueue a demo task")
    demo.add_argument("--seconds", type=int, default=5, help="how long the task runs (0 to 600)")
    sub.add_parser("reindex-evidence", help="queue an embedding task for every active user")
    args = parser.parse_args(argv)

    if args.command == "reindex-evidence":
        return _reindex()
    if not 0 <= args.seconds <= 600:
        print("--seconds must be between 0 and 600", file=sys.stderr)
        return 1
    engine = create_db_engine(get_settings().database_url.get_secret_value())
    marker = uuid.uuid4().hex
    with Session(engine) as db, db.begin():
        task_id = enqueue(
            db,
            task_type=TASK_DEMO,
            idempotency_key=f"demo:{marker}",
            payload={"args": {"seconds": args.seconds, "marker": marker}},
            max_attempts=3,
        )
    print(json.dumps({"task_id": str(task_id), "marker": marker, "seconds": args.seconds}))
    return 0


def _reindex() -> int:
    """Queue one embedding task per active user. Each task rebuilds the chunks and embeds what is
    missing, so it is safe to run as often as you like."""
    engine = create_db_engine(get_settings().database_url.get_secret_value())
    queued = 0
    with Session(engine) as db, db.begin():
        for user_id in db.execute(select(User.id).where(User.is_active.is_(True))).scalars():
            queued += int(enqueue_embedding(db, user_id))
    print(json.dumps({"queued": queued}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
