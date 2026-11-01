import { newId } from "../doc-ops";
import { alignBoxes, bounds, clampDelta, distributeBoxes, round1 } from "./geometry";
import type { AlignMode, Box } from "./geometry";
import { LIMITS, allElements, findElement, pageSize } from "./types";
import type { CanvasDoc, CanvasElement, CanvasStyle, ShapeElement, TextElement } from "./types";

/** Every edit of a canvas document as a pure function. Each returns a new document. */

function mapElements(doc: CanvasDoc, edit: (el: CanvasElement, page: number) => CanvasElement): CanvasDoc {
  return {
    ...doc,
    pages: doc.pages.map((page, pi) => ({ ...page, elements: page.elements.map((el) => edit(el, pi)) })),
  };
}

const boxOf = (el: CanvasElement): Box => ({ x: el.x, y: el.y, w: el.w, h: el.h });

/** Selecting one member of a group selects all of its members. */
export function expandSelection(doc: CanvasDoc, ids: readonly string[]): string[] {
  const groups = new Set<string>();
  const wanted = new Set(ids);
  for (const el of allElements(doc)) if (wanted.has(el.id) && el.group) groups.add(el.group);
  for (const el of allElements(doc)) if (el.group && groups.has(el.group)) wanted.add(el.id);
  return allElements(doc)
    .filter((el) => wanted.has(el.id))
    .map((el) => el.id);
}

export function updateElement(doc: CanvasDoc, id: string, patch: Partial<CanvasElement>): CanvasDoc {
  return mapElements(doc, (el) => (el.id === id ? ({ ...el, ...patch } as CanvasElement) : el));
}

export function setBoxes(doc: CanvasDoc, boxes: Record<string, Box>): CanvasDoc {
  return mapElements(doc, (el) => {
    const b = boxes[el.id];
    return b ? { ...el, x: round1(b.x), y: round1(b.y), w: round1(b.w), h: round1(b.h) } : el;
  });
}

/** Move the elements that are not locked among `ids`, keeping the group inside its page. */
export function moveElements(doc: CanvasDoc, ids: readonly string[], dx: number, dy: number): CanvasDoc {
  const wanted = new Set(ids);
  return {
    ...doc,
    pages: doc.pages.map((page) => {
      const movable = page.elements.filter((el) => wanted.has(el.id) && !el.locked);
      if (movable.length === 0) return page;
      const [pw, ph] = pageSize(doc.style);
      const clamped = clampDelta(bounds(movable.map(boxOf)), dx, dy, pw, ph);
      const moving = new Set(movable.map((el) => el.id));
      return {
        ...page,
        elements: page.elements.map((el) =>
          moving.has(el.id) ? { ...el, x: round1(el.x + clamped.dx), y: round1(el.y + clamped.dy) } : el,
        ),
      };
    }),
  };
}

export function addElement(doc: CanvasDoc, pageIndex: number, el: CanvasElement): CanvasDoc {
  if (allElements(doc).length >= LIMITS.maxElements) return doc;
  return {
    ...doc,
    pages: doc.pages.map((page, pi) => (pi === pageIndex ? { ...page, elements: [...page.elements, el] } : page)),
  };
}

export function deleteElements(doc: CanvasDoc, ids: readonly string[]): CanvasDoc {
  const gone = new Set(ids);
  const removed = mapPages(doc, (els) => els.filter((el) => !gone.has(el.id)));
  return releaseLonelyGroups(removed);
}

function mapPages(doc: CanvasDoc, edit: (els: CanvasElement[], page: number) => CanvasElement[]): CanvasDoc {
  return { ...doc, pages: doc.pages.map((page, pi) => ({ ...page, elements: edit(page.elements, pi) })) };
}

function releaseLonelyGroups(doc: CanvasDoc): CanvasDoc {
  const counts = new Map<string, number>();
  for (const el of allElements(doc)) if (el.group) counts.set(el.group, (counts.get(el.group) ?? 0) + 1);
  return mapElements(doc, (el) => (el.group && (counts.get(el.group) ?? 0) < 2 ? { ...el, group: null } : el));
}

