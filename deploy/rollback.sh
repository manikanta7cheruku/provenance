#!/usr/bin/env bash
# Go back to the previous version of the code. The data is NOT rolled back: migrations are written
# to be compatible with the version before, so the previous code runs on the current data.
#
#   deploy/rollback.sh              to the version before the current one
#   deploy/rollback.sh 9f2c1ab04d   to that commit (its images must still exist: docker images)
#
# To go back to an earlier state of the DATA, that is a restore, not a rollback (deploy/restore.sh).
source "$(dirname "$0")/common.sh"
need_env_file

target="${1:-$(cat deploy/.previous 2>/dev/null || true)}"
[ -n "${target}" ] || fail "there is no previous version recorded. Name a commit: deploy/rollback.sh <commit>"
docker image inspect "provenance-api:${target}" >/dev/null 2>&1 || fail "the image provenance-api:${target} is not on this machine"
docker image inspect "provenance-web:${target}" >/dev/null 2>&1 || fail "the image provenance-web:${target} is not on this machine"

export IMAGE_TAG="${target}"
say "Rolling back to ${target}..."
${COMPOSE} up -d --no-build --remove-orphans api worker web proxy
echo "${target}" > deploy/.current
say "Running ${target}. Run deploy/smoke.sh to check it."
