# ADR-0004: LangGraph for the agentic subgraph (pending spike)

Status: Accepted (Phase 0)

## Context
A durable graph runtime for the evidence resolution agent only.

## Problem
The agent needs typed state, checkpointing, interrupt and resume across worker crashes.

## Options considered
Hand-rolled loop with our own state table; LangGraph; other agent frameworks.

## Decision
Provisional: LangGraph for the subgraph only, confirmed or reversed by a spike in checkpoint 1.6 comparing it to a hand-rolled loop.

## Why
Checkpoint and interrupt are hard to get right. But a framework is a dependency we must understand. The spike keeps the choice evidence based.

## Consequences
Dependency weight and upgrade risk. The domain must not import it.

## Scale analysis
| Users | Posture |
|---|---|
| 10 | Either option works. |
| 100 | Either works. Observability matters more. |
| 10,000 | Framework value rises with graph complexity. |

## Revisit when
The spike shows little saving, or upgrades repeatedly break us.
