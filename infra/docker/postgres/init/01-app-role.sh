#!/bin/bash
# Runs ONCE, when the data volume is first created (not on every start).
# To re-run it: docker compose down -v   (this deletes the database)
set -e

: "${APP_DB_PASSWORD:?APP_DB_PASSWORD must be set}"

psql -v ON_ERROR_STOP=1 \
  --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -v app_password="$APP_DB_PASSWORD" -v dbname="$POSTGRES_DB" <<'EOSQL'
CREATE ROLE provenance_app
  LOGIN PASSWORD :'app_password'
  NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS NOREPLICATION;
GRANT CONNECT ON DATABASE :"dbname" TO provenance_app;
EOSQL
