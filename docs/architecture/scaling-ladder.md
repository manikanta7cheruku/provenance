# Scaling Ladder and Evolution Policy

Status: Decided (Phase 0)

## 1. Policy

No infrastructure is added for imagined scale. Every step up is driven by a measured bottleneck and documented with the template below.

Bottleneck signals: API latency, database CPU, connections, queue depth and age, worker utilization, discovery throughput, LLM latency, LLM cost, vector search latency, storage growth, error rate, source quotas.

## 2. Ladder

| Stage | Shape | Trigger to leave |
|---|---|---|
| 0 Local | Compose, local Postgres, dev mail, optional local model | First real cohort |
| 1 Closed cohort | One VM running compose.prod, managed or self-managed Postgres with backups, object storage, one or two workers, reverse proxy with TLS | Sustained API or worker saturation |
| 2 Growing | Multiple API replicas, multiple workers, connection pooling, indexing and query tuning, caching of hot reads | Database CPU or connection limits, queue latency |
| 3 Significant | Dedicated ingestion and analysis worker pools, queue tuning, managed observability, larger database, read replica | Queue contention, ingestion throughput |
| 4 Large | Specialized components only where measured: dedicated queue broker, dedicated vector store, search engine | Measured limits of Postgres for that workload |
| 5 Distributed | Extract services for ownership, independent scaling, fault isolation | Concrete benefit exceeds operational cost |

## 3. What changes at each user scale (summary, details per ADR)

| Users | Expected posture |
|---|---|
| 10 | Everything on one box. Simplicity is the feature |
| 100 | Managed DB backups, two workers, rate limits and quotas matter, cost dashboard in use |
| 10,000 | Replicas, pooled connections, partitioned or archived old data, dedicated workers, careful LLM routing and caching, possibly separate vector index |

## 4. Migration record template

```
Current bottleneck:
Evidence (metrics):
Options considered:
Chosen solution:
Migration strategy:
Rollback strategy:
Expected improvement:
Actual measured improvement:
New operational complexity:
```

Each migration gets an ADR or an addendum to the relevant ADR.
