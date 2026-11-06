# Runbook: database failure

## Detection
- Health shows "The database is not answering" (critical), `check-alerts` prints it, and `/readyz` returns not ready.
- People see "Something went wrong on our side" on every page that reads data.
- The worker log shows connection errors and tasks stop being claimed.

## Diagnosis
1. Is the container up? `docker compose -f compose.prod.yaml --env-file .env.production ps postgres`.
2. Read its log: `... logs --tail 100 postgres`. Look for "out of memory", "No space left on device", "could not write", "too many connections", or a crash recovery message.
3. Disk: `df -h` on the host, and the size of the `pgdata` volume. A full disk is the most common cause.
4. Connections: from the database, `select count(*) from pg_stat_activity;` against the limit.

## Mitigation
- The container stopped: `... up -d postgres`. It recovers from its own log on start. Wait for it to be healthy before anything else.
- Disk full: free space first (old backups in `./backups`, old Docker images: `docker image prune`, logs). Do not delete anything inside the `pgdata` volume.
- Too many connections: restart the API and worker (`... restart api worker`), then look for what leaks connections.
- Out of memory: raise the memory limit of `postgres` in `compose.prod.yaml` and redeploy.

## Recovery
1. When the database is healthy, `/readyz` turns ready by itself. The API and worker reconnect without a restart.
2. Tasks that were running when it stopped come back after their lease ends (about 2 minutes). Nothing is lost: a task is claimed again.
3. Check Health: no dead letters that came from the outage, queue draining.
4. If the data volume is damaged and the database will not start, that is a restore: runbook "backup restore".

## Prevention
- Alert on disk use before it is full (carryover C-147).
- Take a backup before every deploy (the deploy script does) and copy backups off the machine.
- Run `deploy/restore.sh <backup> --drill` on a schedule so the restore path is known to work.
