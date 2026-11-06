#!/usr/bin/env bash
# Restore a backup. Two modes.
#
#   deploy/restore.sh <backup folder> --drill
#       Restore into a scratch database next to the live one, check it, and drop it. Nothing live is
#       touched. This is the drill: run it on a schedule and time it (docs/operations/disaster-recovery.md).
#
#   deploy/restore.sh <backup folder> --replace-live-data
#       Stop the application, REPLACE the live database and the stored files with the backup, start the
#       application again. Everything written since the backup is lost. Use it for a disaster, after
#       reading the runbook "backup restore".
source "$(dirname "$0")/common.sh"
need_env_file

dir="${1:-}"; mode="${2:-}"
[ -d "${dir}" ] || fail "usage: restore.sh <backup folder> --drill | --replace-live-data"
[ "${mode}" = "--drill" ] || [ "${mode}" = "--replace-live-data" ] || fail "say --drill or --replace-live-data"

say "Checking the backup is intact..."
(cd "${dir}" && sha256sum -c SHA256SUMS) || fail "a checksum does not match: this backup is damaged"

started=$(date +%s)
db_container=$(${COMPOSE} ps -q postgres)
[ -n "${db_container}" ] || fail "the database container is not running"

if [ "${mode}" = "--drill" ]; then
  scratch="restore_drill_$(date +%s)"
  say "Restoring into a scratch database (${scratch})..."
  ${COMPOSE} exec -T postgres sh -c "psql -U \"\$POSTGRES_USER\" -d postgres -v ON_ERROR_STOP=1 -c 'CREATE DATABASE ${scratch}'"
  docker cp "${dir}/db.dump" "${db_container}:/tmp/drill.dump"
  # --no-owner is not used: owners and privileges are part of what is being proven.
  ${COMPOSE} exec -T postgres sh -c "pg_restore -U \"\$POSTGRES_USER\" -d ${scratch} --exit-on-error /tmp/drill.dump"
  restore_seconds=$(( $(date +%s) - started ))

  q() { ${COMPOSE} exec -T postgres sh -c "psql -U \"\$POSTGRES_USER\" -d ${scratch} -tA -c \"$1\"" | tr -d '\r\n '; }
  migration=$(q "select version_num from alembic_version")
  users=$(q "select count(*) from users")
  tables=$(q "select count(*) from information_schema.tables where table_schema='public'")
  unsafe=$(q "select count(*) from pg_class c join pg_namespace n on n.oid=c.relnamespace where n.nspname='public' and c.relkind='r' and c.relname <> 'tasks' and exists (select 1 from information_schema.columns k where k.table_schema='public' and k.table_name=c.relname and k.column_name='owner_user_id') and not (c.relrowsecurity and c.relforcerowsecurity)")
  app_can_read=$(q "select has_table_privilege('provenance_app','users','SELECT')")
  extension=$(q "select count(*) from pg_extension where extname='vector'")
  want=$(grep -o '"migration": "[^"]*"' "${dir}/manifest.json" | cut -d'"' -f4)

  say "Restored in ${restore_seconds} seconds."
  say "  migration:            ${migration} (the backup says ${want})"
  say "  users:                ${users}"
  say "  tables:               ${tables}"
  say "  without forced RLS:   ${unsafe}"
  say "  app role can read:    ${app_can_read}"
  say "  vector extension:     ${extension}"

  ${COMPOSE} exec -T postgres sh -c "psql -U \"\$POSTGRES_USER\" -d postgres -c 'DROP DATABASE ${scratch}'" >/dev/null
  ${COMPOSE} exec -T postgres sh -c "rm -f /tmp/drill.dump"

  # The files: unpack into a throwaway folder and count.
  files=$(tar tzf "${dir}/files.tar.gz" | grep -vc '/$' || true)
  say "  stored files in the backup: ${files}"

  [ "${migration}" = "${want}" ] || fail "the restored database is at a different migration than the backup"
  [ "${unsafe}" = "0" ] || fail "the restored database has tables without forced Row Level Security"
  [ "${app_can_read}" = "t" ] || fail "the application role lost its privileges in the restore"
  [ "${extension}" = "1" ] || fail "the vector extension is missing after the restore"
  say "DRILL PASSED in $(( $(date +%s) - started )) seconds."
  exit 0
fi

# ---- replace live data
say "Stopping the application (the database stays up)..."
${COMPOSE} stop proxy web worker api
say "Replacing the database..."
docker cp "${dir}/db.dump" "${db_container}:/tmp/restore.dump"
${COMPOSE} exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d postgres -v ON_ERROR_STOP=1 -c "DROP DATABASE IF EXISTS \"$POSTGRES_DB\" WITH (FORCE)" -c "CREATE DATABASE \"$POSTGRES_DB\""'
${COMPOSE} exec -T postgres sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --exit-on-error /tmp/restore.dump && rm -f /tmp/restore.dump'
say "Replacing the stored files..."
docker run --rm -v "${FILES_VOLUME}:/data/files" -v "$(cd "${dir}" && pwd):/in:ro" alpine:3.20 \
  sh -c 'find /data/files -mindepth 1 -delete && tar xzf /in/files.tar.gz -C /data/files && chown -R 10001:10001 /data/files'
say "Starting the application..."
${COMPOSE} up -d
say "Restored from ${dir} in $(( $(date +%s) - started )) seconds. Run deploy/smoke.sh next."
