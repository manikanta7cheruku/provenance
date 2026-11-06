# Failure drills

A drill is something broken on purpose, to see that the alert fires, the runbook works and the system recovers. These were run on 6 November 2026 on the production stack (`compose.prod.yaml`) on a laptop, with the production images, real TLS from the proxy, and a database that held test data. They prove the mechanisms work. They do not prove how the real host will behave (disk, network, load), which is why they are repeated on the real host before launch (carryover C-158).

| # | What was broken | What was seen | Recovery | Result |
|---|---|---|---|---|
| 1 | The worker stopped with a task waiting | After a minute `check-alerts` printed "[CRITICAL] No worker is running, 1 tasks are waiting" and exited 1 | `start worker`. The next check printed nothing needs attention and exited 0 | The alert fired with the action to take |
| 2 | The database stopped | `/readyz` answered 503, `/healthz` stayed 200 (the process is alive but not ready), the sign-in check answered | Started the database. `/readyz` was 200 again after 3 seconds with no restart of the API | The API reconnects by itself |
| 3 | The API container was killed with `docker kill` | It stayed down, because Docker treats `docker kill` as a manual stop and the restart policy does not apply | Found a gap in the drill, not the system: killing is not crashing | Rerun as drill 3b |
| 3b | The API process was killed from inside (a crash) | Back and ready in 4 seconds, restart count 1 | Automatic (`restart: unless-stopped`) | A crash heals itself |
| 4 | A deploy with a development mail host in the configuration | `check-config` printed "[FAIL] Mail" and the deploy stopped before anything new started | The previous version kept running (15 of 15 smoke checks) | The configuration gate stops a bad deploy |
| 5 | A second deploy, then a rollback | Deploy took 32 seconds, rollback 16, smoke passed on both | `deploy/rollback.sh` returned to the first version | Deploy and rollback work |
| 6 | The web container kept an old address for the API after a deploy | The site answered 502 until it restarted. The first deploy test caught it | The web container now looks the API address up again every few seconds (a fix, not a workaround) | A real defect found and fixed |
| 7 | Rotating `SECRET_KEY` | People stayed signed in: sessions are database rows, so the key does not sign anyone out | Added `revoke-all-sessions` and corrected the runbooks | A wrong belief found and fixed |
| 8 | Backup and restore drill of the development database (8,293 users of test data, 10 MB) | Backup 4 seconds. The drill restored into a scratch database in 5 seconds and checked it (migration, tables, forced Row Level Security, the application role, the vector extension): 10 seconds in all | Scratch database dropped | The backup is readable and complete |
| 9 | Restore that replaces live data on the production stack (2 users, then 1) | Two people were registered, a backup was taken after the first, then the live data was replaced from it: 1 person left, the proxy back, smoke 15 of 15, 20 seconds | The path a disaster would take | The real restore works |

## Not drilled yet
- Losing the machine and rebuilding on a new one from a copy of the backup (needs a second machine).
- A full disk, memory pressure and a slow network (need the real host).
- A leaked secret end to end with the real providers.
- A person-run tabletop with more than one person (docs/operations/incident-response.md).
These are listed in the carryover register (C-157, C-158).
