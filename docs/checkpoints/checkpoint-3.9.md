# Checkpoint 3.9: The resume experience

Phase 3, the design and experience checkpoints. Branch `phase-3/checkpoint-3.9-resume-experience`. Decision: [ADR-0047](../adr/0047-the-resume-experience.md). Builds on the foundation of [3.8](checkpoint-3.8.md) and the canvas editor ([2.2](checkpoint-2.2.md)).

## What this checkpoint is for
The owner asked for an easy, excellent and accessible way to create and edit a resume. This checkpoint reworks how a resume is started and how the editor feels to use. It does not change what the editor can do with a resume or any stored data.

## 1. Build
- **Start in three steps** with large choice cards (profile or blank, free design or ATS-safe guided, a design) and sensible defaults, so one click starts.
- **Command palette** (Ctrl or Command K, or the Commands button) over every editor action, resume actions and "Go to" any element.
- **Calm toolbar:** selection tools float over the page when something is selected and are gone otherwise. Selecting never moves the page.
- **Recent changes:** a labelled history with "Go back to here", several steps at once.
- **Focus on the page:** hides the side panel and returns it.
- **Page labels** ("Page 1 of 2") above every page.
- **Unsaved edits** ask before leaving. A saved resume never asks.
- **A speed budget test:** no interaction of 200 ms or more while dragging and typing.
- New UI kit parts: `ChoiceCards` and `CommandPalette`.
- No server, database or API change.

## 2. UX
- The start screen reads top to bottom as a short story and needs no decisions to finish.
- A keyboard user can do anything from one key press (Ctrl K) and a few letters.
- Nothing jumps: the page stays where it is when tools appear.
- Undo is something you can see and use, not only a button.

## 3. Technical acceptance criteria
1. Starting from defaults takes one click and produces a canvas resume with the profile's words.
2. The start choices are radio buttons with arrow-key movement.
3. Ctrl K opens the palette from anywhere on the editor, focus is in the search field, and Escape returns focus.
4. Commands that cannot run are not listed. Every word typed must match.
5. Selecting an element does not change the position of the page.
6. Going back several steps restores the document exactly as it was before them.
7. Leaving with unsaved edits is intercepted. A saved resume is not.
8. No interaction during a drag or typing run takes 200 ms or more.
9. All earlier tests pass.

## 4. Accessibility acceptance criteria
Axe finds no WCAG 2.2 A or AA violation on the start screen, the editor with something selected, the palette, recent changes and focus mode, in light and dark. The palette is a modal dialog with a labelled combobox and listbox, `aria-activedescendant`, an announced match count and returned focus. Each "Go back to here" button names the change it goes back before. The choice cards are a fieldset with a legend and descriptions.

## 5. Test
| Where | What |
|---|---|
| `src/features/studio/canvas/experience.test.ts` | command filtering and labelled history (13 tests) |
| `e2e/experience.spec.ts` | the whole flow in the browser with axe in both themes, and the speed budget (15 tests) |
| existing suites | studio, canvas, templates, pictures, touch, themes, design |

## 6. Not verified
Real people using it (no usability session was run), real devices and slow machines, a screen reader on the palette and the start cards, drag to reorder (not built, see the ADR), and the guided editor beyond its start screen (its editing screens are unchanged).

## 7. What is next
3.10, the whole product on the new foundation.
