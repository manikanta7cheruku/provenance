# ADR-0006: Source adapter architecture

Status: Accepted (Phase 0)

## Context
A Source Registry as data and adapters that emit a canonical JobPosting.

## Problem
Many sources with different capabilities and terms must feed one pipeline without leaking source fields into the domain.

## Options considered
Per-source branching in code; generic scraper; registry plus adapters.

## Decision
Registry (capabilities, compliance, health) plus adapter interface. Resolver is a pure function.

## Why
Capabilities are data so compliance can gate enablement. Adding a source does not change the domain.

## Consequences
Registry upkeep and periodic compliance review.

## Scale analysis
| Users | Posture |
|---|---|
| 10 | A handful of sources. |
| 100 | Dozens, with health and circuit breakers. |
| 10,000 | Dedicated ingestion workers per source family. |

## Revisit when
A source needs behavior that the adapter interface cannot express.
