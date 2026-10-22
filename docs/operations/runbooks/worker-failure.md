# Runbook: Worker failure

Use when emails are not arriving, queued work is not moving, or the admin System screen shows no workers.

## Detection
- Admin, System: "No worker has reported in", or every worker shows Stale.
- `.\scripts\pv.ps1 status` shows the worker container as `unhealthy`, `restarting` or missing.
- Oldest waiting task keeps growing and the queued count does not fall.
- Users report that verification or reset email never arrives.

## Diagnosis
1. `.\scripts\pv.ps1 status` : is the `worker` container running and healthy?
2. `.\scripts\pv.ps1 logs worker` : look for `worker_database_error` (database trouble), `heartbeat_failed`, a Python traceback at start, or no lines at all.
3. `.\scripts\pv.ps1 queue` : are heartbeats recent? Are tasks `running` with an old `updated_at`?
4. If the worker restarts in a loop, the first traceback is the cause (usually a bad setting: `WORKER_LEASE_SECONDS` must exceed `WORKER_HEARTBEAT_SECONDS`).
5. If the database is the problem, see `docker compose logs postgres` (the Database failure runbook arrives in 3.7).

## Mitigation
- Restart: `.\scripts\pv.ps1 restart worker`.
- Add capacity if work is only slow: `docker compose up -d --scale worker=2`.
- Nothing is lost while the worker is down: tasks stay queued and a task claimed by a crashed worker becomes claimable again after `WORKER_LEASE_SECONDS`.

## Recovery
1. Confirm a heartbeat appears (Admin, System) within about 10 seconds of the restart.
2. Watch the queued count fall. Tasks run in order of when they became due.
3. Check dead letters (see the Dead-letter task runbook). Email tasks that dead-lettered cannot be requeued: ask the affected users to request a new link.
4. If the mail provider was the cause, confirm with a test: request a password reset for your own account and watch Mailpit (`.\scripts\pv.ps1 inbox`) or your provider.

## Prevention
- Keep the worker healthcheck enabled (it fails when the heartbeat file is older than one minute).
- Do not set `WORKER_LEASE_SECONDS` shorter than your slowest handler unless it calls `extend_lease`.
- Alert on oldest waiting task age and on zero workers (checkpoint 3.5).
