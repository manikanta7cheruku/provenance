#!/usr/bin/env bash
# Deploy the commit that is checked out (or the one named), safely.
#
#   deploy/deploy.sh                 deploy HEAD
#   deploy/deploy.sh 9f2c1ab04d      deploy that commit (check it out first: the images are built from the files here)
#
# The steps, in order, and what happens when one fails:
#   1. build the images, tagged with the commit
#   2. start the database, take a backup
#   3. run the migrations (a separate step, as the owner role)
#   4. check the configuration is safe        a FAIL stops here, nothing new is running
#   5. start the new version and wait until it reports ready
#   6. smoke test it from outside              a failure rolls back to the previous version
# Migrations are written to work with the previous version of the code too (expand, migrate,
# contract), so rolling the code back never needs the data rolled back.
source "$(dirname "$0")/common.sh"
need_env_file

TAG="${1:-$(git rev-parse --short=10 HEAD)}"
PREVIOUS="$(cat deploy/.current 2>/dev/null || true)"
export IMAGE_TAG="${TAG}"
SITE="$(env_value PUBLIC_BASE_URL)"
[ -n "${SITE}" ] || fail "PUBLIC_BASE_URL is not set in ${ENV_FILE}"

say "Deploying ${TAG} (running now: ${PREVIOUS:-nothing})"

# When the new version is not good: go back to the previous one, or say plainly that there is none.
give_up() {
  if [ -n "${PREVIOUS}" ] && ./deploy/rollback.sh "${PREVIOUS}"; then
    fail "${TAG} was not good and ${PREVIOUS} is running again. Fix it and deploy again."
  fi
  fail "${TAG} was not good. This was the first deploy, so there is nothing to roll back to: ${TAG} is still running. Fix it and deploy again, or stop it with: ${COMPOSE} stop"
}

say "1/6 Building the images..."
${COMPOSE} build api web

say "2/6 Starting the database and taking a backup..."
${COMPOSE} up -d postgres
until ${COMPOSE} exec -T postgres sh -c 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"' >/dev/null 2>&1; do sleep 2; done
if ${COMPOSE} exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tA -c "select 1 from alembic_version"' >/dev/null 2>&1; then
  IMAGE_TAG="${PREVIOUS:-${TAG}}" ./deploy/backup.sh
else
  say "    (a new database: nothing to back up yet)"
fi

say "3/6 Running the migrations..."
${COMPOSE} run --rm migrate

say "4/6 Checking the configuration..."
${COMPOSE} run --rm --no-deps api python -m pv_api.cli check-config || fail "the configuration is not safe. Fix every FAIL above. Nothing new is running."

say "5/6 Starting ${TAG}..."
${COMPOSE} up -d --remove-orphans
deadline=$(( $(date +%s) + 180 ))
until ${COMPOSE} exec -T api python -c "import urllib.request,sys; sys.exit(0 if b'\"ready\":true' in urllib.request.urlopen('http://127.0.0.1:8000/readyz', timeout=3).read() else 1)" >/dev/null 2>&1; do
  if [ "$(date +%s)" -ge "${deadline}" ]; then
    say "The API did not become ready in 3 minutes."
    give_up
  fi
  sleep 3
done

say "6/6 Smoke test..."
if ! ./deploy/smoke.sh "${SITE}"; then
  say "The smoke test failed."
  give_up
fi

echo "${PREVIOUS}" > deploy/.previous
echo "${TAG}" > deploy/.current
say "Deployed ${TAG}. Rollback, if you need it: deploy/rollback.sh"
