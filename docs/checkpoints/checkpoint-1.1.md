# Checkpoint 1.1: Foundation, application shell and design-system foundation

Phase 1, Foundation and Core Intelligence. Tag at the end of Phase 1: v0.1.0.

## 1. Build

Technical:
- uv workspace with one lockfile: `apps/api`, `packages/domain`, `packages/config`, `packages/persistence`.
- Docker Compose: PostgreSQL 16 with pgvector, a one-shot migration service, the API, the web dev server.
- Two database roles: an owner for migrations and a least-privilege application role created by an init script.
- Alembic with a first migration: extensions (vector, citext, pg_trgm) and application-role grants. All SQL is literal (no string building).
- Fail-fast typed settings. Missing, weak or placeholder configuration stops startup.
- FastAPI app factory, `/healthz` (liveness), `/readyz` (readiness: database and migrations), `/api/v1/status`, JSON request logging with request ids, classified error responses.
- `FailureClass` in the domain package.
- import-linter contracts, ruff, mypy, pytest, GitHub Actions CI with a real PostgreSQL, secret scanning.

Frontend:
- Application shell, routing and navigation. Responsive layout (sidebar from 900px, toggled menu below).
- Design-system foundation: complete token file and six primitives (Button, Status, Notice, Section, EmptyState, PageHeader).
- `settings` feature with live system status. `features/planned` holds honest placeholders for screens later checkpoints build.
- `lib/system-status.tsx` holds shared API status state. `app/` holds composition only.

## 2. UX

- A coherent frame every later screen lives inside, with the final navigation and URL structure.
- Typographic, flat visual language: content sits on the page, hierarchy comes from type, spacing, hairline rules and alignment. No cards, gradients, shadows or badges.
- Honest placeholders. Each unbuilt screen says why it matters and what comes next, and names the checkpoint that builds it.
- Live system status in the navigation and in Settings, with explicit loading, ready, not ready and unreachable states.
- A not-found page with a next action.

## 3. Technical acceptance criteria

1. `docker compose up --build` ends with postgres healthy, `migrate` exited with code 0, `api` healthy, `web` running.
2. `GET http://localhost:8000/healthz` returns `{"status":"ok"}`. `GET /readyz` returns 200 with `"ready": true`.
3. `http://localhost:8000/api/docs` shows generated OpenAPI documentation (development only).
4. Removing `SECRET_KEY` from `.env` stops the API with a clear validation message. Compose refuses to start if a required variable is empty.
5. The application database role cannot create tables and is not a superuser (proved by tests).
6. `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy`, `uv run lint-imports` pass.
7. `uv run pytest` passes. After migrating, `uv run pytest -m integration` passes.
8. In `apps/web`: `npm run check:boundaries`, `npm run typecheck`, `npm run build` pass.
9. CI is green on the pull request.

## 4. UX acceptance criteria

1. Opening http://localhost:5173 lands on Opportunities inside the shell.
2. Opportunities, Saved, Applications, Profile and Runs each have their own title and an empty state with why it matters and what to do next.
3. Settings shows the system status table with real values from the API.
4. Stopping the API container changes the navigation indicator to "API unreachable". Settings says no data is at risk and offers Check again. Restarting the API and pressing Check again recovers.
5. An unknown URL shows the not-found page with a link back.
6. The interface contains no card containers, gradients, shadows, badges or decorative elements.

## 5. Accessibility acceptance criteria

1. The first Tab stop is "Skip to content" and it jumps to the main area.
2. Every navigation link is reachable by keyboard with a visible focus ring. The current page has `aria-current="page"`.
3. After navigating, focus moves to the page heading and the document title changes.
4. Below 900px the Menu button has `aria-expanded` and `aria-controls`, and Escape closes the menu. Menu links are 44px tall.
5. The shell status is a polite live region. Status is conveyed by text and a distinct dot shape, never color alone.
6. Light and dark themes follow the operating system. Reduced motion is respected.
7. 200 percent zoom without horizontal page scrolling (manual check).
8. Contrast for every token pair used (computed, section 8).

## 6. Completion report

