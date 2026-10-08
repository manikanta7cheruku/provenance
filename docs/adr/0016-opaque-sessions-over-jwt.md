# ADR-0016: Opaque sessions over JWT

Status: Accepted (Phase 0)

## Context
Cookie sessions with server-side records.

## Problem
Revocation and simplicity for a first-party web app.

## Options considered
JWT access and refresh; opaque sessions.

## Decision
Opaque random token, hash in database.

## Why
Logout and password change revoke immediately. No token claims to go stale.

## Consequences
Database lookup per request.

## Scale analysis
| Users | Posture |
|---|---|
| 10 | Fine. |
| 100 | Cache short TTL. |
| 10,000 | Consider managed identity provider. |

## Revisit when
Third-party API clients need bearer tokens.
