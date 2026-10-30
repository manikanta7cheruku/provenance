# ADR-0028: Design system implementation

Status: Accepted (checkpoint 1.5). Builds on [ADR-0019](0019-frontend-architecture-and-boundaries.md). The visual rules are in [design-system.md](../architecture/design-system.md).

## Context
Checkpoint 1.1 shipped minimum tokens and six primitives. Checkpoint 1.4 added data screens whose styles used raw values (fixed hex colors, `color-mix`, `Canvas`) and a deferred promise: tokens, fonts, both themes and automated accessibility checks arrive in 1.5. The product must not look like a generic template, must work in light and dark, and must stay accessible while many screens are added.

## Problem
How do we implement tokens, themes, fonts, primitives and accessibility checks so that a wrong value or a regression is caught by a machine, not by review?

## Options considered
| Question | Options | Result |
|---|---|---|
| Theme tokens | Two full blocks of variables (one under a media query, one under an attribute) or `light-dark(light, dark)` per token | `light-dark()`. One declaration per token, the theme switch only changes `color-scheme`. No duplicated dark block that can drift |
| Theme storage | Cookie, localStorage, none | localStorage, wrapped in try/catch. A blocked store falls back to the operating system preference. The applied attribute on `<html>` is the source of truth |
| Flash of wrong theme | Inline script, same-origin file, none | A small synchronous file `public/theme-init.js`. Same origin, so a strict Content-Security-Policy can allow it without `unsafe-inline` |
| Fonts | Google Fonts CDN, self-hosted via @fontsource, system fonts only | Self-hosted via @fontsource (SIL Open Font License 1.1). No third-party request, no privacy leak, works offline. Latin subset only. Other scripts fall back to system fonts |
| Components | A component library, or our own primitives on native elements | Our own, on native elements (`<dialog>`, radio inputs, `<details>`, `<input type="file">`). Fewer dependencies and the browser supplies focus and keyboard behavior |
| Accessibility checks | Manual only, jsdom axe, real browser axe | Real browser (Playwright with axe-core). jsdom cannot compute contrast or layout |
| Contrast | Trust the eye, check by hand once, compute in CI | A script computes WCAG 2.2 ratios from `tokens.css` for every pair the UI uses, in both themes, and fails the build below threshold |
| Raw values | Convention only, or a check | A script fails the build on hex, rgb, hsl, `color-mix`, raw shadows and raw font stacks outside `tokens.css` |

## Decision
1. `src/ui/tokens.css` is the only place raw values live. Every color is `light-dark(...)`. `:root[data-theme="light"|"dark"]` sets `color-scheme`; no attribute means "follow the system".
2. Theme choice is `system | light | dark`, stored under `pv-theme` in localStorage (system removes the key). `public/theme-init.js` applies it before first paint. `lib/theme.ts` is the only code that reads or writes it. The two files must use the same key and values.
3. Fonts: IBM Plex Sans (interface), Newsreader (display), IBM Plex Mono (data), imported from `@fontsource/*` in `ui/fonts.css` with only the weights used.
4. Primitives added or reworked: Dialog (native `<dialog>`, ConfirmDialog is built on it), Skeleton, SegmentedControl, TextArea, Select, Checkbox, FileDrop, a themed table, themed action buttons. They hold no data fetching, routing or product vocabulary.
5. Checks in CI (job `web`): `check:tokens`, `check:contrast`, unit tests (Vitest, jsdom), and browser tests (Playwright) that run axe against the component gallery, both prototypes and every existing screen (with a mocked API) in both themes. A negative control proved that axe flags a deliberate contrast failure.
6. The two critical screens exist first as interactive prototypes at `/design/workbench` and `/design/job`, built from the real tokens and primitives, with sample data and every state. They need no sign-in and no API. The real screens are built in 1.9 and 2.8.

## Why
The decision moves correctness from convention to machines: a wrong color, a missing theme value, a contrast regression or an inaccessible new screen fails CI. Native elements keep the dependency list short and the behavior standard.

## Consequences
- `light-dark()` needs a browser from 2024 or later (Chrome 123, Firefox 120, Safari 17.5). The target audience is students on current phones and laptops. If analytics later show older browsers, a fallback block can be added in `tokens.css` only.
- The design routes ship with the app. They hold sample data only. Hiding them in production is a choice for 3.7.
- Playwright needs a browser: CI installs Chromium. On a developer machine set `PW_CHANNEL=msedge` (or `chrome`) to reuse an installed browser.
- The seven bundled woff2 font files total about 146 KB. Older woff copies are also bundled as a fallback and are not downloaded by current browsers. A page downloads only the weights it uses.
- Not covered by automation: screen reader behavior, Firefox and Safari rendering, real touch devices. These are manual passes at 3.7.

## Scale analysis
| Users | Posture |
|---|---|
| 10 | Static assets from the web container |
| 100 | Same, with long cache headers for hashed assets |
| 10,000 | A CDN in front of the static assets. No design change |

## Revisit when
A required browser does not support `light-dark()`, a screen needs a component the native elements cannot provide, or a font licence or file size becomes a problem.
