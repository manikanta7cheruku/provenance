# ADR-0046: Design foundation and brand

Status: Accepted (checkpoint 3.8). Amends ADR-0028 and the Direction and Excluded lists of the design system.

## Context
Phase 1 and 2 built a calm, accessible, token-based interface. The owner asked for a premium, professional look that does not resemble a template or an AI product, a professional color palette with one gradient, and a smooth feel. The design system said gradients, glow and large radii were excluded and that the accent was the single brand color. Those rules were right for a research workbench and are too plain for a product people choose. They also mean the interface has no identity beyond a name in serif type.

## Decision

**Identity: ink and paper.** Warm paper surfaces, deep ink-blue for structure and actions, brass for the one thing to notice. Editorial serif (Newsreader) for titles and the brand, IBM Plex Sans for the interface, Plex Mono for data. The fonts are unchanged: they are self-hosted, distinctive and already tested. The tone is confident and quiet. Nothing in the interface calls itself AI, magic or smart, and there are no sparkles, robots, chat bubbles, glow or stock illustrations.

**Proportions, 60-30-10.** Sixty percent paper (the surfaces), thirty percent ink-blue (text, navigation selection, primary actions, links, focus), ten percent brass (a rule under every page title, the selected-item marker, selection color, the dot in the brand mark). Brass is never a large area.

**The palette** (every value is a `light-dark()` token in `tokens.css`, so a later change is one file):

| Role | Light | Dark |
|---|---|---|
| Paper (base, raised, sunken) | `#faf8f4`, `#ffffff`, `#f1eee7` | `#0e1116`, `#151a22`, `#0a0d12` |
| Ink (text, secondary) | `#14202e`, `#4a5565` | `#e9ecf1`, `#a3acb9` |
| Ink-blue (accent, hover, active, tint) | `#1f3a5f`, `#182e4c`, `#11223a`, `#e7ecf4` | `#9db8e6`, `#b3c9ee`, `#c6d7f3`, `#1b2740` |
| Brass (text, tint, line) | `#8a5a0b`, `#f5e6c4`, `#b07a1e` | `#e2b25c`, `#2e2410`, `#c99a3e` |
| Status (success, warning, danger, info) | `#1f6b44`, `#8a5a0b`, `#a6372b`, `#25607f` | `#7cc49a`, `#e0b15c`, `#ec9488`, `#86bdd9` |

Every used pair is checked by `npm run check:contrast` (96 pairs, light and dark). Text is at least 4.5:1, borders of controls and decorative marks that carry meaning at least 3:1.

**One gradient, "dusk".** Ink-blue `#1f3a5f` to deep teal `#0f6b6b` at 135 degrees, a token (`--gradient-dusk`). It is used at most once on a screen: the brand mark now, and later a welcome moment and a progress ring. Text on it is a fixed white (11.5:1 and 6.3:1 at its two ends), in both themes, and the contrast check covers both ends.

**A brand mark.** A rounded square in the gradient holding a "P" made of a stem and a bowl, with a brass dot where a receipt would be punched ("Jobs, with receipts"). It is an inline SVG that takes its colors from tokens, hidden from assistive technology because the word sits next to it, and it is also the favicon.

**Shape, depth and motion.** Radii 4, 8 and 14 pixels (small, controls and panels, dialogs). Three elevation steps: flat with a hairline, raised (a soft two-layer shadow), overlay. Motion is short and purposeful: 140 ms, 220 ms and 360 ms, a standard curve and an emphasis curve, a dialog that rises a few pixels as it opens, a one pixel press on buttons, fields that gain a soft ring on focus. `prefers-reduced-motion` still removes all of it.

**Type.** A display step (2.5 rem, tight leading and tracking) joins the scale for the brand and welcome moments. Titles use tighter tracking.

**Voice.** Plain, specific and calm. Say what happened and what to do. No exclamation marks, no filler, no cleverness at the cost of clarity. Written in `docs/product/voice-and-tone.md`.

## Alternatives considered
- **A cool saturated look (purple or violet with gradients, glass, glow).** Rejected: it is the look of most AI products and templates, which the owner asked to avoid.
- **A dark navigation sidebar in both themes.** Deferred to 3.10: it needs a second set of nav-scoped color roles and a pass over everything inside it. A light, quiet sidebar with a brass marker gives the identity without that cost now.
- **New fonts.** Rejected for now: the current pair is distinctive, self-hosted and covered by tests. A change is possible later because the fonts are tokens.
- **Gradients on buttons and cards.** Rejected: one gradient used rarely is memorable, many are decoration.
- **Cards everywhere.** Rejected: hierarchy still comes from type, spacing and hairlines.

## Consequences
- The palette is a proposal the owner approved on the condition that it can be changed. It can: one file, and the contrast check says at once if a change breaks readability.
- Colors in the resume canvas (paper, template palettes) are separate and unchanged.
- Existing screens inherit the new look through tokens but have not been redesigned. That is 3.9 and 3.10.
- Brass on paper at small sizes is only used for text when it passes 4.5:1 (it does: 5.6:1). The brass line (3.5:1) carries no information alone.

## Evidence
`npm run check:contrast` for the 18 new pairs and all old ones. `check:tokens` shows no raw values outside `tokens.css`. The design gallery shows the brand, the proportions, the gradient and the three elevation steps, and axe scans it in light and dark. The full browser suite (every screen, in light and dark, with axe) passes on the new tokens.