### Files changed since the first 1.1 package
- Migration `0001_foundation.py`: literal SQL (fixes Ruff S608).
- Frontend: tokens, base and component CSS rewritten as a real system. New primitives Button, Status, Notice, Section. EmptyState and PageHeader reworked. Removed StatusPill and `features/system`. Added `features/settings`, `lib/system-status.tsx`, `app/NavStatus.tsx`, `features/planned/planned-screens.ts`.
- Docs created or rewritten: `design-system.md` (full system), `engineering/git-workflow.md`, this document.
- Docs updated: `ux-specification.md` (interaction patterns, destructive-action and success states, operation state models), `ai-ux-patterns.md` (vocabulary, user control), `architecture.md` (state diagram, styling row), `data-model.md` (canonical state vocabularies), `user-journey.md`, `product-requirements.md`, ADR-0014 and ADR-0019 addenda, `CONTRIBUTING.md`, both READMEs.

### Consistency review (documents checked against each other)

Checked: user-journey, ux-specification, product-requirements, design-system, architecture, ADR-0005, ADR-0011, ADR-0014, ADR-0017, ADR-0019.

| # | Conflict found | Resolution | Where |
|---|---|---|---|
| 1 | User journey said save, dismiss and applied are reversible. The state diagram had no reverse transitions | Added unsave, undo dismiss, undo applied and retry transitions | architecture.md, ADR-0014 addendum |
| 2 | "Processing" and "Partial result" had no backend definition | Defined as derived UI states from match state plus persisted verdicts | ux-specification 10.2, architecture.md |
| 3 | `needs_user_input` was listed as a task state but is a match and run state | Split task states (10.1) from match states (10.2) | ux-specification, data-model section 8 |
| 4 | Architecture named Tailwind. ADR-0019 chose plain CSS tokens | Plain CSS tokens now. Utility framework decided in 1.5 and only if token-driven | architecture.md, ADR-0019 addendum |
| 5 | Settings screen sat in `app/` in the first 1.1 package | Moved to the `settings` feature. Shared status state moved to `lib/` | ADR-0019 addendum, code |
| 6 | User journey redefined state and progress rules already in the UX documents | Replaced with pointers so there is one definition | user-journey.md |
| 7 | Claim origin, evidence kind and verdict overlapped in wording | Added a vocabulary table and stored values once | ai-ux-patterns section 0, data-model section 8 |
| 8 | Design system said dark mode ships only if contrast is verified. 1.1 had shipped dark unchecked | Verified all pairs in both themes (section 8) | this document |
| 9 | Resume upload sequence in the UX brief had no backend mapping | Defined server states and client-only transport states | ux-specification 10.3, data-model |
| 10 | My previous package wrote the root README over `docs/README.md` | Rebuilt both files | this package |

No conflict found in ADR-0005 (no submission state), ADR-0011 (grounding) or ADR-0017 (one agent). These are checked by the script in section 7.

### Design-system decisions
Tokens for color roles, typography hierarchy, spacing, sizing, density, borders, radii, elevation, motion, focus and interaction states. Two radii, one shadow (unused so far), one accent. State dot shapes differ by tone. Content is not boxed. A new color, size or radius requires a token first. See [design-system.md](../architecture/design-system.md).

### Frontend architecture decisions
`ui` (presentational primitives), `lib` (infrastructure, no UI), `features` (product experiences, no cross-feature imports), `app` (composition only). Enforced by a script in CI. See ADR-0019 and its addendum.

### Technical tests executed
In my sandbox (no network, no Docker, no Python libraries installed): Python syntax compilation, TOML, JSON and YAML parsing, line-length and unused-import scans, and a scan for string-built SQL. These did not and could not run ruff, mypy or pytest. **Those must run on your machine** (section 9). Ruff's S608 rule is unanchored, so my earlier belief that it only matched queries starting with SELECT was wrong. That is why the migration findings appeared.

### Frontend checks executed
Boundary check (passes, and fails correctly when I add a violation). Not run in my sandbox: `tsc`, `vite build`, because npm packages cannot be installed there.

