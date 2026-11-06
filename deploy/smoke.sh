#!/usr/bin/env bash
# After a deploy or a restore: does the running system answer, and does it carry its protections?
#
#   deploy/smoke.sh https://app.example.com
#   SMOKE_INSECURE=1 deploy/smoke.sh https://localhost:8443      (a local self-signed certificate)
#
# Exit code 0 when every check passes. It sends no credentials and changes nothing.
set -uo pipefail
base="${1:?usage: smoke.sh https://your.domain}"
base="${base%/}"
curl_opts=(-sS --max-time 15)
[ "${SMOKE_INSECURE:-}" = "1" ] && curl_opts+=(-k)

pass=0; failed=0
ok() { printf '  ok    %s\n' "$1"; pass=$((pass + 1)); }
bad() { printf '  FAIL  %s\n' "$1"; failed=$((failed + 1)); }
check() { if eval "$2"; then ok "$1"; else bad "$1"; fi; }

# Neither helper pipes curl into grep -q (which closes the pipe early and makes curl fail) and neither
# writes to /dev/null (which some curl builds on Windows cannot do). Output is captured first.
status() { local out; out=$(curl "${curl_opts[@]}" -w '%{http_code}' "$@" 2>/dev/null || true); printf '%s' "${out: -3}"; }
headers() { local tmp out; tmp=$(mktemp); out=$(curl "${curl_opts[@]}" -D - -o "$tmp" "$@" 2>/dev/null || true); rm -f "$tmp"; printf '%s' "$out" | tr -d '\r'; }

echo "Smoke test of ${base}"
check "the app is served" '[ "$(status "${base}/")" = "200" ]'
check "liveness answers" '[ "$(status "${base}/healthz")" = "200" ]'
ready=$(curl "${curl_opts[@]}" "${base}/readyz" || true)
check "readiness says ready (database, migrations)" 'echo "$ready" | grep -q "\"ready\":true"'
check "the status route answers" '[ "$(status "${base}/api/v1/status")" = "200" ]'
check "a protected route needs a session" '[ "$(status "${base}/api/v1/profile/entries")" = "401" ]'
check "the admin area is not reachable without a session" '[ "$(status "${base}/api/v1/admin/health")" = "401" ] || [ "$(status "${base}/api/v1/admin/health")" = "404" ]'
check "the interactive API documentation is off" '[ "$(status "${base}/api/docs")" != "200" ] && [ "$(status "${base}/api/openapi.json")" != "200" ]'
check "the legal pages are public" '[ "$(status "${base}/privacy")" = "200" ] && [ "$(status "${base}/terms")" = "200" ]'

page=$(headers "${base}/")
check "pages carry a content security policy" 'echo "$page" | grep -qi "^content-security-policy:.*default-src .self."'
check "pages cannot be framed" 'echo "$page" | grep -qi "^x-frame-options: deny"'
check "pages are not sniffed" 'echo "$page" | grep -qi "^x-content-type-options: nosniff"'
check "TLS is enforced with HSTS" 'echo "$page" | grep -qi "^strict-transport-security: max-age=31536000"'
api=$(headers "${base}/api/v1/status")
check "the API sends its own protections" 'echo "$api" | grep -qi "^content-security-policy: default-src .none."'
check "API answers are not cached" 'echo "$api" | grep -qi "^cache-control: no-store"'
check "the server does not announce itself" '! echo "$page" | grep -qiE "^server: (nginx|uvicorn|caddy)/"'

if [[ "${base}" == https://* ]]; then
  plain="http://${base#https://}"
  [ "${SMOKE_INSECURE:-}" = "1" ] || check "plain http is sent to https" 'code=$(status "$plain/"); [ "$code" = "308" ] || [ "$code" = "301" ] || [ "$code" = "302" ]'
fi

echo
echo "${pass} passed, ${failed} failed."
[ "${failed}" -eq 0 ]
