# ADR-0048: Whole-product polish

Status: Accepted (checkpoint 3.10). Amends the design system (Direction, "no cards", empty states, notices, navigation).

## Context
3.8 set the palette, brand and tokens and 3.9 reworked the resume editor. The rest of the product inherited the colors but still looked like a plain text document: no icons, no grouping in the navigation, text sitting directly on the page with no containers, hairline-thin hover feedback, bare notices and empty states, and a sign-in screen that was a column of fields. The owner looked at it and said it did not feel professional enough and that users would not feel good using it.

## Decision

**Panels.** A `Section` is now a panel: a raised surface with a hairline, a large radius, a soft two-layer shadow and the display serif for its title. Each job on a page reads as one thing. This replaces the earlier rule that hierarchy comes from type and rules alone. Cards inside a panel (job sources, sightings, questions) use the paper color with a quiet hairline, so they sit inside rather than compete. A card that needs attention carries a brass left edge.

**Navigation with icons and groups.** The sidebar is grouped (Work, Build, System) with small capitalised labels. Each item has an outline icon from a set drawn in the product (`Icon`: 18 shapes on a 24 grid, no network, color from the text). The current page is shown by a tint, a brass marker and `aria-current`. Hover tints the row and nudges the icon. Icons are decoration, hidden from assistive technology, so the link's name is just its words. The foot of the navigation is an account chip (initial, address, sign out) and the theme and system status.

**Feedback on every control.** A hover, press, focus and disabled state is defined for every kind of control. Buttons darken their edge, primary buttons lift with a soft shadow, links thicken their underline, table rows tint, fields darken their edge on hover and show a soft ring on focus, segmented options and choice cards react, toolbar buttons tint. A browser test hovers one of each kind and fails if nothing changes, and another walks the first twenty tab stops and fails if any has no visible focus.

**Notices and empty states with a face.** A notice is a panel with an icon, a colored left edge and the same message, announced as before. An empty state has an icon medallion above its title. Neither says anything new: they say the same things in a calmer, more finished way.

**Movement.** A page fades and rises a few pixels as it arrives. Loading shapes shimmer instead of pulsing. Dialogs arrive with a short rise. Everything stops under reduced motion by the one rule in the base styles.

**Type scale.** Body text is 15 px (from 14), headings 32 px, section titles in the display serif. Controls are 40 px tall (from 36).

**Sign-in.** The sign-in family of screens puts the form beside a panel that says what the product stands for ("Jobs, with receipts." and three plain statements), on the one gradient. On a phone the panel is hidden and the form is the whole screen. This is the second use of the gradient and the only place it is the main thing on screen. It follows the rule of once per screen.

**The page title is no longer boxed on load.** A heading that receives focus from the program, to announce a new page, shows no ring. It is not a control.

## Alternatives considered
- **A dark sidebar.** Still deferred. It needs its own set of color roles and a pass over what sits inside it.
- **Illustrations in empty states.** Rejected: an icon medallion is enough, and illustrations date quickly and risk looking like a template.
- **Cards with images, big hero sections, animated counters.** Rejected: this is a work tool. Calm and confident beats busy.
- **Changing the order of the Opportunities page** so the list comes before "Add a job". Not done here. It is an information-structure change that deserves its own look with the owner.
- **Redesigning the workbench and the job detail pane.** Not done here. They inherit the panels, controls and states, but their layout is the older design.

## Consequences
- Every screen changes appearance at once, including ones not looked at one by one. The full browser suite with axe in both themes is the safety net.
- Panels add padding, so dense screens are a little longer. The compact density setting still exists.
- The 15 px body text makes everything slightly larger. The design gallery shows each primitive so it can be judged.
- The workbench, job detail, runs detail, admin and settings screens still have older internal layouts inside their new panels. They are listed for the owner's review.

## Evidence
The full browser suite (every screen, light and dark, with axe), the new polish tests (hover on each kind of control, visible focus on twenty tab stops, the grouped navigation with decorative icons and the current page, the sign-in screen with and without the panel, no sideways scroll at 390 pixels on six screens, axe on five screens and sign-in in both themes), the token, contrast and copy checks, and screenshots reviewed by eye in light and dark.