export function uniqueName(doc: CanvasDoc, base: string): string {
  const names = new Set(allElements(doc).map((el) => el.name));
  if (!names.has(base)) return base;
  for (let n = 2; n < 1000; n += 1) if (!names.has(`${base} ${n}`)) return `${base} ${n}`;
  return base;
}

export function duplicateElements(doc: CanvasDoc, ids: readonly string[]): { doc: CanvasDoc; ids: string[] } {
  const wanted = new Set(ids);
  const groupMap = new Map<string, string>();
  const created: string[] = [];
  const [pw, ph] = pageSize(doc.style);
  let next = doc;
  for (let pi = 0; pi < doc.pages.length; pi += 1) {
    const originals = doc.pages[pi]!.elements.filter((el) => wanted.has(el.id));
    if (originals.length === 0) continue;
    const frame = bounds(originals.map(boxOf));
    const shift = clampDelta(frame, 3, 3, pw, ph);
    const copies = originals.map((el) => {
      const id = newId();
      created.push(id);
      let group = el.group;
      if (group) {
        if (!groupMap.has(group)) groupMap.set(group, newId());
        group = groupMap.get(group) ?? null;
      }
      return { ...el, id, group, locked: false, x: round1(el.x + shift.dx), y: round1(el.y + shift.dy), name: uniqueName(next, el.name) };
    });
    for (const copy of copies) next = addElement(next, pi, copy as CanvasElement);
  }
  return { doc: next, ids: created };
}

export type Order = "forward" | "backward" | "front" | "back";

/** Change stacking. The order of the list is the order of drawing, last on top. */
export function reorder(doc: CanvasDoc, ids: readonly string[], how: Order): CanvasDoc {
  const wanted = new Set(ids);
  return mapPages(doc, (els) => {
    const picked = els.filter((el) => wanted.has(el.id));
    if (picked.length === 0) return els;
    const rest = els.filter((el) => !wanted.has(el.id));
    if (how === "front") return [...rest, ...picked];
    if (how === "back") return [...picked, ...rest];
    const out = [...els];
    const indices = els.map((el, i) => (wanted.has(el.id) ? i : -1)).filter((i) => i >= 0);
    if (how === "forward") {
      for (const i of [...indices].reverse()) {
        if (i < out.length - 1 && !wanted.has(out[i + 1]!.id)) [out[i], out[i + 1]] = [out[i + 1]!, out[i]!];
      }
    } else {
      for (const i of indices) {
        if (i > 0 && !wanted.has(out[i - 1]!.id)) [out[i], out[i - 1]] = [out[i - 1]!, out[i]!];
      }
    }
    return out;
  });
}

export function groupElements(doc: CanvasDoc, ids: readonly string[]): CanvasDoc {
  if (ids.length < 2) return doc;
  const group = newId();
  const wanted = new Set(ids);
  return mapElements(doc, (el) => (wanted.has(el.id) ? { ...el, group } : el));
}

export function ungroupElements(doc: CanvasDoc, ids: readonly string[]): CanvasDoc {
  const wanted = new Set(ids);
  return mapElements(doc, (el) => (wanted.has(el.id) ? { ...el, group: null } : el));
}

export function lockElements(doc: CanvasDoc, ids: readonly string[], locked: boolean): CanvasDoc {
  const wanted = new Set(ids);
  return mapElements(doc, (el) => (wanted.has(el.id) ? { ...el, locked } : el));
}

export function alignElements(doc: CanvasDoc, ids: readonly string[], mode: AlignMode): CanvasDoc {
  const [pw, ph] = pageSize(doc.style);
  const wanted = new Set(ids);
  return mapPages(doc, (els) => {
    const picked = els.filter((el) => wanted.has(el.id) && !el.locked);
    if (picked.length === 0) return els;
    const aligned = alignBoxes(picked.map(boxOf), mode, pw, ph);
    const byId = new Map(picked.map((el, i) => [el.id, aligned[i]!]));
    return els.map((el) => {
      const b = byId.get(el.id);
      return b ? { ...el, x: round1(b.x), y: round1(b.y) } : el;
    });
  });
}

