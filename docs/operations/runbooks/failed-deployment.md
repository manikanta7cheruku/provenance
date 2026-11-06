# Runbook: failed deployment

## Detection
`deploy/deploy.sh` stops with FAILED and a step number, or the smoke test fails after the new version started and the script rolled back. Health or the alerts show trouble within minutes of a deploy.

## Diagnosis
Read which step failed:
1. Build: an image would not build. The error is in the output. Nothing running changed.
2. Backup: the database could not be dumped. Nothing running changed. Fix this first, never deploy without a backup.
3. Migrate: the migration failed. The database is at the previous version (see "database migration rollback").
4. Check config: a FAIL names the setting. Nothing new is running.
5. Start: the API did not become ready in 3 minutes. The script rolled back. Read `... logs --tail 200 api migrate`.
6. Smoke test: the system started but a check failed. The script rolled back. The failing check is named.

## Mitigation
- The script rolls back by itself for steps 5 and 6. Confirm: `cat deploy/.current` is the previous commit and `deploy/smoke.sh https://your.domain` passes.
- If it did not roll back, or you want to go back later: `deploy/rollback.sh` (to the previous) or `deploy/rollback.sh <commit>`. The images must still be on the machine (`docker images | grep provenance`).

## Recovery
1. Reproduce on a laptop with the same commit and the production-like config (`.env.production.test`).
2. Fix, run the full tests, deploy again. Never edit files on the server.
3. If the data was damaged by the deploy, that is a restore (runbook "backup restore"), not a rollback.

## Prevention
- The `images` CI job builds the production images and validates the stack on every pull request.
- Deploy at a time when someone can watch it, not at the end of the day.
- Keep the last two images on the machine (do not prune the previous tag).
