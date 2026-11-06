#!/usr/bin/env bash
# Take a backup: the database (a compressed dump) and the stored files (resumes, pictures, PDFs),
# with a checksum for each and a small manifest, in a folder named for the time in UTC.
#
#   deploy/backup.sh                  into ./backups/<time>
#   BACKUP_DIR=/mnt/backups deploy/backup.sh
#
# Old backups are removed after BACKUP_KEEP_DAYS (default 30), which is also the longest a person's
# deleted data can survive in a backup (see the privacy policy). Copy the folder somewhere else too:
# a backup on the same machine does not survive losing the machine (runbook: backup restore).
source "$(dirname "$0")/common.sh"
need_env_file

started=$(date +%s)
stamp=$(date -u +%Y%m%dT%H%M%SZ)
out="${BACKUP_DIR}/${stamp}"
mkdir -p "${out}"

say "Backing up the database..."
${COMPOSE} exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom --compress=6' > "${out}/db.dump"
[ -s "${out}/db.dump" ] || fail "the database dump is empty"

say "Backing up the stored files..."
docker run --rm -v "${FILES_VOLUME}:/data/files:ro" -v "$(cd "${out}" && pwd):/out" alpine:3.20 \
  tar czf /out/files.tar.gz -C /data/files . || fail "could not read the files volume ${FILES_VOLUME}"

version=$(${COMPOSE} exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tA -c "select version_num from alembic_version"' | tr -d '\r\n ')
(cd "${out}" && sha256sum db.dump files.tar.gz > SHA256SUMS)
seconds=$(( $(date +%s) - started ))
cat > "${out}/manifest.json" <<JSON
{
  "taken_at": "${stamp}",
  "image_tag": "${IMAGE_TAG:-$(cat deploy/.current 2>/dev/null || echo unknown)}",
  "migration": "${version}",
  "db_bytes": $(wc -c < "${out}/db.dump"),
  "files_bytes": $(wc -c < "${out}/files.tar.gz"),
  "seconds": ${seconds}
}
JSON

say "Removing backups older than ${BACKUP_KEEP_DAYS} days..."
find "${BACKUP_DIR}" -mindepth 1 -maxdepth 1 -type d -mtime "+${BACKUP_KEEP_DAYS}" -exec rm -rf {} + 2>/dev/null || true

say "Backup written to ${out} in ${seconds} seconds (migration ${version})."
