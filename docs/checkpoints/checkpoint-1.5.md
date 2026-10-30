# Checkpoint 1.5: Design system, themes and the two critical screens as prototypes

Phase 1, Foundation and Core Intelligence. Branch `phase-1/checkpoint-1.5-design-system`. Decisions: [ADR-0028](../adr/0028-design-system-implementation.md).

Roadmap revision 2 split the old 1.5 in two. This checkpoint is the design half. Resume upload, parsing and the profile are checkpoint 1.6.

## 1. Build

**Tokens (`apps/web/src/ui/tokens.css`).** Every color is one `light-dark(light, dark)` declaration. New roles: `danger-fill`, `text-on-danger`, `backdrop`, `skeleton`, `size-detail-pane`, `size-dot`. Typography tokens now name the self-hosted fonts first and fall back to system stacks.

**Themes.** Light, dark and system. The choice is stored under `pv-theme` in localStorage. `public/theme-init.js` runs synchronously in `<head>` so the stored theme is applied before first paint. `lib/theme.ts` (`useTheme`, `saveTheme`, `applyTheme`) is the only code that touches the key. A theme control (a segmented control) sits in the application shell and in the design routes. If storage is blocked the choice still applies for the visit and the operating system preference is used on the next one.

**Fonts.** `@fontsource/ibm-plex-sans` (400, 500, 600), `@fontsource/newsreader` (500 and 500 italic), `@fontsource/ibm-plex-mono` (400, 500), Latin subset, imported in `ui/fonts.css`. All three are SIL Open Font License 1.1 (licence files ship in each package). No request leaves the origin.

**Primitives (`apps/web/src/ui`).** New: `Dialog` (native `<dialog>`), `Skeleton`, `SegmentedControl` (native radios), `TextArea`, `Select`, `Checkbox`, `FileDrop` (native file input plus drag and drop, browser-side type and size checks that the server will repeat). Reworked onto tokens: `ConfirmDialog` (now built on `Dialog`), `DataTable` (header style, numeric columns, selected row with an accent bar), `ActionButton` (primary and danger fills with computed contrast), `TextField` (now forwards its ref). `data.css`, `admin.css` and `runs.css` no longer contain raw values. The settings key-value table is now `kv-table`.

**Design routes (no sign-in, no API).** `/design` is the component gallery: colors, type scale, buttons, status, notices, fields, segmented control, file drop, table, dialog, skeleton and empty state. `/design/workbench` prototypes the opportunities workbench with sample data: filters, dense table, persistent detail pane, keyboard flow (J, K, S, D, /, ?), save and dismiss with undo, and a state switcher (populated, loading, empty, error). `/design/job` prototypes the trust screen: provenance line, summary, eligibility checks in words, requirement-by-requirement analysis with the posting quote, direct, inferred, missing and conflicting evidence, confidence with a reason, what is missing, suggestions, a gap-to-qualify plan and a "was this right?" form. Four kinds of statement (the posting says, direct evidence, inferred, suggestion) differ by label, rule style and typography, never by color alone. All sample names are invented.

**Machine checks.** `npm run check:tokens` (no raw colors, shadows or font stacks outside `tokens.css`), `npm run check:copy` (no em dashes, sparkle emoji or stock AI-template phrases in the repository), `npm run check:contrast` (70 WCAG pairs, both themes), `npm test` (Vitest, 28 tests), `npm run test:e2e` (Playwright and axe-core, 32 tests). `.\scripts\pv.ps1 test` runs the first three plus the existing checks. `.\scripts\pv.ps1 webtest` runs the browser tests.

## 2. UX

- A user can choose System, Light or Dark in the shell. The choice survives reload and never flashes the wrong theme.
- Page titles are the display serif everywhere. Data is set in tabular figures. Status is a dot and text with a different shape per tone.
- The two critical screens can be reviewed in a browser before the real ones are built. Review them at `/design/workbench` and `/design/job` in both themes and at a narrow width.
- Prototype limit: below 900px the detail pane stacks under the table and the table scrolls inside its own region. The real workbench (2.8) uses a drawer at medium width and structured rows on compact, as the design system specifies.

## 3. Technical acceptance criteria

1. Every color token is a light and dark pair and `npm run check:contrast` passes all 70 pairs (text 4.5:1, controls and focus 3:1).
2. `npm run check:tokens` passes: no raw values outside `tokens.css`.
3. No request goes to another origin and all three font families are declared from files bundled in the build.
4. The stored theme is applied before first paint (test reads `data-theme` at `DOMContentLoaded`), persists across reload, and "System" removes the key.
5. Axe finds no WCAG 2.2 A or AA violation on the gallery, both prototypes (including every workbench state and every opened requirement) and the existing screens (sign in, sign up, forgot password, opportunities, runs, settings, admin users) in both themes.
6. A negative control shows axe does fail when contrast is broken on purpose.
7. `ConfirmDialog` and `Dialog` use the native `<dialog>`. Focus starts on Cancel, never escapes the dialog, Escape closes it and focus returns to the trigger.
8. Unit tests, type check, boundaries, states and the production build pass. CI runs all of them in job `web`.

