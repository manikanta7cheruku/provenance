import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { analyzeAts } from "./ats";
import { elementCss, mm, reactStyle } from "./css";
import {
  addElement,
  addPage,
  alignElements,
  deleteElements,
  distributeElements,
  duplicateElements,
  expandSelection,
  fitToPage,
  groupElements,
  lockElements,
  makeRule,
  makeShape,
  makeText,
  moveElements,
  moveToPage,
  removePage,
  reorder,
  setBoxes,
  setCanvasStyle,
  ungroupElements,
  updateElement,
} from "./edit";
import { alignBoxes, bounds, clampDelta, distributeBoxes, resizeBox, snapMove, snapTargets } from "./geometry";
import { History } from "./history";
import { allElements, findElement } from "./types";
import type { CanvasDoc, CanvasElement, CanvasStyle, TextElement } from "./types";

const STYLE: CanvasStyle = { template: "free", font_pair: "plex-newsreader", accent: "#1f3d7a", ink: "#1b1b1b", muted: "#4a4a4a", tint: "#eef1f6", paper: "a4", margin_mm: 16 };

function text(id: string, x: number, y: number, w: number, h: number, extra: Partial<TextElement> = {}): TextElement {
  return {
    id,
    kind: "text",
    name: id,
    x,
    y,
    w,
    h,
    locked: false,
    group: null,
    body: { type: "doc", content: [{ type: "paragraph", content: [{ type: "text", text: id }] }] },
    font: "body",
    size: 10.5,
    color: "ink",
    align: "left",
    line_height: 1.3,
    caps: false,
    ...extra,
  };
}

function doc(...els: CanvasElement[]): CanvasDoc {
  return { version: 2, style: STYLE, pages: [{ id: "p1", elements: els }] };
}

const ids = (d: CanvasDoc, page = 0) => d.pages[page]!.elements.map((e) => e.id);

describe("css shared with the server", () => {
  const golden = JSON.parse(
    readFileSync(resolve(process.cwd(), "../../tests/fixtures/canvas_css_golden.json"), "utf-8"),
  ) as { name: string; style: CanvasStyle; element: CanvasElement; z: number; css: Record<string, string> }[];

  it.each(golden.map((g) => [g.name, g] as const))("matches the golden file for %s", (_name, g) => {
    expect(elementCss(g.element, g.style, g.z)).toEqual(g.css);
  });

  it("writes millimetres the way the server does", () => {
    expect(mm(16)).toBe("16mm");
    expect(mm(0.4)).toBe("0.4mm");
    expect(mm(158.55)).toBe("158.55mm");
    expect(mm(0)).toBe("0mm");
  });

  it("turns declarations into a React style", () => {
    expect(reactStyle({ "min-height": "5mm", "z-index": "3" })).toEqual({ minHeight: "5mm", zIndex: "3" });
  });
});

