# Design System

Status: Decided (Phase 0 amendment, foundation implemented in checkpoint 1.1). Visual and interaction half of the **Product UX + Design System Specification**. The experience half is [ux-specification.md](../product/ux-specification.md) and [ai-ux-patterns.md](../product/ai-ux-patterns.md).

The single source of values is `apps/web/src/ui/tokens.css`. Components use token names and never raw values.

## 1. Direction

A calm, dense, professional workbench. Closer to a research tool than a marketing dashboard. Interaction references (not visual copies): Linear for workflow clarity, GitHub for information density, Notion for structure, Stripe for polish.

Identity: warm neutral surfaces, one ink-blue accent, a serif used for page titles and empty states, a plain system sans for the interface, a mono face for ids and counts.

Hierarchy comes from typography, spacing, alignment, hairline rules and progressive disclosure. It does not come from cards. Content sits directly on the page. A bordered container is used only when it groups interactive controls or separates an overlay from the page.

Excluded: gradients, glow, glassmorphism, oversized hero text, donut charts, floating AI orbs, purple-blue AI palettes, emoji in the interface, large radii, heavy shadows, decorative or looping animation, chat-first navigation, badges used as decoration, arbitrary icons.

## 2. Color roles

| Role | Tokens | Use |
|---|---|---|
| Surface | base, raised, sunken | Page, overlays and inputs, inset regions |
| Border | subtle, strong, control | Hairline rules, decorative separation (never for control boundaries), control boundaries at 3:1 or better |
| Text | primary, secondary, disabled, on-accent | Body, supporting text, disabled, text on accent fill |
| Accent | default, hover, active, subtle | The single brand color: links, primary action, selection, focus |
| Status | success, warning, danger, info | Meaning only. Always paired with text and a distinct shape |
| Interaction | hover, pressed, selected, focus, invalid | Derived from the roles above so states stay consistent |

Rules: one accent. Status colors carry meaning and are never decorative. Color is never the only signal. A component may not introduce a new color. A missing role is added to the token file and this document first.

Dark theme follows the operating system and mirrors every role. It ships in 1.1 because every token pair used was checked in both themes (see checkpoint-1.1.md).

## 3. Typography hierarchy

| Role | Token | Size | Family | Weight | Use |
|---|---|---|---|---|---|
| Heading | text-heading | 28px | Display serif | 500 | Page title (one h1 per page) |
| Title | text-title | 20px | Display serif | 500 | Brand wordmark, empty state titles |
| Section | text-body-lg | 16px | UI sans | 600 | Section headings (h2) |
| Body | text-body | 14px | UI sans | 400 | Default text and table cells |
| Small | text-small | 13px | UI sans | 400 | Dense secondary text, shell status |
| Caption | text-caption | 12px | UI sans | 400 | Labels, uppercase with tracking |

Line heights: 1.25 for headings, 1.5 for body. Digits are tabular so numbers align in tables. Measure for reading text is capped at 64 characters. Self-hosted brand fonts (Newsreader, IBM Plex Sans) are decided in 1.5 after the visual prototypes. Until then, system stacks apply, and the type roles above do not change when the fonts do.

## 4. Spacing and sizing

Spacing scale (4px base): 2, 4, 8, 12, 16, 24, 32, 48. Only these values. Sizing tokens: control height 36px (28px compact), touch target 44px, sidebar 232px, content maximum 1100px.

## 5. Density

Two densities. Comfortable is the default. Compact (`data-density="compact"`) reduces control height and row height, and is meant for the work queue and tables. Density changes sizes only, never type roles or colors.

## 6. Borders, radii, elevation

- Borders: 1px hairlines. Subtle for layout, control for the edge of a control.
- Radii: 3px and 6px. No other radii. Dots and avatars are the only circles.
- Elevation: flat by default. A single overlay shadow exists for popovers and dialogs. Nothing else has a shadow.

## 7. Interaction states

