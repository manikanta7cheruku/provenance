# ADR-0008: Authentication strategy

Status: Accepted (Phase 0)

## Context
Own email and password auth with opaque sessions, behind an AuthProvider interface.

## Problem
Need secure, revocable, understandable auth for a learning and production project.

## Options considered
Managed identity provider; JWT access and refresh tokens; opaque server sessions.

## Decision
Argon2id, opaque tokens in httpOnly Secure SameSite cookies, hash stored, rotation, revocation. Email verification behind a flag.

## Why
Server sessions are instantly revocable and simpler for a first-party web app than JWT. Interface keeps a managed provider swappable.

## Consequences
We own security of the implementation. Session lookups hit the database.

## Scale analysis
| Users | Posture |
|---|---|
| 10 | Fine. |
| 100 | Cache session lookups if measured needed. |
| 10,000 | Likely move to a managed provider for MFA, SSO and abuse tooling. |

## Revisit when
Need for MFA, SSO or compliance features, or the maintenance burden outgrows the benefit.
