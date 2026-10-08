# Provenance

Jobs, with receipts.

Provenance is a multi-tenant job intelligence platform. It finds jobs from permitted sources, extracts what each job requires, compares those requirements against a candidate's real evidence, and explains every conclusion with traceable proof. It never submits an application on the user's behalf.

## Status

Phase 1 in progress. Checkpoint 1.1 (foundation) is the first code. The planning pack lives in [`docs/`](docs/README.md).

| Phase | Goal | Tag |
|---|---|---|
| 0 | Planning pack: requirements, UX specification, architecture, threat model, ADRs | v0.0.1 |
| 1 | Foundation and core loop | v0.1.0 |
| 2 | Sources, workflow, tailoring | v0.2.0 |
| 3 | Depth and production | v0.3.0 |

## Principles

1. Evidence over model confidence.
2. Code enforces and computes. LLMs interpret and reason.
3. Human approval before any consequential action. There is no application-submission state.
4. Source compliance over scraping convenience.
5. Every conclusion is auditable.

## Documentation

Start at [docs/README.md](docs/README.md). Local setup is in [docs/development-setup.md](docs/development-setup.md).

## License

MIT. See [LICENSE](LICENSE).

## Run it locally

See [docs/checkpoints/checkpoint-1.1.md](docs/checkpoints/checkpoint-1.1.md) for exact commands. Summary: install Docker Desktop and uv, copy `.env.example` to `.env`, run `uv sync --all-packages`, run `npm install` in `apps/web`, then `docker compose up --build`.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) and [docs/engineering/git-workflow.md](docs/engineering/git-workflow.md).