describe("geometry", () => {
  it("bounds a group and keeps it inside the page", () => {
    const b = bounds([
      { x: 10, y: 10, w: 20, h: 10 },
      { x: 50, y: 30, w: 10, h: 10 },
    ]);
    expect(b).toEqual({ x: 10, y: 10, w: 50, h: 30 });
    expect(clampDelta(b, -20, 500, 210, 297)).toEqual({ dx: -10, dy: 257 });
  });

  it("snaps a box edge, middle or margin onto a nearby line and says which line", () => {
    const targets = snapTargets(210, 297, 16, [{ x: 100, y: 100, w: 40, h: 10 }]);
    const near = snapMove({ x: 16.8, y: 60, w: 30, h: 8 }, targets, 1.5);
    expect(near.dx).toBeCloseTo(-0.8);
    expect(near.guides).toContainEqual({ axis: "x", at: 16 });
    const centred = snapMove({ x: 90.4, y: 50, w: 29, h: 8 }, targets, 1.5);
    expect(centred.dx).toBeCloseTo(0.1);
    const none = snapMove({ x: 60, y: 60, w: 10, h: 5 }, targets, 1.5);
    expect(none.guides).toEqual([]);
  });

  it("prefers the closest line", () => {
    const targets = { xs: [10, 12], ys: [] };
    expect(snapMove({ x: 11.8, y: 0, w: 5, h: 5 }, targets, 3).dx).toBeCloseTo(0.2);
  });

  it("resizes from any handle, never crosses edges and stays on the page", () => {
    const box = { x: 20, y: 20, w: 40, h: 20 };
    const limits = { minW: 5, minH: 5, pageW: 210, pageH: 297 };
    expect(resizeBox(box, "e", 10, 99, limits)).toEqual({ x: 20, y: 20, w: 50, h: 20 });
    expect(resizeBox(box, "w", 100, 0, limits)).toEqual({ x: 55, y: 20, w: 5, h: 20 });
    expect(resizeBox(box, "nw", -50, -50, limits)).toEqual({ x: 0, y: 0, w: 60, h: 40 });
    expect(resizeBox(box, "se", 500, 500, limits)).toEqual({ x: 20, y: 20, w: 190, h: 277 });
  });

  it("aligns to the page for one box and to the group for several", () => {
    const one = alignBoxes([{ x: 20, y: 20, w: 40, h: 10 }], "center", 210, 297);
    expect(one[0]?.x).toBe(85);
    const many = alignBoxes(
      [
        { x: 10, y: 0, w: 20, h: 10 },
        { x: 50, y: 40, w: 10, h: 10 },
      ],
      "right",
      210,
      297,
    );
    expect(many.map((b) => b.x)).toEqual([40, 50]);
    expect(alignBoxes([{ x: 5, y: 5, w: 10, h: 10 }, { x: 5, y: 50, w: 10, h: 10 }], "bottom", 210, 297).map((b) => b.y)).toEqual([50, 50]);
  });

  it("distributes with equal gaps and keeps the outer two", () => {
    const out = distributeBoxes(
      [
        { x: 0, y: 0, w: 10, h: 10 },
        { x: 15, y: 0, w: 10, h: 10 },
        { x: 90, y: 0, w: 10, h: 10 },
      ],
      "x",
    );
    expect(out.map((b) => b.x)).toEqual([0, 45, 90]);
    expect(distributeBoxes([{ x: 0, y: 0, w: 1, h: 1 }], "x")).toHaveLength(1);
  });
});

