# Disaster recovery

Status: Proposed targets, measured on a laptop. The owner confirms the targets before launch (carryover C-157).

## What can be lost and what it takes to get back

| Loss | How it is recovered | What is lost |
|---|---|---|
| A container crashes | Restart policy, seconds | Nothing |
| The API or worker image is bad | `deploy/rollback.sh`, about 20 seconds | Nothing (migrations are compatible with the version before) |
| The database is damaged or data is wrongly changed | `deploy/restore.sh <backup> --replace-live-data` | Everything since the backup |
| The machine is lost | New machine, copy of the checkout, `.env.production` and the newest backup, then the same restore | Everything since the backup, plus the time to get a machine |
| The backups are lost with the machine | Nothing to restore | Everything. Backups must be copied off the machine |

## Targets (proposed)

| | Proposed | Why |
|---|---|---|
| RPO, how much work may be lost | 24 hours | A person re-enters a day of edits and notes. Backups run nightly. A tighter RPO needs point-in-time recovery, which a managed database offers (carryover C-159) |
| RTO, how long until it is back | 4 hours | Time to get a machine, copy the backup and restore. The restore itself is minutes |

## Measured (laptop, production images)

| Step | Time |
|---|---|
| Backup of a 10 MB database and 6 files | 4 seconds |
| Restore into a scratch database and check it | 10 seconds |
| Replace live data on the production stack and restart | 20 seconds |
| Deploy of a new version | about 30 seconds |
| Rollback to the previous version | about 16 seconds |

These grow with the data. At 100 times the data the restore is minutes, still far inside the target. The slow part of a real disaster is getting a machine and the backup to it, not the restore.

## What a backup holds
A compressed dump of the database (every table, owners and privileges, the vector extension is recreated by the init script) and an archive of the stored files, with a checksum for each and a manifest (time, migration, sizes). It does not hold `.env.production`. Keep that, and the keys in it, in a password manager. Losing `TOKEN_ENCRYPTION_KEYS` loses the GitHub tokens by design: people reconnect.

## Retention
30 days (`BACKUP_KEEP_DAYS`). Job listings fetched from sources and closed for more than `CLOSED_JOB_RETENTION_DAYS` (90) are deleted by the worker. The privacy policy tells people that deleted data can stay in a backup for up to 30 days. After a restore, repeat any account deletions made after the backup date (`account_deletions` shows them).

## Where backups go
`./backups` on the machine, and then somewhere else. Copying off the machine is not automated yet (carryover C-160): until it is, a lost machine loses the backups too. Nothing here should be called disaster recovery until that is done.

## Rehearsal
`deploy/restore.sh <backup> --drill` monthly and after any change to backups or to the database image. Record the time here.
