# Runbook: security incident

For a suspected or confirmed breach: someone got in, data leaked, a secret leaked, or the service is being attacked. Stay calm, write down times as you go, and follow the order: contain, assess, recover, tell, learn.

## Detection
Health alerts (failed sign-ins, wrong origin, server errors), a report from a person, a leaked key found by the secret scanner or in a public place, an unexpected admin action in the audit log, or a provider telling you.

## Diagnosis
1. What do you know and when did it start? Write it down.
2. Audit log (Admin, Audit log): admin actions, `auth.login_failed`, `origin_rejected`, `csrf_rejected`, `account.exported`, `account.deletion_requested` around the time.
3. Health: queue, failures, spend (a spike in model cost can mean a stolen key or abuse).
4. Logs: `... logs --since 24h api` for the request id and paths. Logs hold no passwords, no resume text and no tokens.
5. Scope: which accounts, which data, which secrets could be involved?

## Mitigation (contain first)
- A person's account: Admin, Users, disable it and revoke sessions.
- Every session: `docker compose -f compose.prod.yaml --env-file .env.production exec api python -m pv_api.cli revoke-all-sessions`. Everyone signs in again. (Rotating `SECRET_KEY` alone does not do this: sessions are database rows.)
- A leaked key: rotate it now (model key, mail password, database passwords, GitHub secret, token keys). Runbook "secret rotation".
- Abuse of sign-up: set `SIGNUP_MODE=invite`, revoke open invites, lower the rate limits.
- Attack on the service: stop the proxy (`... stop proxy`) to cut traffic while you work.
- An expensive feature being abused: lower the plan limit for it (a data change) or set the daily spend ceiling.

## Recovery
1. Remove the cause: close the hole, rotate what was exposed, remove access that should not exist.
2. Check nothing was left behind: admin list, invites, the audit log after the time of entry, scheduled tasks.
3. Restore from a backup only if data was altered or destroyed (runbook "backup restore").
4. Bring the service back, run `deploy/smoke.sh` and `check-config`.

## Tell people
- If personal data may have been seen or taken, tell the people affected, without delay, in plain words: what happened, what was involved, what you did, what they should do. Check what the law that applies to you requires, including whether a regulator must be told and by when (carryover C-156: decide this before launch with a lawyer).
- Do not guess or play it down. Say what you do not know yet.

## Learn
Within a week, write a short review: timeline, cause, what worked, what did not, what changes. Add a test or a check so it cannot happen the same way. File carryovers for what you could not fix at once.

## Prevention
Rate limits, forced Row Level Security, encrypted tokens, secret scanning in CI, dependency audits, the configuration check before each deploy, least-privilege database roles. The tabletop drill (docs/operations/incident-response.md) is repeated twice a year.