export function distributeElements(doc: CanvasDoc, ids: readonly string[], axis: "x" | "y"): CanvasDoc {
  const wanted = new Set(ids);
  return mapPages(doc, (els) => {
    const picked = els.filter((el) => wanted.has(el.id) && !el.locked);
    if (picked.length < 3) return els;
    const spread = distributeBoxes(picked.map(boxOf), axis);
    const byId = new Map(picked.map((el, i) => [el.id, spread[i]!]));
    return els.map((el) => {
      const b = byId.get(el.id);
      return b ? { ...el, x: round1(b.x), y: round1(b.y) } : el;
    });
  });
}

// ---- pages and style

export function addPage(doc: CanvasDoc): CanvasDoc {
  if (doc.pages.length >= LIMITS.maxPages) return doc;
  return { ...doc, pages: [...doc.pages, { id: newId(), elements: [] }] };
}

export function removePage(doc: CanvasDoc, index: number): CanvasDoc {
  if (doc.pages.length <= 1) return doc;
  return releaseLonelyGroups({ ...doc, pages: doc.pages.filter((_, i) => i !== index) });
}

export function moveToPage(doc: CanvasDoc, ids: readonly string[], target: number): CanvasDoc {
  if (target < 0 || target >= doc.pages.length) return doc;
  const wanted = new Set(ids);
  const moving = doc.pages.flatMap((p, pi) => (pi === target ? [] : p.elements.filter((el) => wanted.has(el.id))));
  if (moving.length === 0) return doc;
  const cleared = mapPages(doc, (els, pi) => (pi === target ? els : els.filter((el) => !wanted.has(el.id))));
  return releaseLonelyGroups(
    mapPages(cleared, (els, pi) => (pi === target ? [...els, ...moving.map((el) => ({ ...el, group: el.group }))] : els)),
  );
}

/** After a change of paper size, bring every element back inside the page. */
export function fitToPage(doc: CanvasDoc): CanvasDoc {
  const [pw, ph] = pageSize(doc.style);
  return mapElements(doc, (el) => {
    const w = Math.min(el.w, pw);
    const h = Math.min(el.h, ph);
    return { ...el, w: round1(w), h: round1(h), x: round1(Math.min(Math.max(el.x, 0), pw - w)), y: round1(Math.min(Math.max(el.y, 0), ph - h)) };
  });
}

export function setCanvasStyle(doc: CanvasDoc, patch: Partial<CanvasStyle>): CanvasDoc {
  const next = { ...doc, style: { ...doc.style, ...patch } };
  return patch.paper && patch.paper !== doc.style.paper ? fitToPage(next) : next;
}

// ---- making new elements

export function makeText(doc: CanvasDoc, page: number, overrides: Partial<TextElement> = {}): TextElement {
  const [pw] = pageSize(doc.style);
  const margin = doc.style.margin_mm;
  const width = Math.min(80, pw - 2 * margin);
  return {
    id: newId(),
    kind: "text",
    name: uniqueName(doc, "Text"),
    x: margin,
    y: margin + 10 * Math.min(page, 0),
    w: width,
    h: 6,
    locked: false,
    group: null,
    body: { type: "doc", content: [{ type: "paragraph", content: [{ type: "text", text: "New text" }] }] },
    font: "body",
    size: 10.5,
    color: "ink",
    align: "left",
    line_height: 1.3,
    caps: false,
    ...overrides,
  };
}

export function makeShape(doc: CanvasDoc, overrides: Partial<ShapeElement> = {}): ShapeElement {
  const margin = doc.style.margin_mm;
  return {
    id: newId(),
    kind: "shape",
    name: uniqueName(doc, "Box"),
    x: margin,
    y: margin + 20,
    w: 60,
    h: 20,
    locked: false,
    group: null,
    fill: "accent",
    stroke: "none",
    stroke_pt: 0,
    radius: 0,
    ...overrides,
  };
}

export function makeRule(doc: CanvasDoc): ShapeElement {
  const [pw] = pageSize(doc.style);
  const margin = doc.style.margin_mm;
  return makeShape(doc, { name: uniqueName(doc, "Rule"), x: margin, y: margin + 20, w: pw - 2 * margin, h: 0.4, fill: "accent" });
}

export function elementCount(doc: CanvasDoc): number {
  return allElements(doc).length;
}

export { findElement };
