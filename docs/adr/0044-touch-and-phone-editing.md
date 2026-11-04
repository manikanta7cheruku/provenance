# ADR-0044: Touch and phone editing on the canvas

Status: Accepted (checkpoint 2.12).

## Context
The canvas editor (ADR-0035) was mouse and keyboard only. Below 980 pixels it showed the page read-only with a note, because a drag with a finger scrolled the page instead of moving things and the tools did not fit. The owner asked for editing on a phone and a tablet. A finger differs from a mouse in four ways: it hides what it touches, it is imprecise, it also means "scroll", and there is no keyboard for edit, delete, duplicate or small moves.

## Decision

**Editing is available at every width.** The read-only mode and its note are gone. The tools, the pages and the properties stack in one column on a narrow screen. The existing mouse and keyboard behaviour is unchanged.

**One finger on an element drags it, one finger on empty paper scrolls.** `touch-action` is `none` on elements and handles and `pan-x pan-y` on the stage. A press on empty paper with a finger only clears the selection, so the marquee (which would fight with scrolling) stays a mouse tool. Mouse behaviour is untouched.

**Two fingers zoom.** The stage tracks touch pointers. A second finger cancels any drag, so a pinch never moves anything, and the zoom follows the distance between the fingers (`pinchZoom`, clamped to 25 percent to 300 percent). The browser is stopped from taking the pinch as a scroll by cancelling the touch events while two fingers are down, because the browser decides to scroll on the first move and React listens passively.

**A double tap edits text, with more room.** The existing double press rule uses 600 ms and 24 pixels for a finger (450 ms and 6 pixels for a mouse).

**Controls for a finger appear when the main pointer is coarse** (`(pointer: coarse)`), not when the screen is narrow, so a laptop with a small window keeps the compact tools and a tablet with a keyboard dock still gets large targets. A selection bar under the pages offers Edit text, Duplicate, Delete and four small moves of 1 millimetre, because a finger cannot place things to a millimetre and there is no arrow key. Buttons are at least 44 pixels. A handle stays small to look at and gets a 44 pixel target. Fields in the properties use 16 pixel text so a phone does not zoom into them. The toolbar scrolls sideways instead of wrapping into a tall block.

## Alternatives considered
- **Switch to a separate mobile editor.** Rejected: two editors to keep in step for one document model.
- **Long press to drag.** Rejected: slow, and hard to discover. Dragging an element is what people expect.
- **Let the browser pinch the page.** Rejected: it zooms the whole app, not the resume.
- **Marquee select by touch.** Rejected: it competes with scrolling. Select several with Shift and Space on a keyboard, or use the layers list.
- **Show the touch controls below a width.** Rejected: width is not the pointer.

## Consequences
- Several elements cannot be picked by dragging on a phone. The layers list in the properties can.
- Resize by touch relies on the 44 pixel handle targets, which overlap on very small elements. Moving by buttons and typing sizes in the properties remain.
- Fine positioning is 1 millimetre per tap. Typed positions in the properties give any value.
- Real devices were not tried. The tests use emulated touch events.

## Evidence
Unit tests for the pinch maths. Browser tests with emulated touch (390 by 844): the editor and tools show and the page does not scroll sideways, a tap selects and shows the selection bar, Edit text starts editing, the buttons move, duplicate and delete, a finger drag moves an element, two fingers zoom and change nothing in the document, and axe finds nothing in light and dark. The earlier mouse and keyboard tests still pass.
