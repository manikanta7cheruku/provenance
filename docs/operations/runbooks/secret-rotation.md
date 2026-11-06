# Runbook: secret rotation

Rotate on a schedule (every 6 to 12 months), when someone who knew a secret leaves, and at once when one may have leaked. Change one secret at a time and check after each.

Where secrets live: `.env.production` on the server (never in git), and your password manager. Generate a new value with `openssl rand -base64 48`.

## SECRET_KEY (derives CSRF tokens and keys the hashes of network addresses)
Effect: CSRF tokens change (an open page fetches a new one by itself) and the hashes used by rate limits and audit records start fresh. Signed-in sessions are rows in the database, so rotating this key does NOT sign anyone out. To sign everyone out, run `... exec api python -m pv_api.cli revoke-all-sessions` (a drill showed the difference, see docs/operations/drills.md).
Before you rotate: connector tokens sealed the old way (version v1) are derived from this key and become unreadable when it changes. Run `reseal-tokens` first so every token uses `TOKEN_ENCRYPTION_KEYS` (production requires that key to be set).
1. `... exec api python -m pv_api.cli reseal-tokens` and confirm `unreadable 0`.
2. Replace the value in `.env.production`.
3. `deploy/deploy.sh` (or `... up -d api worker`).
4. Check: sign in, a GitHub sync, and `deploy/smoke.sh`.

## TOKEN_ENCRYPTION_KEYS (seals GitHub tokens)
Effect when done in this order: nothing is lost and nobody reconnects.
1. Put the NEW key first and keep the OLD one behind it, comma separated: `NEW,OLD`.
2. Deploy. New tokens are sealed with the new key; old ones still open.
3. Run `docker compose -f compose.prod.yaml --env-file .env.production exec api python -m pv_api.cli reseal-tokens`. It prints how many were re-sealed and how many could not be read.
4. When it reports `unreadable 0`, remove the OLD key from the list and deploy again.
If a key is lost with no copy, the tokens sealed with it cannot be opened. People reconnect GitHub. Nothing else is affected.

## Database passwords (POSTGRES_PASSWORD, APP_DB_PASSWORD)
1. In the database: `ALTER ROLE provenance_app PASSWORD '<new>';` (and the owner role the same way) using `docker compose ... exec postgres psql -U provenance`.
2. Put the same values in `.env.production`.
3. `deploy/deploy.sh`. The API and worker reconnect with the new values.
4. Check `check-config` (the application role must still be a non-superuser that cannot bypass Row Level Security).

## The model key (GEMINI_API_KEY)
Create the new key at the provider, put it in `.env.production`, deploy, confirm a job check works, then delete the old key at the provider.

## The mail password (SMTP_PASSWORD) and GITHUB_CLIENT_SECRET
Same: create the new one at the provider, update `.env.production`, deploy, test a password reset email and a GitHub connect, then revoke the old one.

## After a leak
Rotate everything that could have been exposed, then read the runbook "security incident". A leaked `SECRET_KEY` lets someone compute a CSRF token only for a session token they already hold, and test guesses against hashed network addresses. Rotate it, and run `revoke-all-sessions` if you think session tokens leaked too. A leaked `TOKEN_ENCRYPTION_KEYS` plus a copy of the database means GitHub tokens could be read: rotate the keys, then ask people to reconnect GitHub, and revoke the OAuth app secret.

## Prevention
Keep a list of what each secret is for, who has it and when it was last changed. Scan for secrets in CI (already on). Never paste a secret into a chat, a ticket or a log.
