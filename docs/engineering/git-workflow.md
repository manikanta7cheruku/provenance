# Git Workflow

Status: Decided. Short-lived branches, pull requests and squash merges into `main`.

## Model

- `main` is always runnable and always passes CI. Nothing is committed to it directly.
- **One branch per checkpoint**, not per phase. A checkpoint is a small, reviewable unit of work. A phase is a tag.
- Branch name: `phase-N/checkpoint-N.M-short-name`, for example `phase-1/checkpoint-1.2-auth-and-tenancy`.
- Fixes and small changes get their own short-lived branch from the latest `main`: `fix/short-name`, `docs/short-name`, `chore/short-name`.
- Work is merged by pull request with a **squash merge**, so each checkpoint becomes one commit on `main` with a clear message.
- At the end of a phase, tag `main`: `v0.1.0`, `v0.2.0`, `v0.3.0`.

## Changing something from an earlier checkpoint

You never go back to an old branch. Old branches are merged and deleted. Start from the current `main`:

```
git checkout main
git pull
git checkout -b fix/migration-lint-findings
# edit, test
git add .
git commit -m "fix(persistence): use literal SQL in foundation migration"
git push -u origin fix/migration-lint-findings
# open a pull request, wait for CI, squash merge, delete the branch
```

A change to code written in checkpoint 1.1 while you are working on 2.3 is a normal fix branch from `main`. It does not matter which checkpoint the code came from.

## Daily loop

```
git checkout main && git pull
git checkout -b phase-1/checkpoint-1.2-auth-and-tenancy
# work in small commits, run checks, push often
git push -u origin phase-1/checkpoint-1.2-auth-and-tenancy
# open a pull request. CI must pass. Squash merge.
git checkout main && git pull
git branch -d phase-1/checkpoint-1.2-auth-and-tenancy
```

## Commit messages

Conventional Commits, imperative mood, no trailing period, no em dashes: `type(scope): summary`. Types: feat, fix, docs, test, refactor, chore, ci, perf, security.

## Pull request checklist

- CI is green (python, web, secrets).
- The checkpoint's technical, UX and accessibility criteria are met.
- Documentation and ADRs are updated.
- No secrets, no `.env`, no generated files.

## Repository settings (once)

Settings, Branches, add a rule for `main`: require a pull request, require the CI checks to pass, block force pushes. Availability of branch protection for private repositories depends on your GitHub plan. If it is unavailable, follow the same rules by habit.

## Tags

```
git checkout main && git pull
git tag v0.1.0
git push origin v0.1.0
```
