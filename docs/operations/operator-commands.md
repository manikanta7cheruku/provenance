# Operator commands

Everything below runs in **PowerShell**, from the repository folder
(`M:\Manikanta\Apps\MK-Projects\Agent\provenance`). The helper script wraps Docker Compose and `uv`.

```powershell
.\scripts\pv.ps1 help
```

If PowerShell refuses to run the script: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, then open a new window.

## Helper script

| Command | What it does |
|---|---|
| `up` | Build and start postgres, migrate, api, worker, mailpit, web. Prints the URLs |
| `down` | Stop everything, keep data |
| `reset` | Stop and delete the database volume (you must type RESET) |
| `restart [service]` | Restart one service. Default `worker`. The worker has no auto-reload |
| `status` | Container state, API readiness, queue counts |
| `logs [service]` | Follow logs. Example: `logs worker` |
| `migrate` | Run migrations now |
| `invite [email]` | Print a one-time signup code |
| `admin <email>` | Give an existing account the ADMIN role |
| `inbox` | Open the Mailpit inbox |
| `psql` | Open psql as the database owner |
| `queue` | Queue counts, ten most recent tasks, workers |
| `demo-task [seconds]` | Enqueue a harmless task (crash-recovery lab) |
| `demo-run <email>` | Create a finished demo run so the Runs screen has something to show |
| `ai-check` | List the Gemini models your key can use and test one generation and one embedding |
| `test` | ruff, format check, mypy, import-linter, unit tests, web checks |
| `itest` | Integration tests. Stops the worker first and starts it again afterwards |

## Raw commands (what the script runs)

| Need | Command |
|---|---|
| Start | `docker compose up -d --build` |
| Stop | `docker compose down` |
| Worker logs | `docker compose logs -f worker` |
| Two workers | `docker compose up -d --scale worker=2` |
| Migrations | `docker compose run --rm migrate` |
| Invite | `docker compose exec api python -m pv_api.cli create-invite --email someone@example.com` |
| Promote admin | `docker compose exec api python -m pv_api.cli promote-admin --email someone@example.com` |
| Demo task | `docker compose exec worker python -m pv_worker.cli enqueue-demo --seconds 20` |
| Demo run | `docker compose exec api python -m pv_api.cli seed-demo-run --email someone@example.com` |
| AI check | `uv run python -m pv_llm.check` |
| Unit tests | `uv run pytest` |
| Integration tests | `docker compose stop worker; uv run pytest -m integration; docker compose start worker` |

## Ports

| Port | Used by | If it is taken |
|---|---|---|
| 5173 | web | Change the mapping in `compose.yaml` and `CORS_ORIGINS`, `PUBLIC_BASE_URL` in `.env` |
| 8000 | api | Change the mapping and `VITE_API_PROXY_TARGET` stays `http://api:8000` (internal) |
| 5433 | postgres | Change the mapping and the two localhost URLs in `.env` |
| 8025 | Mailpit web UI | Change the left side of `127.0.0.1:8025:8025` in `compose.yaml` and set `DEV_INBOX_URL` in `.env` |
| 1025 | Mailpit SMTP (for tools on your machine) | The worker reaches Mailpit inside Docker as `mailpit:1025`, so you may remove this mapping entirely |

Find what holds a port: `Get-NetTCPConnection -LocalPort 8025 | Select-Object OwningProcess` then `Get-Process -Id <pid>`.

## Where email goes

| `SMTP_HOST` in `.env` | Behaviour | Where to look |
|---|---|---|
| `mailpit` (default) | Worker sends to the Mailpit container | http://localhost:8025 |
| empty | Worker writes the email, link included, to its log (development only) | `.\scripts\pv.ps1 logs worker` |
| a real SMTP host | Real delivery | Your provider. Production requires this |

Emails are always queued first. If nothing arrives, check the worker is running (`status`) before anything else.
