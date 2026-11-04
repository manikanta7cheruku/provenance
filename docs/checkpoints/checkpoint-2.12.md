# Checkpoint 2.12: Touch and phone editing

Phase 2, Resume studio and job sources. Branch `phase-2/checkpoint-2.12-touch-editing`, built on 2.11. Decision: [ADR-0044](../adr/0044-touch-and-phone-editing.md). Builds on the canvas editor ([2.2](checkpoint-2.2.md)).

## What this checkpoint is for
The owner asked to edit a resume on a phone or tablet. Until now the canvas was read-only on a narrow screen. This checkpoint makes it editable with a finger.

## 1. Build
- Editing at every width. The read-only note is gone. Tools, pages and properties stack on a narrow screen.
- One finger on an element drags it. One finger on empty paper scrolls. Two fingers zoom the page.
- Double tap on text edits it (more time and room than a mouse).
- Finger controls when the main pointer is coarse: a selection bar (Edit text, Duplicate, Delete, move left, up, down, right by 1 mm), 44 pixel buttons and handle targets, 16 pixel text in the properties, a toolbar that scrolls sideways.
- No server, database or API change.

## 2. UX
- Nothing is lost: every mouse and keyboard action still works.
- On a phone an empty press never starts a selection box that would block scrolling.
- Moves by button are announced to screen readers.

## 3. Technical acceptance criteria
1. At 390 pixels wide the editor shows, with no sideways page scroll.
2. A tap selects. The selection bar appears only for a coarse pointer and when something is selected.
3. A finger drag moves an element. A pinch changes the zoom and nothing in the document.
4. The pinch stays between 25 and 300 percent.
5. Edit text, Duplicate, Delete and the four moves work without a keyboard.
6. Mouse and keyboard behaviour is unchanged (the earlier browser tests pass).

## 4. Accessibility acceptance criteria
Axe finds no WCAG 2.2 A or AA violation on a phone with an element selected, in light and dark. The selection bar is a labelled toolbar and each button names its action.

## 5. Test
| Where | What |
|---|---|
| `src/features/studio/canvas/engine.test.ts` | pinch maths and limits |
| `e2e/touch.spec.ts` | emulated touch: layout, tap, buttons, drag, pinch, axe in both themes |

## 6. Not verified
A real phone or tablet (the tests emulate touch events), a screen reader on a phone, iOS Safari, a stylus. See carryover M.