Every interactive component defines all of these. A component is not done until each exists in both themes.

| State | Treatment |
|---|---|
| Default | Role colors |
| Hover | Surface changes to the hover role. Primary buttons darken. Never a size or position change |
| Active (pressed) | Pressed role. Primary buttons darken further |
| Focus-visible | 2px accent outline, 2px offset, on every interactive element. Never removed |
| Selected | Selected role plus a 2px accent bar on the leading edge. Not color alone |
| Disabled | Disabled text, subtle border, `not-allowed` cursor, still readable. A disabled control that needs explaining says why in text |
| Invalid | Invalid border plus an error message associated with the field. The message says what to do |
| Loading | A named step or a skeleton. Never an unlabeled spinner. Progress only from persisted counters |

## 8. Breakpoints and responsive behavior

| Name | Width | Behavior |
|---|---|---|
| Compact | below 600px | Single column. Menu in header. Tables become structured rows. Detail is its own screen |
| Medium | 600 to 899px | Single column. Menu in header. Detail opens as a drawer |
| Wide | 900px and up | Sidebar plus content. Split pane with persistent detail |
| Large | 1200px and up | Wider detail panes and more table columns |

CSS variables cannot be used inside media queries, so these values are constants recorded here and used identically in `shell.css` and component CSS.

## 9. Motion principles

Motion communicates a state change and nothing else. Durations come from tokens (120ms and 180ms) and the easing is one curve. Nothing loops or decorates. `prefers-reduced-motion` reduces all durations to near zero. Content never moves in a way that causes layout shift under the user's pointer.

## 10. Component composition rules

1. `ui/` primitives are presentational. They hold no data fetching, no routing and no product vocabulary.
2. Primitives expose semantic props (`tone`, `variant`), not style props. Callers cannot pass colors or sizes.
3. One primary button per view. Everything else is secondary or ghost.
4. Status is shown with the Status primitive (dot and text). Notices are inline with a leading rule, not boxed.
5. Empty states use the EmptyState primitive and answer what, why, next.
6. Page structure is PageHeader, then Sections. Content is not wrapped in containers.
7. A new component needs: all states, both themes, keyboard behavior, and a place in the component gallery (introduced in 1.5).
8. Raw values in component CSS are a defect.

## 11. Components

Built in 1.1: Button (secondary, primary, ghost), Status, Notice, Section, EmptyState, PageHeader. Planned by checkpoint: form controls and validation (1.2), table, tabs, dialog, drawer, evidence item, verdict row, run trace (1.5 and 1.6), toast and confirm (2.5).

## 12. Layout

```
+----------+------------------------------------------------+
| Wordmark | Page title                                     |
| Nav      | Description                                    |
|  ...     | ---------------------------------------------- |
|          | Section                                        |
| Status   | Content                                        |
+----------+------------------------------------------------+
```

Wide: fixed sidebar and a scrolling content area. The wordmark and the page title share a baseline. Opportunities adds a persistent detail pane at Wide in 1.6. Below 900px the sidebar becomes a toggled menu.

## 13. Keyboard map

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

Shortcuts never replace visible controls, are disabled inside text fields, and are discoverable.

## 14. Accessibility

Semantic HTML, labeled controls, visible focus, accessible dialogs and tables, polite live regions, 4.5:1 text contrast and 3:1 for control boundaries and focus, keyboard completeness, associated error text, reduced motion. Automated checks (axe) arrive in 1.5. Manual keyboard and screen reader passes happen at 3.7.

## 15. Copy

Plain, specific, honest. Sentence case. No em dashes. Empty states answer what, why, next. Errors answer what happened, is my data safe, will it retry, what can I do. Predictions use hedged language.

## 16. Contrast findings

Token pairs are computed against WCAG 2.2 (see [checkpoint-1.1.md](../checkpoints/checkpoint-1.1.md)). `border.strong` fails 3:1 for control boundaries, so `border.control` exists and `border.strong` is decorative only.
