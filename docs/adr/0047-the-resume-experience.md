# ADR-0047: The resume experience

Status: Accepted (checkpoint 3.9).

## Context
The studio worked but felt like a tool panel. The start screen was two segmented controls and a gallery with no sense of order. In the editor a wall of about thirty buttons sat above the page at all times, most of them disabled until something was selected. There was no quick way to find an action, the undo history was invisible beyond two buttons, nothing said which page was which, and leaving with unsaved edits did nothing. The owner asked for an excellent, easy, accessible way to create and edit a resume.

## Decision

**A start in three steps.** One screen, in order: where the words come from (my profile or a blank page), how to work (free design or guided and ATS-safe), and which design. Each choice is a large card with a plain sentence, built from real radio buttons in a fieldset (arrow keys, group and description read by a screen reader, the selected card shown by an outline, a tint and a brass marker, not by color alone). The sensible choices are already made, so one click on "Start my resume" is enough, and everything can be changed later without losing a word. The component is a general `ChoiceCards` in the UI kit.

**The page first, the tools when needed.** The tools that act on a selection (duplicate, delete, group, lock, stacking, align) are not shown until something is selected, and then they float over the bottom of the page area instead of pushing the page down. An early version put them in the toolbar row and the layout moved under the pointer in the middle of a double click, which broke editing. The rule is that selecting never moves the page, and a test measures it.

**A command palette.** Ctrl or Command and K, or the Commands button, opens a search over everything the editor can do: add things, undo and redo, selection actions, stacking, align, zoom, margins, the layout check, change template, earlier versions, go to the PDF, tailor to a job, and "Go to" any element by name. Commands that cannot run now are left out, not greyed. It is a native modal dialog with a combobox over a listbox, arrow keys, Home and End, Enter to run, Escape to close, the count of matches announced, and focus returned where it came from. It is how a keyboard or screen reader user reaches any tool in one step, and how anyone finds a tool without learning the toolbar.

**Visible, usable undo.** Every step in the history carries a short label (Moved, Resized, Edited text, Duplicated, Deleted, Grouped, Aligned, Added a text box, Changed the page style). "Recent changes" lists the last thirty, newest first, and each has "Go back to here", which undoes several steps at once. Redo remains in the toolbar and Ctrl Y until a new change is made.

**Focus on the page.** One toggle hides the side panel and gives the page the width, and brings it back. The state is announced.

**Honest page and save state.** Every page is labelled ("Page 1 of 2") above the page. Leaving the screen with edits that are not saved asks first (the browser's own leave-page question), and a saved resume never asks. The save status was already shown as text and a shape.

**Speed as a tested budget.** A browser test drags an element across the page and types forty characters into a text box while observing event timing, and fails if any interaction takes 200 ms or more (the threshold for a good interaction in the Web Vitals measure). Drawing is local and the autosave is debounced, so this holds with room to spare. The test is a guard, not a promise about slow machines.

**Everything stays equal across inputs.** Every new control is a real button or form control, reachable by keyboard and touch, with axe checks in light and dark.

## Alternatives considered
- **Drag and drop to reorder layers and sections.** Deferred. The Forward and Backward buttons already work for keyboard and screen reader users, and the palette adds "Bring to the front" and "Send to the back". A drag-only reorder would be less accessible, and a drag plus keyboard version is its own piece of work (carryover).
- **A step by step wizard that blocks the editor.** Rejected: three steps on one screen are faster and can be answered in any order.
- **A separate mobile editor.** Rejected, as in ADR-0044.
- **Showing the selection tools in the main toolbar and keeping them disabled.** Rejected: it is noise, and enabling or hiding them in the toolbar moves the page.
- **Greying out unavailable commands in the palette.** Rejected: an unavailable command is not an option, and listing it only to refuse is clutter.
- **Replacing the toolbar with the palette.** Rejected: the visible tools teach what is possible and are the fastest path for common actions.

## Consequences
- The selection tools are on a floating bar over the lower part of the page. On a very short window it can cover the bottom of a page. It scrolls sideways and goes away when the selection is cleared (Escape).
- The "Go to" commands list the first 80 elements, which is more than a resume has.
- The leave-page question uses the browser's wording, which we cannot change.
- The performance budget measures one machine class. It will catch a regression, not tell us about an old phone.
- Real people have not used this yet. A usability session on the start screen and the editor is carryover.

## Evidence
Unit tests (13) for command filtering (every word, case, order, unavailable commands) and for labelled history (order, undo and redo, going back several steps, the limit, coalesced drags, the names of changes). Browser tests (15 new, with axe in light and dark): the three steps and a one-click start, radio buttons and arrow keys, opening the palette, narrowing, Enter and focus, arrow keys and Escape, finding by words and by element name, running a command, recent changes and going back, empty history, selecting does not move the page, focus mode, page labels, the leave-page question, and the interaction budget. The 85 earlier studio, canvas, template, picture, touch and theme tests pass unchanged apart from the layout of the toolbar.
