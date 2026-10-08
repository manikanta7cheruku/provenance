# ADR-0001: Modular monolith

Status: Accepted (Phase 0)

## Context
Three processes (api, worker, web) sharing one codebase and one database.

## Problem
A small team must build and operate many features. Distribution adds failure modes before it adds value.

## Options considered
Microservices; serverless functions; modular monolith.

## Decision
Modular monolith with separate api and worker processes. Boundaries enforced by import-linter.

## Why
One deploy unit, one transaction scope, simple debugging, shared typed models. Boundaries preserve a path to extraction.

## Consequences
Boundaries need discipline. A bug in one module can affect the process.

## Scale analysis
| Users | Posture |
|---|---|
| 10 | Single box is fine. |
| 100 | Replicate api and worker processes. |
| 10,000 | Dedicated worker pools; consider extraction only for proven ownership or scaling needs. |

## Revisit when
A module needs independent scaling or a different team owns it.
