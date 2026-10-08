# Production Operations Plan

Status: Decided (Phase 0). Describes how the same architecture evolves from laptop to production. Docker is a deployment unit, not only a development convenience.

## 1. Container evolution

| Stage | Where | Notes |
|---|---|---|
| Dev | Docker Compose on the laptop: postgres, api, worker, web, mailpit, optional local model | Hot reload, dev defaults |
| CI | Same images built, tested against real Postgres service container | |
| Stage 1 | Same images on one VM with `compose.prod.yml` behind a reverse proxy with TLS | Managed Postgres option from the start if affordable |
| Later | Same images on a container platform with horizontal API and worker replicas | No application rewrite |

Image rules: pinned base image versions (never `latest`), multi-stage builds, non-root users, healthcheck, resource limits, graceful shutdown, no secrets baked in, SBOM or vulnerability scan in CI, immutable tags equal to the git SHA.

## 2. Configuration and secrets

- Settings validated at startup. Missing or insecure production settings abort startup.
- Secrets arrive through environment or a secret store, never the repo. Rotation procedure documented. Encryption key for connector tokens has a recovery plan.
- Separate config per environment. Production values never exist on a developer laptop.

## 3. Health, readiness, liveness

| Endpoint | Meaning |
|---|---|
| /healthz (liveness) | Process is up |
| /readyz (readiness) | DB reachable, migrations at expected version, required config present |
| Worker heartbeat | Row updated periodically. Stale heartbeat raises an alert |

## 4. Database and migrations

- Alembic migrations run by a separate privileged role, as a deploy step before the new version receives traffic.
- Migrations are backward compatible for one version (expand, migrate, contract) so rollback of app code is safe.
- Backups and restore drills per identity-and-data-lifecycle-requirements.md.

## 5. Worker recovery and retries

Visibility timeout returns abandoned tasks to the queue. Retries use exponential backoff with jitter. After max attempts, tasks go to dead letter with context, inspectable and requeueable by admins. Agent runs resume from checkpoints.

## 6. Source circuit breakers

Per source: failure streak opens the breaker, jittered half-open probes, health status in the registry. Other sources continue.

## 7. Deployment and rollback strategy

1. Build and test in CI. Push image tagged by git SHA.
2. Backup, run migration, start new containers, wait for readiness, switch traffic.
3. Rollback: redeploy previous tag. Migrations are backward compatible, so data stays valid.
4. Feature flags and a kill switch for expensive features.

Blue-green or rolling updates are adopted when downtime becomes unacceptable, not before.

## 8. Disaster recovery

Documented rebuild from backup onto a fresh host, with RPO and RTO recorded. Restore is rehearsed, not assumed.

## 9. Security incident response

Runbook: detect, contain (revoke sessions, rotate secrets, disable features), assess impact from audit logs, notify as required by applicable law and policy, recover, post-incident review. A tabletop drill is part of checkpoint 3.7.

## 10. Privacy operations

Retention schedule, deletion workflow, DSAR style data export, and PII-safe logging are operational duties with owners, listed in privacy.md.

## 11. Cost operations

Usage ledger, daily spend ceiling, provider budget alerts, monthly cost review comparing actual cost per analysis against the economics model.
