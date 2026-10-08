# ADR-0019: Frontend architecture and boundaries

Status: Accepted (checkpoint 1.1)

## Context
UX is a first-class workstream. The frontend must be organized so the design system, the screens and the data access evolve without tangling, and so the UI and backend share one vocabulary for states.

## Problem
Decide the frontend structure, routing, styling approach and how backend state definitions reach the frontend, without building product screens that belong to later checkpoints.

## Options considered
1. Structure: by type (components, hooks, pages) versus by area (ui, lib, features, app).
2. Routing: React Router versus a file-based framework (Next.js).
3. Styling: CSS custom properties as tokens versus a CSS-in-JS library versus a component library now.
4. State vocabulary: hand-written TypeScript types versus types generated from the backend OpenAPI schema.

## Decision
1. Four areas under `src/`: `ui` (presentational primitives and tokens), `lib` (API client, utilities), `features` (one folder per product area with its data and screens), `app` (shell, routes, navigation). Rules: `ui` imports nothing outside `ui`; `lib` nothing outside `lib`; a feature imports only `ui`, `lib` and itself, never another feature; `app` may import anything. A script (`npm run check:boundaries`) enforces this in CI.
2. React Router in a single-page app. No server rendering is needed behind sign-in.
3. Design tokens as CSS custom properties in one file, used through semantic names. No component library in 1.1. Accessible primitives (for example Radix) are chosen in checkpoint 1.5 when dialogs and menus are first needed.
4. Shared state vocabularies (task and run states, verdicts, evidence kinds, origins) are defined once in the backend and exposed through OpenAPI. The frontend generates its types from the schema starting in checkpoint 1.4, so the two cannot drift.

## Why
- Area-based structure keeps the design system portable and keeps feature code local.
- A mechanical rule survives staff turnover and tiredness better than a convention.
- Tokens as CSS variables give theming, dark mode and a single source of truth with no runtime cost.
- Generating types removes a whole class of "backend says X, UI shows Y" bugs.

## Consequences
- Cross-feature reuse requires promoting code to `ui` or `lib`, which is intentional friction.
- Until 1.4 the single status type in `lib/api.ts` is hand-written. It is small and replaced by generated types.

## Scale analysis
| Users | Posture |
|---|---|
| 10 | Single bundle, no code splitting |
| 100 | Route-level code splitting if bundle size grows |
| 10,000 | CDN for static assets, caching headers, possibly separate deployment of the SPA |

## Revisit when
A feature needs server rendering (public marketing pages), or the boundary rules block legitimate reuse often.

## Addendum (checkpoint 1.1 review)

1. `app/` is composition only: providers, routes, the shell, navigation and global concerns. Product screens do not accumulate there. The Settings screen is the `settings` feature. A first draft placed it in `app/`, which this addendum corrects.
2. Shared frontend infrastructure that renders no UI (for example the API status state) lives in `lib/`, so several features and the shell can use it without importing each other. `lib/system-status.tsx` is the first example.
3. The system status table is part of the `settings` feature. The shell's status indicator is a shell concern in `app/`.
4. Copy for screens that are not built yet lives in `features/planned`, not in `app/`. Each entry is deleted when its real screen ships.
5. Styling: plain CSS with custom-property tokens. Whether to adopt a utility framework is decided in checkpoint 1.5 and is accepted only if it is configured from the tokens and cannot introduce raw values. This supersedes the earlier mention of Tailwind in the architecture overview.