describe("edits", () => {
  const base = () => doc(text("a", 20, 20, 50, 10), text("b", 20, 60, 50, 10), text("c", 20, 100, 50, 10));

  it("never change the document they were given", () => {
    const d = base();
    const before = JSON.stringify(d);
    moveElements(d, ["a"], 5, 5);
    updateElement(d, "a", { name: "x" });
    deleteElements(d, ["a"]);
    duplicateElements(d, ["a"]);
    reorder(d, ["a"], "front");
    groupElements(d, ["a", "b"]);
    alignElements(d, ["a", "b"], "left");
    expect(JSON.stringify(d)).toBe(before);
  });

  it("moves and rounds, keeps the group on the page and skips locked elements", () => {
    const d = lockElements(base(), ["c"], true);
    const moved = moveElements(d, ["a", "c"], 5.04, -500);
    expect(findElement(moved, "a")?.element.x).toBe(25);
    expect(findElement(moved, "a")?.element.y).toBe(0);
    expect(findElement(moved, "c")?.element).toMatchObject({ x: 20, y: 100 });
  });

  it("adds, deletes and releases a group that is left with one member", () => {
    let d = groupElements(base(), ["a", "b"]);
    expect(expandSelection(d, ["a"])).toEqual(["a", "b"]);
    d = deleteElements(d, ["b"]);
    expect(ids(d)).toEqual(["a", "c"]);
    expect(findElement(d, "a")?.element.group).toBeNull();
    expect(ids(addElement(d, 0, makeShape(d)))).toHaveLength(3);
  });

  it("duplicates with an offset, new ids and a new group for grouped copies", () => {
    const grouped = groupElements(base(), ["a", "b"]);
    const { doc: next, ids: copies } = duplicateElements(grouped, ["a", "b"]);
    expect(copies).toHaveLength(2);
    const [a, b] = copies.map((id) => findElement(next, id)!.element);
    expect(a?.x).toBe(23);
    expect(a?.group).toBeTruthy();
    expect(a?.group).toBe(b?.group);
    expect(a?.group).not.toBe(findElement(next, "a")?.element.group);
    expect(new Set(allElements(next).map((e) => e.id)).size).toBe(5);
    expect(a?.name).not.toBe(findElement(next, "a")?.element.name);
  });

  it("reorders one step or to the ends, for one or several", () => {
    const d = base();
    expect(ids(reorder(d, ["a"], "forward"))).toEqual(["b", "a", "c"]);
    expect(ids(reorder(d, ["c"], "backward"))).toEqual(["a", "c", "b"]);
    expect(ids(reorder(d, ["a"], "front"))).toEqual(["b", "c", "a"]);
    expect(ids(reorder(d, ["c"], "back"))).toEqual(["c", "a", "b"]);
    expect(ids(reorder(d, ["c"], "forward"))).toEqual(["a", "b", "c"]);
    expect(ids(reorder(d, ["a", "b"], "forward"))).toEqual(["c", "a", "b"]);
  });

  it("aligns and distributes only elements that are not locked", () => {
    const d = lockElements(base(), ["b"], true);
    const aligned = alignElements(d, ["a", "b", "c"], "right");
    expect(findElement(aligned, "b")?.element.x).toBe(20);
    const spread = distributeElements(setBoxes(base(), { b: { x: 90, y: 20, w: 50, h: 10 } }), ["a", "b", "c"], "y");
    expect(findElement(spread, "b")?.element.y).toBe(60);
  });

  it("groups, ungroups and sets the lock", () => {
    const d = ungroupElements(groupElements(base(), ["a", "b"]), ["a"]);
    expect(findElement(d, "a")?.element.group).toBeNull();
    expect(groupElements(base(), ["a"])).toEqual(base());
  });

  it("manages pages: add up to the limit, move elements, remove the last", () => {
    let d = addPage(addPage(base()));
    expect(d.pages).toHaveLength(3);
    expect(addPage(d).pages).toHaveLength(3);
    d = moveToPage(d, ["a"], 2);
    expect(ids(d, 2)).toEqual(["a"]);
    expect(ids(d, 0)).toEqual(["b", "c"]);
    d = removePage(d, 2);
    expect(d.pages).toHaveLength(2);
    expect(removePage(doc(), 0).pages).toHaveLength(1);
  });

  it("brings elements back inside the page when the paper changes", () => {
    const d = doc(text("a", 150, 280, 60, 15), makeRule(doc()));
    const letter = setCanvasStyle(d, { paper: "letter" });
    const a = findElement(letter, "a")!.element;
    expect(a.x + a.w).toBeLessThanOrEqual(215.9);
    expect(a.y + a.h).toBeLessThanOrEqual(279.4);
    expect(fitToPage(d).pages[0]?.elements[0]?.y).toBeCloseTo(280);
  });

  it("makes new elements inside the margins with unique names", () => {
    const d = doc(text("a", 20, 20, 50, 10));
    const t = makeText(d, 0);
    expect(t.x).toBe(16);
    expect(makeText(addElement(d, 0, t), 0).name).toBe("Text 2");
    expect(makeRule(d).h).toBeLessThan(1);
  });
});