## 4. UX acceptance criteria

1. All of the following exist as an in-product example: loading (Skeleton with a named label), empty (what, why, next), error (what happened, is my data safe, retry), populated, selected, disabled, invalid, busy.
2. A reviewer can see in the job prototype what the requirement is, whether it is met, the proof and where it came from, how confident the system is and why, what is missing, and what to do next, without any developer view.
3. Reversible actions (save, dismiss) use undo in a polite live region instead of a confirmation.
4. The file drop says what is accepted and why, rejects the wrong type with a sentence that says what to do, and keeps the keyboard path (the native file input).

## 5. Accessibility acceptance criteria

1. Visible 2px focus ring on every interactive element (tested on a button).
2. The segmented control, filters and file input are keyboard operable with native behavior (radio arrow keys, Tab).
3. The skeleton pulse stops under `prefers-reduced-motion` (tested).
4. Tables have captions and `scope` headers. The current row uses `aria-current`. Status never relies on color alone.
5. Selected and disabled states have a non-color cue. `forced-colors` has explicit rules.

## 6. Test

| Where | What |
|---|---|
| `src/lib/theme.test.ts` | parsing, apply, persist, blocked storage, the hook |
| `src/ui/FileDrop.test.tsx` | size and type rules, error wiring, selection |
| `src/ui/controls.test.tsx` | segmented control semantics and arrow keys, field wiring, skeleton |
| `src/features/design/fixtures.test.ts` | sample data invariants (no em dashes, Met needs direct evidence) |
| `e2e/design.spec.ts` | axe on the design routes, themes, fonts, dialog, keyboard flow, filters, file drop, reduced motion, focus ring |
| `e2e/app-screens.spec.ts` | axe on every existing screen with a mocked API, in both themes, and the shell theme control |
| `scripts/check-contrast.mjs`, `scripts/check-tokens.mjs` | design rules as build checks |

## 7. Document

[ADR-0028](../adr/0028-design-system-implementation.md), [design-system.md](../architecture/design-system.md) (theme, fonts, components, checks), [ux-specification.md](../product/ux-specification.md) (prototype status), [operator-commands.md](../operations/operator-commands.md) (`webtest`), CI workflow.

## 8. Commit

```
feat(web): add design system, light and dark themes, self-hosted fonts and accessibility checks
```

## 9. Interview defense

You should be able to explain:
- Why one `light-dark()` declaration per token is safer than two blocks of variables.
- How the theme choice is stored, applied before first paint, and why the script is a same-origin file (Content-Security-Policy).
- How contrast is computed (relative luminance, 4.5:1 for text, 3:1 for control edges and focus) and why it is a build check.
- What axe can and cannot find (it cannot judge whether a label makes sense or whether a screen reader reads the page well) and why it runs in a real browser.
- Why native `<dialog>`, radio inputs and `<details>` are used instead of a component library.
- Why fonts are self-hosted (privacy, speed, no third-party request) and what the licence is.
- Why the prototypes came before the real screens and what they let you check cheaply.
- How the design keeps four kinds of statement (posting, evidence, inference, suggestion) distinct without relying on color.

## 10. What was verified and what was not

**Run in this checkpoint (on a Windows machine, Edge through Playwright):** TypeScript type check, boundary check, state check, token check, contrast check (70 pairs), 28 unit tests, the production build, and 32 browser tests (axe on 3 design routes and 7 product screens in 2 themes, plus behavior tests). Screenshots of the gallery, both prototypes, the shell and a 390px width were inspected by eye; one inconsistent sample number and one clipped table column were found and fixed.

**Not verified:** GitHub CI on the pushed branch (the Linux job installs Playwright's own Chromium, which was not downloaded locally), Firefox and Safari, real touch devices, any screen reader, `docker compose up` with the changed web files, and the product screens against the real API (the browser tests mock it). Python code was not touched, so ruff, mypy, import-linter and pytest were not re-run here, and CI will run them.

Likeliest first-CI problems: Playwright browser install step needing a newer version flag, a font weight file missing after a `@fontsource` update, and axe flagging something only Linux rendering shows (for example a different fallback font width).

## 11. Run it yourself

```powershell
cd apps\web
npm ci
npm run dev            # http://localhost:5173/design
```
Open `/design`, `/design/workbench` and `/design/job`, switch System, Light and Dark, press Tab through the page, press `?` on the workbench. To run all checks: `.\scripts\pv.ps1 test`, then `$env:PW_CHANNEL="msedge"; .\scripts\pv.ps1 webtest`.
