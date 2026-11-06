# Security hardening review

Status: Reviewed in checkpoint 3.7. Each control, where it lives, how it is tested, and what is still open. This is the checklist to read again before launch and after any big change.

| Area | Control | Where | Tested by | State |
|---|---|---|---|---|
| Identity | Passwords hashed with Argon2, rehashed when parameters change, a dummy hash for unknown emails so timing does not reveal who exists | `pv_api.security.passwords` | auth integration tests | done |
| Sessions | Random tokens stored hashed, revoked on password change and on deletion, idle and absolute limits, cookie `__Host-` prefixed, Secure, HttpOnly, SameSite | `auth_service`, settings | unit and integration tests, production cookie test | done |
| CSRF | A token derived from the session on every state change, plus an Origin check | `deps`, `security.middleware` | CSRF and origin tests | done |
| Isolation | Row Level Security enabled and forced on every table with an owner, the application role cannot bypass it | migrations, `check-config` | RLS tests, `check-config` | done |
| Admin boundary | Admin routes read system tables only; no admin route can read content | `observability`, ADR-0023, ADR-0053 | the no-tenant-table test | done |
| Secrets | Required in production, placeholders refused, never logged, connector tokens sealed with a separate rotatable key ring | settings, `secretbox` | settings and secretbox tests | done |
| Transport | TLS ended at the proxy with HSTS; cookies Secure; plain http redirected | `deploy/Caddyfile` | smoke test | done (real certificate at launch) |
| Headers | CSP, frame denial, nosniff, referrer and permissions policies on pages (nginx) and on the API; no server banner | `nginx.conf`, API middleware | smoke test, the whole browser suite against the production stack | done |
| Input | Size limits, file type checks from bytes, SSRF-hardened fetch, spreadsheet formula neutralizing, formula-safe exports | many | many | done |
| Abuse | Rate limits per user and per address, quotas, invite gating, a spend ceiling alert | `ratelimit`, plans | limit tests | done |
| Supply chain | Locked dependencies, `pip-audit` and `npm audit` in CI (two real findings fixed in this checkpoint: `cryptography` and `certifi`), secret scanning, pinned base images | CI | CI | done; image scanning open (C-163) |
| Containers | Non-root user, read-only filesystem, all capabilities dropped (except what the database image needs), no new privileges, memory limits, no published ports except the proxy | `compose.prod.yaml` | CI image checks, the production stack run | done |
| Deletion | Account deletion removes files and every row; the test walks every foreign key | `delete_account` | the deletion tests | done |
| Logging | Structured, request ids, no passwords, no resume or job text, no tokens; audit holds actions not content | middleware | redaction tests | done |
| Documentation off | Interactive API docs off in production | `main.py` | production test | done |
| Dependencies' OS packages | Image vulnerability scan | | | open (C-163) |
| Penetration test | By someone other than the author | | | open (C-164) |
| Bot protection on sign-up and sign-in | CAPTCHA or similar | | | open, a decision for the owner (C-165) |

## What was found and fixed in this review
- `cryptography` 47.0.0 and `certifi` 2026.7.22 had published vulnerabilities; upgraded to 50.0.2 and 2026.10.23, and CI now fails on a new one.
- The row-security check flagged the task queue, which carries an owner column on purpose (it is claimed across people). It is now a named system table in the check.
- The web container cached the API address, breaking the site after a deploy. Fixed.
- A belief that rotating the application secret signs people out was wrong. Fixed with a command and corrected runbooks.