describe("history", () => {
  it("undoes and redoes, and a new change clears what could be redone", () => {
    const h = new History<number>();
    h.record(1);
    h.record(2);
    expect(h.undo(3)).toBe(2);
    expect(h.undo(2)).toBe(1);
    expect(h.undo(1)).toBeNull();
    expect(h.redo(1)).toBe(2);
    h.record(9);
    expect(h.canRedo).toBe(false);
  });

  it("joins quick changes with the same key into one step", () => {
    const h = new History<number>();
    h.record(0, "drag", 1000);
    h.record(1, "drag", 1200);
    h.record(2, "drag", 1400);
    h.record(3, "other", 1500);
    expect(h.undo(4)).toBe(3);
    expect(h.undo(3)).toBe(0);
    expect(h.canUndo).toBe(false);
  });

  it("starts a new step after a pause or when sealed", () => {
    const h = new History<number>();
    h.record(0, "type", 1000);
    h.record(1, "type", 5000);
    h.seal();
    h.record(2, "type", 5100);
    expect(h.undo(3)).toBe(2);
    expect(h.undo(2)).toBe(1);
    expect(h.undo(1)).toBe(0);
  });

  it("keeps at most the limit", () => {
    const h = new History<number>(3);
    for (let i = 0; i < 10; i += 1) h.record(i);
    let count = 0;
    let current = 10;
    for (let prev = h.undo(current); prev !== null; prev = h.undo(current)) {
      current = prev;
      count += 1;
    }
    expect(count).toBe(3);
  });
});

describe("ATS check", () => {
  it("passes a single-column page with a right-aligned date and a rule", () => {
    const d = doc(
      text("name", 16, 16, 178, 11),
      text("role", 16, 40, 140, 6),
      text("dates", 158, 40, 36, 5, { align: "right" }),
      { ...makeRule(doc()), id: "rule", y: 36 } as CanvasElement,
    );
    expect(analyzeAts(d)).toEqual({ safe: true, issues: [] });
  });

  it("flags text boxes that overlap", () => {
    const report = analyzeAts(doc(text("a", 20, 20, 80, 20), text("b", 30, 25, 80, 20)));
    expect(report.safe).toBe(false);
    expect(report.issues[0]).toMatchObject({ kind: "overlap", blocks: true, ids: ["a", "b"] });
    expect(report.issues[0]?.message).toMatch(/overlap/);
  });

  it("flags tall boxes side by side as columns, but not a short date box", () => {
    const columns = analyzeAts(doc(text("left", 16, 40, 85, 40), text("right", 110, 40, 85, 40)));
    expect(columns.issues.map((i) => i.kind)).toEqual(["columns"]);
    const date = analyzeAts(doc(text("left", 16, 40, 140, 14), text("right", 158, 40, 36, 5)));
    expect(date.safe).toBe(true);
  });

  it("flags text on a filled shape but not text above a thin rule", () => {
    const shape = makeShape(doc(), { x: 16, y: 16, w: 100, h: 20 });
    expect(analyzeAts(doc(shape, text("t", 20, 20, 60, 8))).issues[0]?.kind).toBe("on_shape");
    expect(analyzeAts(doc({ ...makeRule(doc()), y: 30 } as CanvasElement, text("t", 20, 20, 60, 8))).safe).toBe(true);
  });

  it("gives notes, not blockers, for small text, the page edge and pale colors", () => {
    const report = analyzeAts(doc(text("tiny", 2, 100, 60, 4, { size: 6.5 }), text("pale", 20, 120, 60, 5, { color: "#cccccc" })));
    expect(report.safe).toBe(true);
    expect(report.issues.map((i) => i.kind).sort()).toEqual(["contrast", "edge", "small_text"]);
    expect(report.issues.every((i) => !i.blocks)).toBe(true);
  });

  it("names the page when there are several", () => {
    const d: CanvasDoc = { ...doc(), pages: [{ id: "p1", elements: [] }, { id: "p2", elements: [text("a", 20, 20, 80, 20), text("b", 30, 25, 80, 20)] }] };
    expect(analyzeAts(d).issues[0]?.message).toMatch(/page 2/);
  });

  it("ignores empty text boxes", () => {
    expect(analyzeAts(doc(text("a", 20, 20, 80, 20, { body: null }), text("b", 30, 25, 80, 20, { body: null }))).issues).toEqual([]);
  });
});
