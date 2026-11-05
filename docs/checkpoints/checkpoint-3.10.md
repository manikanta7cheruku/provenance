# Checkpoint 3.10: Whole-product polish

Phase 3, the design and experience checkpoints. Branch `phase-3/checkpoint-3.10-product-polish`. Decision: [ADR-0048](../adr/0048-whole-product-polish.md). Builds on [3.8](checkpoint-3.8.md) and [3.9](checkpoint-3.9.md).

## What this checkpoint is for
The owner said the product did not feel professional enough yet. This checkpoint moves every screen onto the new foundation through the shared pieces (shell, panels, controls, notices, empty states, loading) and checks the feel: hover, press, focus, motion and dark mode. It is a first pass. The owner reviews it and asks for specific changes next.

## 1. Build
- **Navigation:** grouped (Work, Build, System), outline icons, tint plus brass marker for the current page, hover that nudges the icon, an account chip, a compact status.
- **Panels:** every section is a raised panel with a display-serif title. Inner cards use the paper color and a quiet edge.
- **Controls:** hover, press, focus and disabled states for buttons, action buttons, links, table rows, fields, segmented options, choice cards and toolbar buttons. Fields show a soft ring on focus. Placeholder color set.
- **Notices and empty states:** an icon, a colored edge, a medallion.
- **Movement:** a page rises and fades in, loading shapes shimmer, dialogs rise. All stop under reduced motion.
- **Type scale:** 15 px body, 32 px headings, 40 px controls.
- **Sign-in screens:** the form beside a gradient panel that says what the product stands for. The panel is hidden on a phone.
- **Icon set:** 18 outline icons drawn in the product (`Icon`), decoration only.
- **Studio toolbar:** one surface with hairline dividers.
- Page titles are no longer boxed when focused from the program.
- No server, database or API change.

## 2. UX
- Every screen reads as grouped panels with a clear title, instead of text on a page.
- Where you are is clear in the navigation. The pointer, keyboard and finger all get feedback.
- Dark mode is a designed palette with the same structure.
- A phone gets the same grouped menu and no sideways scrolling.

## 3. Technical acceptance criteria
1. A hover changes the appearance of a button, a primary button, a ghost button, an action button, a segmented option, a table row, a text field, a navigation link, a choice card and the start button.
2. Each of the first twenty tab stops on a main screen shows a visible focus.
3. The navigation has three labelled groups, marks the current page with `aria-current`, and its icons are hidden from assistive technology.
4. Sign-in shows the form and, at desktop width, the panel. On a phone the panel is hidden and nothing scrolls sideways.
5. Six main screens do not scroll sideways at 390 pixels.
6. All earlier tests pass.
7. Contrast (96 pairs), token, copy and boundary checks pass.

## 4. Accessibility acceptance criteria
Axe finds no WCAG 2.2 A or AA violation on opportunities, find jobs, profile, runs, settings and sign-in in light and dark, and on every earlier screen. Group labels are decorative and each list is labelled. Icons carry no information alone.

## 5. Test
| Where | What |
|---|---|
| `e2e/polish.spec.ts` | hover on every kind of control, visible focus, grouped navigation, sign-in, phone fit, axe (8 tests) |
| existing suites | every screen with axe in both themes |

## 6. Not verified
Whether people like it. No usability session has been held. Real displays and devices, a screen reader pass, the workbench and job detail layouts (they inherit the new panels and controls but keep their older internal layout), the order of the Opportunities page, a designer's review.

## 7. What is next
The owner reviews the screens and asks for specific changes. Then Phase 3 continues with 3.1 to 3.7.
