#!/usr/bin/env bash
# Shared by the deploy scripts. Source it, do not run it.
set -euo pipefail
# Git Bash on Windows rewrites paths that start with a slash. Turn that off for docker commands.
export MSYS_NO_PATHCONV=1

cd "$(dirname "${BASH_SOURCE[0]}")/.."
ENV_FILE="${ENV_FILE:-.env.production}"
COMPOSE_FILE="${COMPOSE_FILE:-compose.prod.yaml}"
COMPOSE="docker compose -f ${COMPOSE_FILE} --env-file ${ENV_FILE}"
BACKUP_DIR="${BACKUP_DIR:-./backups}"
BACKUP_KEEP_DAYS="${BACKUP_KEEP_DAYS:-30}"
FILES_VOLUME="${FILES_VOLUME:-provenance-prod_files}"

say() { printf '%s\n' "$*"; }
fail() { printf 'FAILED: %s\n' "$*" >&2; exit 1; }
need_env_file() { [ -f "${ENV_FILE}" ] || fail "${ENV_FILE} not found. Copy .env.production.example and fill it in."; }

# Read one value from the env file without sourcing it (values may contain spaces or symbols).
env_value() { grep -E "^$1=" "${ENV_FILE}" | head -1 | cut -d= -f2- ; }
