"""Operator commands. Run with: python -m pv_api.cli <command>

  create-invite --email someone@example.com --days 7
  promote-admin --email someone@example.com
  seed-demo-run --email someone@example.com
  set-plan --email someone@example.com --plan pro
  show-plan --email someone@example.com
  check-alerts

Invite codes are printed once and stored only as hashes.
seed-demo-run creates one finished demo run with three steps for that user, so the Runs
screen can be tried before real workflows exist (checkpoint 1.5 onward).
"""

import argparse
import sys
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from pv_config import get_settings
from pv_domain.auth import generate_token, hash_token, normalize_email
from pv_domain.entitlements import UNITS, period_start
from pv_domain.states import RunState, StepState
from pv_persistence.audit import record_audit
from pv_persistence.engine import create_db_engine
from pv_persistence.entitlements import (
    assign_plan,
    get_plan,
    list_plans,
    plan_of,
    used_by_unit,
)
from pv_persistence.models import Invite, User
from pv_persistence.runs import add_step, create_run, set_run_state
from pv_persistence.tenancy import tenant_session


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pv_api.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    invite = sub.add_parser("create-invite", help="create a single-use signup invite code")
    invite.add_argument("--email", default=None, help="bind the invite to one email address")
    invite.add_argument("--days", type=int, default=7, help="days until the invite expires")
    promote = sub.add_parser("promote-admin", help="give an existing user the ADMIN role")
    promote.add_argument("--email", required=True)
    demo = sub.add_parser("seed-demo-run", help="create one finished demo run for a user")
    demo.add_argument("--email", required=True)
    sub.add_parser(
        "check-alerts",
        help="print what needs attention now. Exit code 1 when anything is critical",
    )
    setplan = sub.add_parser("set-plan", help="put a person on a plan (free, starter or pro)")
    setplan.add_argument("--email", required=True)
    setplan.add_argument("--plan", required=True)
    showplan = sub.add_parser(
        "show-plan", help="show a person's plan and what they used this month"
    )
    showplan.add_argument("--email", required=True)
    args = parser.parse_args(argv)

    engine = create_db_engine(get_settings().database_url.get_secret_value())
    if args.command == "check-alerts":
        from pv_api.services.observability_service import build_snapshot, thresholds_for
        from pv_domain.alerts import CRITICAL, evaluate

        # Request timings live in the API process, so they are not measured from here.
        found = evaluate(build_snapshot(engine, None), thresholds_for(get_settings()))
        if not found:
            print("Nothing needs attention. (Request timings are not measured by this command.)")
            return 0
        for alert in found:
            print(f"[{alert.severity.upper()}] {alert.title}")
            print(f"    {alert.detail}")
            print(f"    Do: {alert.action}")
        return 1 if any(a.severity == CRITICAL for a in found) else 0
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
    if args.command in ("set-plan", "show-plan"):
        with Session(engine) as db:
            user_id = db.execute(select(User.id).where(User.email == email)).scalar_one_or_none()
        if user_id is None:
            print("No user with that email.", file=sys.stderr)
            return 1
        settings = get_settings()
        with tenant_session(engine, user_id) as tdb:
            if args.command == "set-plan":
                if get_plan(tdb, args.plan) is None:
                    names = ", ".join(p.id for p in list_plans(tdb))
                    print(f"No such plan. Choose one of: {names}.", file=sys.stderr)
                    return 1
                assign_plan(tdb, user_id, args.plan, "operator")
                print(f"{email} is now on the {args.plan} plan.")
            else:
                now = datetime.now(UTC)
                plan = plan_of(tdb, user_id, settings.default_plan)
                used = used_by_unit(tdb, user_id, period_start(now))
                print(f"{email} is on the {plan.label} plan. Usage since {period_start(now)}:")
                for unit in UNITS:
                    limit = plan.units.get(unit)
                    print(f"  {unit}: {used[unit]} of {'no limit' if limit is None else limit}")
        if args.command == "set-plan":
            record_audit(
                engine,
                category="audit",
                action="admin.plan_set",
                target_type="user",
                target_id=str(user_id),
                metadata={"plan": args.plan},
            )
        return 0

    if args.command == "seed-demo-run":
        with Session(engine) as db:
            user_id = db.execute(select(User.id).where(User.email == email)).scalar_one_or_none()
        if user_id is None:
            print("No user with that email.", file=sys.stderr)
            return 1
        with tenant_session(engine, user_id) as tdb:
            run = create_run(tdb, owner_user_id=user_id, workflow_type="demo")
            set_run_state(tdb, run.id, RunState.RUNNING)
            for ordinal, (name, ms) in enumerate(
                [("Read input", 120), ("Check evidence", 840), ("Write result", 60)], start=1
            ):
                add_step(
                    tdb,
                    run_id=run.id,
                    owner_user_id=user_id,
                    step_name=name,
                    ordinal=ordinal,
                    state=StepState.SUCCEEDED,
                    duration_ms=ms,
                )
            set_run_state(tdb, run.id, RunState.SUCCEEDED)
        print(f"Demo run created for {email}.")
        return 0

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