### Visual and UX validation performed
I rendered static HTML that mirrors the exact DOM and CSS of the components in headless Chromium and reviewed screenshots of: desktop light, desktop dark, Settings with healthy status, Settings with unreachable API, and the mobile menu. Findings fixed: the wordmark and page title baselines differed by about 3px (now within 1px), status text size differed from table text, and notice titles lacked spacing. **This is not a test of the running React app.** Please confirm visually on your machine, in light and dark, and at a narrow width.

### Deliberately deferred
Self-hosted brand fonts (1.5, after prototypes). High-fidelity prototypes of Opportunities and Job detail (start of 1.5). Component gallery and axe in CI (1.5). Form controls and validation (1.2). Generated frontend state types from OpenAPI (1.4). Production image (3.7). Mailpit (1.3). Dependency vulnerability audit in CI (1.3).

### Final commit hash
Not available yet. The commit happens on your machine. After committing run `git log -1 --format=%H` and send it to me.

## 7. Automated validation of the documents and code structure

Run by script against the merged documentation set and the frontend source.

| Check | Result | Detail |
|---|---|---|
| ux-specification covers required items | PASS | 16 items |
| ai-ux-patterns covers required items | PASS | 9 items |
| architecture state diagram == data-model match states | PASS | 16 states |
| no submitting/submitted state anywhere (ADR-0005) | PASS |  |
| UX task states are stored task states | PASS | unknown: [] |
| UX match states are stored match states | PASS | unknown: [] |
| verdict vocabulary: requirements == data-model | PASS | [] |
| breakpoints 600/900 identical in design-system, ux-spec, shell.css | PASS |  |
| one-agent rule consistent (ADR-0017, component register, agent architecture) | PASS |  |
| grounding rule present in ADR-0011, agent architecture, AI UX | PASS |  |
| app/ contains composition files only | PASS | ['App.tsx', 'NavStatus.tsx', 'Shell.tsx', 'nav.ts', 'shell.css'] |
| settings is a feature (ADR-0019 addendum) | PASS |  |
| frontend boundary check | PASS | Boundaries OK |
| no raw colors/easings in component CSS | PASS |  |
| all relative documentation links resolve | PASS | re-run after the README fix, 0 broken |
| no em or en dashes | PASS |  |

## 8. Contrast results (WCAG 2.2, final token set)

| Theme | Pair | Ratio | Needed | Result |
|---|---|---|---|---|
| light | primary text on base | 16.35 | 4.5 | pass |
| light | secondary text on base | 6.75 | 4.5 | pass |
| light | secondary text on hover surface | 6.24 | 4.5 | pass |
| light | primary text on selected nav | 14.66 | 4.5 | pass |
| light | link/accent on base | 8.12 | 4.5 | pass |
| light | on-accent text on primary button | 8.55 | 4.5 | pass |
| light | on-accent text on button hover | 10.89 | 4.5 | pass |
| light | on-accent text on button pressed | 13.49 | 4.5 | pass |
| light | success status dot on base | 6.03 | 3.0 | pass |
| light | warning status dot on base | 5.62 | 3.0 | pass |
| light | danger status dot on base | 6.23 | 3.0 | pass |
| light | danger notice rule on base | 6.23 | 3.0 | pass |
| light | control border on base | 3.45 | 3.0 | pass |
| light | focus ring on base | 8.12 | 3.0 | pass |
| light | accent bar on selected nav | 7.29 | 3.0 | pass |
| dark | primary text on base | 15.36 | 4.5 | pass |
| dark | secondary text on base | 7.50 | 4.5 | pass |
| dark | secondary text on hover surface | 7.74 | 4.5 | pass |
| dark | primary text on selected nav | 12.30 | 4.5 | pass |
| dark | link/accent on base | 7.78 | 4.5 | pass |
| dark | on-accent text on primary button | 7.78 | 4.5 | pass |
| dark | on-accent text on button hover | 9.59 | 4.5 | pass |
| dark | on-accent text on button pressed | 11.24 | 4.5 | pass |
| dark | success status dot on base | 8.99 | 3.0 | pass |
| dark | warning status dot on base | 9.34 | 3.0 | pass |
| dark | danger status dot on base | 7.28 | 3.0 | pass |
| dark | danger notice rule on base | 7.28 | 3.0 | pass |
| dark | control border on base | 4.37 | 3.0 | pass |
| dark | focus ring on base | 7.78 | 3.0 | pass |
| dark | accent bar on selected nav | 6.23 | 3.0 | pass |

