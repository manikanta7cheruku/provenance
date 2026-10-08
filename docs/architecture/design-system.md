# Design System Specification

Status: Decided (Phase 0). Values are proposals to be tuned in checkpoint 1.5 and verified against WCAG 2.2 AA contrast with a checker before they are final.

## 1. Direction

A calm, dense, professional workbench. Closer to a research tool than a marketing dashboard. References for interaction quality only: Linear (workflow clarity), GitHub (information density), Notion (structure), Stripe (polish). Nothing is copied visually.

Identity: warm neutral surfaces, one ink-blue accent, a serif for editorial moments (page titles, empty states, report headings), a clean sans for the interface, a mono face for data such as ids and counts. The serif is what keeps it from looking like a default SaaS template.

Hard exclusions: gradients as decoration, glow, glassmorphism, oversized hero stats, donut charts, floating AI orbs, purple-blue AI palette, emoji in UI, large rounded cards, heavy shadows, decorative animation, chat-first navigation.

## 2. Tokens (semantic, never hardcoded in components)

### Typography
| Role | Family (self hosted, open licensed, verify license at adoption) | Use |
|---|---|---|
| Display | Newsreader | Page titles, empty states, report headings |
| UI | IBM Plex Sans | Interface text |
| Data | IBM Plex Mono | Ids, counts, run traces |

Scale (rem): 0.75, 0.8125, 0.875 (base for dense tables), 1, 1.125, 1.375, 1.75, 2.25. Line heights 1.25 to 1.5. Weights 400, 500, 600.

### Spacing, radius, elevation
- Spacing: 2, 4, 6, 8, 12, 16, 24, 32, 48 px.
- Radius: 3, 6, 10 px. Default 6. No pill shapes except small chips.
- Elevation: borders first. One subtle shadow token for popovers and dialogs only.

### Color (light proposal, dark mirrors through the same semantic names)
| Token | Light | Dark |
|---|---|---|
| surface.base | #FAF9F6 | #131412 |
| surface.raised | #FFFFFF | #1B1C1A |
| surface.sunken | #F2F0EB | #0F100F |
| border.subtle | #E6E3DC | #2A2C28 |
| border.strong | #CFCBC1 | #3C3E39 |
| text.primary | #1C1B19 | #ECEAE4 |
| text.secondary | #5B5850 | #A8A59B |
| accent.default | #2B4A8B | #8FA8E0 |
| accent.subtle | #E8EDF7 | #1E2740 |
| success | #2F6B45 | #7CC49A |
| warning | #8A5A12 | #E0B15C |
| danger | #A6372B | #E58A7E |
| info | #2B5E7A | #7FB6D4 |
| focus.ring | accent.default at 2px with 2px offset | same |

Verdict colors reuse success, warning, danger, info plus a neutral for Not verified. Color is never the only signal: every status has text and a shape or icon.

Dark mode ships only if every screen passes contrast checks in both themes. Otherwise it ships later. It is not added as a checkbox.

## 3. Density

Two densities: Comfortable and Compact. Compact is the default for the work queue (row height about 36 px). Whitespace is deliberate. The authenticated app has no oversized hero sections.

## 4. Components (each needs all states)

Buttons (primary, secondary, ghost, danger), inputs, selects, combobox, checkbox, switch, tabs, table with sortable headers and sticky header, badges and chips (sparingly), tooltip, popover, dialog, drawer and detail pane, toast, inline alert, skeleton, empty state, error state, quota state, progress (only with real denominators), evidence card, verdict row, run trace list, keyboard shortcut hint.

States: default, hover, focus-visible, active, disabled, loading, error, selected.

## 5. Layout

```
+---------+--------------------------------------------+
| Nav     |  Toolbar: search, filters, saved views      |
| Opportunities                                         |
| Saved   +----------------------+---------------------+
| Applications  Work queue table |  Detail pane        |
| Profile |  (keyboard driven)   |  (persistent)       |
| Runs    |                      |                     |
| Settings+----------------------+---------------------+
```

Tablet: detail pane becomes a drawer. Mobile: queue becomes structured rows, detail becomes its own screen, navigation becomes a bottom bar. The desktop layout is not squeezed onto mobile.

## 6. Keyboard map

| Key | Action |
|---|---|
| Up, Down (or J, K) | Move selection |
| Enter | Open detail |
| S | Save |
| D | Dismiss |
| P | Prepare |
| A | Mark applied (opens confirmation) |
| / | Focus search |
| ? | Show shortcuts |
| Escape | Close detail or dialog |

Shortcuts never replace visible controls. They are disabled while typing in inputs.

## 7. Motion

Used only to communicate state change (row inserted, panel opening, status updating). Short durations, `prefers-reduced-motion` respected, no looping decoration.

## 8. Accessibility

Semantic HTML, labeled controls, visible focus, accessible dialogs and tables, live regions for status messages, 4.5:1 text contrast and 3:1 for UI components minimum, keyboard complete, error text associated with fields, tested with axe in CI and manual screen reader pass on key flows.

## 9. Copy

Plain, specific, honest. No em dashes. Empty states answer what, why, next. Errors answer what happened, is my data safe, will it retry, what can I do. Predictions use hedged language.

## 10. Implementation notes

Tokens are CSS custom properties. Tailwind is configured to read them. Radix primitives or equivalent for accessible behavior. A single `tokens.css` is the source. A component gallery page (dev only) shows every component in every state in both themes.
