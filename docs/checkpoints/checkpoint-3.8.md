# Checkpoint 3.8: Design foundation and brand

Phase 3, Intelligence, Monetization and Production (the design and experience checkpoints, built first). Branch `phase-3/checkpoint-3.8-design-foundation`. Decision: [ADR-0046](../adr/0046-design-foundation-and-brand.md). Voice: [voice-and-tone.md](../product/voice-and-tone.md). Reference: [design-system.md](../architecture/design-system.md).

## What this checkpoint is for
The owner asked for a premium, professional interface that does not look like a template or an AI product. This checkpoint sets the foundation every later screen is built on: a palette, a brand, type, depth, motion and a voice. It does not redesign screens. That is 3.9 and 3.10.

## 1. Build
- **Palette.** Paper, ink-blue and brass in the 60-30-10 proportion, light and dark, as tokens. Status colors retuned to sit on them.
- **One gradient** (dusk, ink-blue to deep teal), as a token, with its fixed white text color.
- **Brand mark** (a rounded square, a "P", a brass dot) as a component and as the favicon, with the line "Jobs, with receipts".
- **Depth and shape.** Radii 4, 8 and 14. Elevation: flat, raised, overlay.
- **Motion.** 140, 220 and 360 ms, a standard and an emphasis curve, a dialog entrance, a button press, a field focus ring. Reduced motion still removes it.
- **Type.** A display step. Tighter tracking on titles.
- **Details.** A brass rule under every page title, a brass marker for the selected navigation item, brass-tinted text selection.
- **Components.** The shell, page header, buttons, fields, dialogs and navigation take the new tokens. The design gallery shows the brand, the proportions, the gradient and the three depths.
- **Voice.** A written guide.
- No server, database or API change.

## 2. UX
- Every page now has the same quiet signature (title, brass rule). Selected navigation is obvious without relying on color alone (a marker, a tint and `aria-current`).
- Focus is visible everywhere. Fields show a soft ring on focus and on hover.
- Dark mode is a first-class palette, not an inversion.

## 3. Technical acceptance criteria
1. Every color is a token. No raw color outside `tokens.css` (`check:tokens`).
2. Every used color pair passes WCAG 2.2 in both themes, including the new roles and both ends of the gradient (`check:contrast`, 96 pairs).
3. The gradient is a token and is used at most once per screen.
4. The brand mark is hidden from assistive technology and carries no information alone.
5. All earlier unit and browser tests pass unchanged.
6. Reduced motion removes all transitions and animations.

## 4. Accessibility acceptance criteria
Axe finds no WCAG 2.2 A or AA violation on the design gallery, the shell and every existing screen, in light and dark. Focus rings, the selected marker and status shapes do not depend on color alone.

## 5. Test
| Where | What |
|---|---|
| `scripts/check-contrast.mjs` | 96 pairs, light and dark |
| `scripts/check-tokens.mjs` | no raw values outside the token file |
| existing vitest and Playwright suites | every screen with axe in light and dark |

## 6. Not verified
Real devices and displays (wide-gamut, low-brightness, glare), a color-blindness simulation of every screen, and the look in the owner's eyes: the palette is a decision the owner confirms by using it. Changing it is one file.

## 7. What is next
3.9, the resume experience, built on this foundation.
