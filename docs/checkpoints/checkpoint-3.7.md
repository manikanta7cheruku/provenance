# Checkpoint 3.7: Production, security and your data

Phase 3, Intelligence, Monetization and Production. Branch `phase-3/checkpoint-3.7-production`. Decision: [ADR-0055](../adr/0055-production-security-and-your-data.md). Plan: [production-operations.md](../operations/production-operations.md). Builds on everything before it, especially the console ([3.5](checkpoint-3.5.md)), plans ([3.3](checkpoint-3.3.md)) and the evaluation gate ([3.6](checkpoint-3.6.md)).

## What this checkpoint is for
Make it possible to put real people on the system safely: run it from images with one script, know that its protections are on, get the data back after a disaster, and keep the promises the privacy policy makes.

## 1. Build
- **Production stack**: `compose.prod.yaml`, production Dockerfiles for the API and the web app, an nginx config with security headers, a Caddy proxy that gets its own certificate, `.env.production.example`.
- **Deploy scripts** in `deploy/`: `deploy.sh` (build, back up, migrate, check, start, smoke, roll back), `rollback.sh`, `backup.sh`, `restore.sh` (a drill and a real restore), `smoke.sh` (15 checks).
- **Configuration checks**: `pv_api.cli check-config` and stricter production settings.
- **Token key ring**: `TOKEN_ENCRYPTION_KEYS`, `v2` sealed values, `reseal-tokens` for rotation.
- **Your data**: a copy of it, and account deletion (a durable task that removes files and every row), in Settings.
- **Incident tools**: `revoke-all-sessions`.
- **Public documents**: a privacy policy and terms of use (drafts) at `/privacy` and `/terms`.
- **CI**: dependency audits and an images job. Two real vulnerabilities fixed (`cryptography`, `certifi`).
- **Runbooks**: database failure, migration rollback, failed deployment, data deletion request, security incident, backup restore, secret rotation, model provider outage, high model costs, prompt injection, source outage and schema change. Plus disaster recovery, incident response, drills and a hardening review.
- Data: migration 0023 (`users.deletion_requested_at`, `account_deletions`), routes `GET /api/v1/account/export` and `POST /api/v1/account/delete`, worker task `delete_account`.

## 2. UX
- Settings, Your data: download a copy; delete the account with the password and the words typed, a clear statement that it cannot be undone, and focus on Cancel so a stray Enter confirms nothing.
- After deleting you are signed out and sent to sign in.
- The privacy policy and the terms are public, in plain words, and list what is still open.

## 3. Technical acceptance criteria
1. The production images build, run as a non-root user with no development tools, and the stack starts with only the proxy on the host.
2. A deploy takes a backup, migrates, checks the configuration, waits for readiness and smoke tests; a bad configuration stops it and a bad version rolls back.
3. `check-config` fails an unsafe configuration and prints no secret.
4. Connector tokens rotate without disconnecting anyone.
5. After the deletion task, no table holds a row for the person, no stored file remains, and no email remains in audit records, invites or queued mail.
6. A restore drill and a real restore both succeed and are timed.
7. The whole browser suite passes against the production stack.
8. Ruff, mypy, import-linter, unit tests, the integration tests for this checkpoint and the web tests pass.

## 4. Accessibility acceptance criteria
Axe finds no WCAG 2.2 A or AA violation in Your data, the delete dialog (empty and with errors) and both public documents, in light and dark, and nothing scrolls sideways at 390 pixels. The dialog starts on Cancel. Fields are labeled and errors are on the field.

## 5. Test
| Where | What |
|---|---|
| `tests/unit/test_secretbox.py` | the key ring (9 added) |
| `tests/unit/test_settings.py`, `test_api.py`, `test_mail.py` | production settings (4 added) |
| `tests/unit/test_readiness.py` | the configuration checks (11) |
| `tests/integration/test_production_readiness.py` | database checks, rotation, headers, cookies, incident command (14) |
| `tests/integration/test_account.py` | the copy of your data and deletion (16) |
| `e2e/account.spec.ts` | Your data, the dialog, the documents (10) |
| the whole browser suite | also run against the production stack over TLS |
| `docs/operations/drills.md` | nine drills with what was seen |

## 6. Not verified
A real host, a real domain, a real certificate and real mail (the owner provides them). Copying backups off the machine (C-160). Image vulnerability scanning (C-163). A penetration test (C-164). Bot protection on sign-up (C-165). A lawyer's review (C-155). A tabletop with more than one person (C-157, C-161). Failure drills on the real host (C-158). Object storage (C-40). A paid model plan with no-training terms (C-42). A screen reader pass (C-166). Cross-browser runs in Firefox and Safari (C-167). The full 28 minute backend suite was not run for this checkpoint by agreement; it runs now, after all checkpoints.

## 7. What is next
The checkpoint list is complete. What remains is the full backend suite and the carryover register: first what can be done without the owner, then what only the owner can do (accounts, domain, money, lawyer, real users).
