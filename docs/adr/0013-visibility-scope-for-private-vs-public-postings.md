# ADR-0013: Visibility scope for private vs public postings

Status: Accepted (Phase 0)

## Context
Postings are public or private. Users reach them via per-user sightings.

## Problem
A global postings table would leak user-supplied or confidential content between tenants.

## Options considered
Fully global postings; fully per-user postings; scoped visibility with sightings.

## Decision
visibility column, per-user job_sightings holding original values, no merge that exposes private fields, global caching only on public text.

## Why
Keeps dedup and cost sharing for public jobs without leaks.

## Consequences
More complex queries and RLS policies.

## Scale analysis
| Users | Posture |
|---|---|
| 10 | Fine. |
| 100 | Fine. |
| 10,000 | Fine. |

## Revisit when
A cross-user sharing feature is requested.
