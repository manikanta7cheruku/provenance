# Contributing

## Workflow

See [docs/engineering/git-workflow.md](docs/engineering/git-workflow.md). In short: one branch per checkpoint, a pull request, CI green, squash merge, tag at the end of each phase.

A checkpoint is done only when it meets the Definition of Done and its technical, UX and accessibility acceptance criteria in [docs/roadmap/implementation-plan.md](docs/roadmap/implementation-plan.md).

## Commit messages

Conventional Commits: `type(scope): summary`, imperative mood, no trailing period, no em dashes.

Types: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`, `ci`, `perf`, `security`.

## Rules that are enforced

- Domain code must not import FastAPI, SQLAlchemy, source adapters or agent frameworks (import-linter in CI).
- Frontend dependencies follow `ui`, `lib`, `features`, `app` boundaries (`npm run check:boundaries` in CI). `app/` holds composition only.
- Components use design tokens only. A raw color, size, radius, shadow or duration in component CSS is a defect.
- Every tenant table needs an isolation test.
- Every LLM feature needs a versioned prompt, versioned schema, evaluation fixture and cost measurement.
- Every screen implements the state catalog in the UX specification.
- No secrets in the repository.
- No em dashes in documentation or product copy.
