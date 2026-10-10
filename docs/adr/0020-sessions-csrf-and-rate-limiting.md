# ADR-0020: Sessions, CSRF protection and rate limiting

Status: Accepted (checkpoints 1.2 and 1.3). Implements ADR-0008, ADR-0009 and ADR-0016.

## Context
The web app and API are first party and share a site. Users hold sensitive data. Abuse (credential stuffing, spam, cost) must be limited before public use.

## Problem
Choose a session mechanism, a CSRF defense that works with it, and a rate limiting design that does not leak information and does not need extra infrastructure.

## Options considered
1. Sessions: opaque server-side tokens in cookies, or signed JWTs.
2. CSRF: synchronizer token stored per session, derived (HMAC) token, double-submit cookie, SameSite only.
3. Rate limits: reverse proxy only, in-memory counters, Redis, Postgres counters.
4. Email delivery: inline in the request, or after the response.

## Decision
1. **Opaque session tokens.** 256 random bits, stored only as a SHA-256 hash. Cookie is httpOnly, SameSite=Lax, and Secure with the `__Host-` prefix in production. Idle timeout 7 days, absolute lifetime 30 days (configurable). Password change or reset revokes every session. Password change also rotates the current session.
2. **Derived CSRF token.** The token is `HMAC(SECRET_KEY, "csrf:" + session token)`. It needs no storage, is bound to one session, and is returned by `GET /auth/session`. State-changing requests from a signed-in browser must send it in `X-CSRF-Token`. In addition, any unsafe request that carries an `Origin` header from a non-allowed origin is rejected before routing. SameSite=Lax is the third layer.
3. **Postgres fixed-window counters** keyed by policy and a keyed hash of the subject (IP or email), so raw emails and addresses never reach the table. Each hit commits in its own transaction so failed requests count. Policies are data (`DEFAULT_POLICIES`) and the app accepts a different table.
4. **Mail is sent after the response** (background task) so timing does not reveal whether an account exists. Checkpoint 1.4 replaces this with the durable queue.

Additional rules: login failure messages are identical for unknown email and wrong password, and an unknown email still pays the cost of one password hash. Registration is invite-only by default. Every authentication event is written to an append-only audit table.

## Why
- Opaque sessions are revocable instantly and need no token claims to go stale.
- A derived CSRF token removes a storage column and a lookup while staying bound to the session.
- Counters in the database add no new system and keep the limits consistent across API replicas.
- Hashing the rate limit subject keeps personal data out of operational tables.

## Consequences
- Every authenticated request reads one session row. Acceptable now. A short cache is the first optimization if measurements demand it.
- A fixed window allows a burst at a window boundary. A sliding window is a later refinement.
- Per-IP limits depend on the client address. Behind a proxy the proxy must pass it, and the application must trust only that proxy. Development uses `--forwarded-allow-ips=*`, which is development only.
- Registration with an invite reveals that an email exists when it is already taken. This is accepted while signup is invite-only. Public signup must switch to the "check your email" pattern.
- Email sent in a background task is lost if the process dies at the wrong moment. Accepted until 1.4.

## Scale analysis
| Users | Posture |
|---|---|
| 10 | Everything above is fine |
| 100 | Fine. Watch rate limit table size (purged opportunistically) |
| 10,000 | Cache session lookups briefly, consider an in-memory counter store for hot limits, move mail to the queue (done in 1.4), consider a managed identity provider for MFA and abuse tooling |

## Revisit when
Rate limit writes appear among the top database load contributors, session lookups dominate latency, MFA or SSO is required, or public signup is enabled.
