# Runbook: backup restore

Two different needs, two different commands. Do not mix them up.

- **Prove the backups work** (do this on a schedule): `deploy/restore.sh <backup folder> --drill`. It restores into a scratch database next to the live one, checks it, and drops it. Nothing live is touched.
- **Recover from a disaster**: `deploy/restore.sh <backup folder> --replace-live-data`. It replaces the live database and files. Everything written after the backup is lost.

## Detection
For a disaster: the database volume is lost or damaged, the machine is gone, data was deleted or corrupted by mistake or by a bad deploy, or a ransomware event.

## Diagnosis
1. What is the newest backup, and how old is it? `ls -1 backups/` and `cat backups/<folder>/manifest.json` (time, migration, sizes).
2. Is it intact? `cd backups/<folder> && sha256sum -c SHA256SUMS`.
3. How much would be lost? Everything between the backup time and now (the RPO, see disaster recovery).
4. Is a point before the damage needed rather than the newest? Choose an older folder.

## Mitigation
- Stop anything that could write more damage: `... stop proxy` (people see the proxy is down rather than losing more work).
- Copy the damaged data aside if you can (`docker run --rm -v provenance-prod_pgdata:/d -v $PWD:/o alpine tar czf /o/damaged-pgdata.tgz /d`) so nothing is lost for good.

## Recovery
1. On the same machine: `deploy/restore.sh backups/<folder> --replace-live-data`.
2. On a new machine: install Docker, copy the repository checkout, `.env.production` and the backup folder over, then `... up -d postgres`, wait healthy, and run the same command. The database role and extension come from the init script on first start. The same `TOKEN_ENCRYPTION_KEYS` (and `SECRET_KEY`, for any token still sealed the old way) are required: without them GitHub tokens cannot be opened and people reconnect. Sessions are in the database, so they come back with the restore.
3. Run `deploy/deploy.sh` (it migrates forward if the backup is older than the code), then `deploy/smoke.sh`.
4. Tell people what period of work was lost.
5. Repeat any account deletions that happened after the backup (runbook "data deletion request").

## Prevention
- Run the drill monthly and after any change to backups. Record the time it took (disaster recovery doc).
- Copy backups to a second place (another machine or object storage). A backup only on the machine it protects is not a backup.
- Keep `.env.production` and the keys in a password manager. Losing `TOKEN_ENCRYPTION_KEYS` loses the GitHub tokens by design.
