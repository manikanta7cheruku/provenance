# ADR-0003: pgvector instead of a separate vector database

Status: Accepted (Phase 0)

## Context
Embeddings stored in Postgres next to the evidence they describe.

## Problem
Semantic retrieval is needed over per-user evidence and job requirements.

## Options considered
Pinecone; Qdrant; Weaviate; pgvector.

## Decision
pgvector with an ANN index chosen from measurement.

## Why
Vectors are transactionally consistent with rows, RLS applies to them, one fewer system, volumes per user are small.

## Consequences
Index tuning is on us. Large global vector sets may stress the database.

## Scale analysis
| Users | Posture |
|---|---|
| 10 | Exact scan is fine. |
| 100 | HNSW or IVFFlat index. |
| 10,000 | Evaluate partitioning by tenant, or a dedicated store if recall or latency degrade. |

## Revisit when
p95 vector search latency or index build time breaches targets under realistic load.
