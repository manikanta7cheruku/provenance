# Contributing

## Workflow

1. Work on a branch named `phase-N/checkpoint-N.M-short-name`.
2. One checkpoint equals one pull request equals one squash commit on `main`.
3. A checkpoint is done only when it meets the Definition of Done in [docs/roadmap/implementation-plan.md](docs/roadmap/implementation-plan.md).

## Commit messages

Conventional Commits: `type(scope): summary`, imperative mood, no trailing period, no em dashes.

Types: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`, `ci`, `perf`, `security`.

Examples:

- `docs(phase-0): add planning pack`
- `feat(auth): add argon2id password hashing and cookie sessions`
- `security(tenancy): enforce row level security on tenant tables`

## Rules that are enforced

- Domain code must not import FastAPI, SQLAlchemy, source adapters or agent frameworks (checked by import-linter in CI).
- Every tenant table needs an isolation test.
- Every LLM feature needs a versioned prompt, versioned schema, evaluation fixture and cost measurement.
- No secrets in the repository.
- No em dashes in documentation or product copy.
