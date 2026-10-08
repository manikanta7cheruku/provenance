# Provider: PostgreSQL and pgvector

| Field | Value |
|---|---|
| Role in Provenance | System database, task queue, full-text search, vector search, checkpoint store |
| Official documentation URL | https://www.postgresql.org/docs/16/ |
| Extension documentation | https://github.com/pgvector/pgvector (README) |
| Terms of service | Open source license (PostgreSQL License). Confirm current text in each project's repository before redistribution |
| Container image used | `pgvector/pgvector:0.8.0-pg16` (pinned) |
| Capability class | Self-hosted dependency, not an external data source |
| Current integration status | Integrated in checkpoint 1.1 |
| Last reviewed date | 2026-10-08 |
| Reviewed by | Project owner |
| Next review due | At checkpoint 3.7 (production image and managed database choice) |
| Notes | Verify that the pinned image tag still exists when upgrading. Managed Postgres providers must support the `vector`, `citext` and `pg_trgm` extensions |
