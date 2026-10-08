# Admin and Operational Requirements

Status: Decided (Phase 0). Basic instrumentation starts in Phase 1. Full console in checkpoint 3.5.

## 1. Phase 1 observability baseline

From the first workflow, record enough to answer:

| Question | Source |
|---|---|
| What happened | workflow_runs, workflow_steps, state_transitions |
| Which run failed, which step | workflow_steps with error_class |
| Why this result | Stored verdicts, evidence ids, scoring inputs, versions |
| How long | Step durations |
| Which model | llm_calls.model, prompt_version |
| Tokens and cost | llm_calls tokens and estimated cost |
| Which evidence | requirement_verdicts.evidence_chunk_ids, tool_calls |

Every workflow has a run_id that appears in logs, DB rows, and API responses. A minimal run view is available to developers in Phase 1 (a read-only page or CLI), expanded to the full Run Inspector in 3.5.

## 2. Admin console (Phase 3)

Each metric answers an operational question. No decorative charts.

| Question | Data |
|---|---|
| Is the system healthy | API, worker, database health, deployment version, migration version |
| Why are jobs not appearing | Source health, latency, failure rate, last success, circuit breaker state, queue depth, active workers |
| Is work stuck | Active, failed, retrying runs. Stuck tasks. Dead letters with inspect and requeue |
| What does it cost | Tokens and estimated cost by model, operation, plan, source, user (aggregate by default) |
| Is anyone abusing it | Rate limit hits, quota exceed counts, recent security events |
| Are we regressing | Latest evaluation summary |

Example answer to "why are jobs not appearing": Greenhouse healthy, Lever healthy, Adzuna rate limited, 37 tasks queued, 4 workers active.

## 3. Admin boundaries

Admins see aggregates and operational records. They do not browse resumes or materials. Break-glass access requires an explicit capability, a stated reason, and creates an audit event visible in the audit log.

## 4. Run Inspector (Phase 3)

Answers: why did this job get this recommendation, which step failed, what evidence was used, what did it cost, which model and prompt versions produced it. Shows an operational trace (counts and steps), never raw chain of thought.

## 5. Monitoring and alerting

| Signal | Alert condition (thresholds set from measurement) |
|---|---|
| API error rate and latency | Sustained breach |
| Queue depth and oldest task age | Growing or stale |
| Dead letters | Any new |
| Source failure streak | Circuit open |
| LLM error rate and spend | Spend ceiling nearing |
| Database | Connections, disk, replication or backup status |
| Backup | Missed or failed backup |
| Security | Spike in auth failures, SSRF rejections |

Alerts go to a channel the operator actually reads. An alert without a runbook is incomplete.

## 6. Logging and tracing

Structured JSON logs with run_id, user id (hashed where possible), step, duration, status. No resume text, no full prompts with PII, no secrets. Tracing uses OpenTelemetry-compatible spans where it earns its place, with run_id as the primary correlation key.
