import { describe, expect, it } from "vitest";
import { filterCommands } from "../../../ui";
import type { Command } from "../../../ui";
import { History, labelForKey } from "./history";

const run = () => undefined;
const COMMANDS: Command[] = [
  { id: "add-text", label: "Add a text box", group: "Add", keywords: "write words", run },
  { id: "add-picture", label: "Add a picture", group: "Add", keywords: "photo logo", run },
  { id: "zoom-in", label: "Zoom in", group: "View", run },
  { id: "dup", label: "Duplicate the selection", group: "Selection", disabled: true, run },
  { id: "undo", label: "Undo", group: "History", run },
];

describe("finding a command", () => {
  it("lists everything that can run when nothing is typed, and leaves out what cannot", () => {
    const ids = filterCommands(COMMANDS, "").map((c) => c.id);
    expect(ids).toEqual(["add-text", "add-picture", "zoom-in", "undo"]);
  });

  it("matches every word, in the name, the group or the keywords", () => {
    expect(filterCommands(COMMANDS, "photo").map((c) => c.id)).toEqual(["add-picture"]);
    expect(filterCommands(COMMANDS, "add logo").map((c) => c.id)).toEqual(["add-picture"]);
    expect(filterCommands(COMMANDS, "history").map((c) => c.id)).toEqual(["undo"]);
    expect(filterCommands(COMMANDS, "add zoom")).toEqual([]);
  });

  it("is not case sensitive and ignores extra spaces", () => {
    expect(filterCommands(COMMANDS, "  ZOOM   in ").map((c) => c.id)).toEqual(["zoom-in"]);
  });

  it("puts names that start with the text first", () => {
    const list: Command[] = [
      { id: "b", label: "Show the margin guides", group: "View", run },
      { id: "a", label: "Margin notes", group: "View", run },
    ];
    expect(filterCommands(list, "margin").map((c) => c.id)).toEqual(["a", "b"]);
  });

  it("never offers a command that cannot run, even when it matches", () => {
    expect(filterCommands(COMMANDS, "duplicate")).toEqual([]);
  });
});

describe("history with labels", () => {
  it("shows what an undo would take back, newest first", () => {
    const h = new History<number>();
    h.record(0, undefined, 0, "Added text box");
    h.record(1, undefined, 0, "Moved");
    h.record(2, undefined, 0, "Deleted");
    expect(h.undoable).toEqual(["Deleted", "Moved", "Added text box"]);
  });

  it("moves a label to the redo list on undo and back on redo", () => {
    const h = new History<number>();
    h.record(0, undefined, 0, "Moved");
    h.record(1, undefined, 0, "Deleted");
    expect(h.undo(2)).toBe(1);
    expect(h.undoable).toEqual(["Moved"]);
    expect(h.redoable).toEqual(["Deleted"]);
    expect(h.redo(1)).toBe(2);
    expect(h.undoable).toEqual(["Deleted", "Moved"]);
    expect(h.redoable).toEqual([]);
  });

  it("goes back several steps at once and returns the value before them", () => {
    const h = new History<number>();
    for (let i = 0; i < 5; i += 1) h.record(i, undefined, 0, `Step ${i}`);
    expect(h.undoMany(5, 3)).toBe(2);
    expect(h.undoable).toEqual(["Step 1", "Step 0"]);
    expect(h.redoable).toHaveLength(3);
  });

  it("stops at the oldest step when asked to go back further than there is", () => {
    const h = new History<number>();
    h.record(0, undefined, 0, "Only");
    expect(h.undoMany(1, 5)).toBe(0);
    expect(h.canUndo).toBe(false);
    expect(h.undoMany(0, 2)).toBeNull();
  });

  it("a new change clears what could be redone", () => {
    const h = new History<number>();
    h.record(0, undefined, 0, "A");
    h.undo(1);
    expect(h.redoable).toEqual(["A"]);
    h.record(0, undefined, 0, "B");
    expect(h.redoable).toEqual([]);
  });

  it("keeps one step for a drag and labels it", () => {
    const h = new History<number>();
    for (let i = 0; i < 10; i += 1) h.record(i, "move-1", i * 10, labelForKey("move-1"));
    expect(h.undoable).toEqual(["Moved"]);
  });

  it("drops the oldest steps and their labels together past the limit", () => {
    const h = new History<number>(3);
    for (let i = 0; i < 5; i += 1) h.record(i, undefined, 0, `Step ${i}`);
    expect(h.undoable).toEqual(["Step 4", "Step 3", "Step 2"]);
  });

  it("names the kinds of change in plain words", () => {
    expect(labelForKey("move-4")).toBe("Moved");
    expect(labelForKey("nudge")).toBe("Moved");
    expect(labelForKey("resize-2")).toBe("Resized");
    expect(labelForKey("keysize")).toBe("Resized");
    expect(labelForKey("text-abc")).toBe("Edited text");
    expect(labelForKey("style")).toBe("Changed the page style");
    expect(labelForKey(undefined)).toBe("Change");
    expect(labelForKey("other")).toBe("Changed");
  });
});