`border.strong` (about 1.5:1) is decorative only and is not used for control boundaries. `border.control` is used for buttons now and inputs in 1.2.

## 9. Run it (Windows PowerShell, from the repository folder)

```powershell
# remove files that this package replaces (ignore errors if a path is already gone)
Remove-Item -Recurse -Force apps\web\src\features\system -ErrorAction SilentlyContinue
Remove-Item -Force apps\web\src\app\SettingsPage.tsx -ErrorAction SilentlyContinue
Remove-Item -Force apps\web\src\ui\StatusPill.tsx -ErrorAction SilentlyContinue

# checks
uv sync --all-packages
uv run ruff check . --fix
uv run ruff format .
uv run ruff check .
uv run mypy
uv run lint-imports
uv run pytest
cd apps\web; npm install; npm run check:boundaries; npm run typecheck; npm run build; cd ..\..

# stack
docker compose up --build
```

In a second terminal while compose runs:

```powershell
uv run alembic -c packages/persistence/alembic.ini upgrade head
uv run pytest -m integration
```

Then open http://localhost:5173, http://localhost:8000/readyz, http://localhost:8000/api/docs, and walk through sections 4 and 5.

Git, once everything passes:

```powershell
git branch -M main
git push -u origin main
git checkout -b phase-1/checkpoint-1.1-foundation
git add .
git status
git commit -m "feat(foundation): add workspace, compose stack, migrations, fail-fast config and app shell"
git push -u origin phase-1/checkpoint-1.1-foundation
```

Open the pull request, wait for CI, squash merge. See [git-workflow.md](../engineering/git-workflow.md).

## 10. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `uv.lock` not found during build | Lockfile not generated | Run `uv sync --all-packages`, then build again |
| `required variable APP_DB_PASSWORD is missing` | `.env` missing or empty value | Create `.env` from `.env.example` |
| API cannot log in as `provenance_app` | Database volume was created with other passwords | `docker compose down -v`, then `docker compose up --build` (deletes local data) |
| Port 5433, 8000 or 5173 in use | Another program uses it | Stop it or change the published port in `compose.yaml` |
| Web shows "API unreachable" | API still starting or unhealthy | `docker compose logs api`, then Check again |
| `validation error ... SECRET_KEY` | Missing or shorter than 32 characters | Generate with `uv run python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| Integration tests skip | No `.env` found | Create `.env` in the repository root |
| Web container fails after changing `package.json` | The `node_modules` volume holds the old install | `docker compose down`, `docker volume rm provenance_web_node_modules`, `docker compose up --build` |

## 11. Document

[ADR-0018](../adr/0018-development-stack-conventions.md), [ADR-0019](../adr/0019-frontend-architecture-and-boundaries.md) with addendum, [UX specification](../product/ux-specification.md), [AI UX patterns](../product/ai-ux-patterns.md), [design system](../architecture/design-system.md), [git workflow](../engineering/git-workflow.md), [PostgreSQL provider record](../providers/postgres.md).

## 12. Commit

```
feat(foundation): add workspace, compose stack, migrations, fail-fast config and app shell
```

## 13. Interview defense

You should be able to explain:
- Why the application connects as a different database role than the one that runs migrations, and what that has to do with Row Level Security.
- What liveness and readiness each answer, and why readiness checks migrations.
- Why configuration fails at startup, and why secrets have no defaults.
- What a lockfile guarantees.
- Why SQL in migrations is written as literal strings, and what a linter rule like S608 is protecting against.
- How the frontend boundary rule is enforced, and why settings is a feature and not part of `app/`.
- Why content is not wrapped in cards, and how hierarchy is built without them.
- How frontend states stay consistent with backend states (one vocabulary, derived states listed, generated types).
- What your consistency review found, and why resolving conflicts in documents beats choosing silently.
