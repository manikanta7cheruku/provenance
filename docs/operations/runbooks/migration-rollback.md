# Runbook: database migration rollback

Migrations are written to be compatible with the version of the code before them (expand, migrate, contract). That is what makes a code rollback safe: the previous code runs on the migrated data.

## Detection
- The migration step of the deploy failed, or Health says "The database is behind the code" or "does not match".
- After a deploy, errors mention a missing column or table, or a constraint.

## Diagnosis
1. Which version is the database at? `... exec -T postgres psql -U provenance -d provenance -tA -c "select version_num from alembic_version"`.
2. Which version does the code expect? `git log -1 -- packages/persistence/src/pv_persistence/migrations/versions` and the newest file there.
3. Did the migration run in one transaction? Each migration here is a literal script. If it failed half way, Postgres rolled back the whole of it (DDL is transactional), so the database is at the previous version.

## Mitigation
- The migration FAILED: nothing changed. Fix the migration, or `deploy/rollback.sh` to put the previous code back (the deploy script already does this on a failed step). The data is untouched.
- The migration SUCCEEDED but the new code is bad: `deploy/rollback.sh`. The old code runs on the new schema because the migration only added things. Do not run a downgrade.

## Recovery
- Only if a migration was destructive or wrong and rollback of code is not enough: a downgrade (`alembic downgrade -1`) is possible for every migration here, but it drops what the migration added, including any data written to it. Prefer a restore to before the deploy if data in the new tables matters (runbook: backup restore).
- After any of this, run `deploy/smoke.sh` and `check-config`.

## Prevention
- A migration that removes or renames something is split into two releases: first stop using it, then remove it.
- Every deploy takes a backup first. The deploy script refuses to continue if the backup fails.
- Test the migration on a copy of real data (restore a backup into a scratch database, then migrate it).
