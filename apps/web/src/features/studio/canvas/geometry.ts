/** Rectangles, snapping, resizing, alignment and distribution. Pure, in millimetres. */

export interface Box {
  x: number;
  y: number;
  w: number;
  h: number;
}

export type Handle = "n" | "ne" | "e" | "se" | "s" | "sw" | "w" | "nw";
export type AlignMode = "left" | "center" | "right" | "top" | "middle" | "bottom";

export const round1 = (n: number): number => Math.round(n * 10) / 10;

export function bounds(boxes: readonly Box[]): Box {
  if (boxes.length === 0) return { x: 0, y: 0, w: 0, h: 0 };
  const left = Math.min(...boxes.map((b) => b.x));
  const top = Math.min(...boxes.map((b) => b.y));
  const right = Math.max(...boxes.map((b) => b.x + b.w));
  const bottom = Math.max(...boxes.map((b) => b.y + b.h));
  return { x: left, y: top, w: right - left, h: bottom - top };
}

export function intersects(a: Box, b: Box): boolean {
  return a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;
}

export function overlapArea(a: Box, b: Box): number {
  const w = Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x);
  const h = Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y);
  return w > 0 && h > 0 ? w * h : 0;
}

/** Keep a group inside the page by limiting how far it may move. */
export function clampDelta(box: Box, dx: number, dy: number, pageW: number, pageH: number): { dx: number; dy: number } {
  const nx = Math.min(Math.max(box.x + dx, 0), Math.max(pageW - box.w, 0));
  const ny = Math.min(Math.max(box.y + dy, 0), Math.max(pageH - box.h, 0));
  return { dx: nx - box.x, dy: ny - box.y };
}

export interface Guide {
  axis: "x" | "y";
  at: number;
}

export interface SnapTargets {
  xs: number[];
  ys: number[];
}

/** The lines something can snap to: page edges and middle, the margins, and the other elements. */
export function snapTargets(pageW: number, pageH: number, margin: number, others: readonly Box[]): SnapTargets {
  const xs = [0, margin, pageW / 2, pageW - margin, pageW];
  const ys = [0, margin, pageH / 2, pageH - margin, pageH];
  for (const o of others) {
    xs.push(o.x, o.x + o.w / 2, o.x + o.w);
    ys.push(o.y, o.y + o.h / 2, o.y + o.h);
  }
  return { xs, ys };
}

function nearest(candidates: number[], targets: number[], threshold: number): { delta: number; at: number } | null {
  let best: { delta: number; at: number } | null = null;
  for (const c of candidates) {
    for (const t of targets) {
      const delta = t - c;
      if (Math.abs(delta) <= threshold && (best === null || Math.abs(delta) < Math.abs(best.delta))) {
        best = { delta, at: t };
      }
    }
  }
  return best;
}

/** Nudge a moving box onto a nearby line, left edge, middle or right edge, top, middle or bottom. */
export function snapMove(
  moving: Box,
  targets: SnapTargets,
  threshold: number,
): { dx: number; dy: number; guides: Guide[] } {
  const sx = nearest([moving.x, moving.x + moving.w / 2, moving.x + moving.w], targets.xs, threshold);
  const sy = nearest([moving.y, moving.y + moving.h / 2, moving.y + moving.h], targets.ys, threshold);
  const guides: Guide[] = [];
  if (sx) guides.push({ axis: "x", at: sx.at });
  if (sy) guides.push({ axis: "y", at: sy.at });
  return { dx: sx?.delta ?? 0, dy: sy?.delta ?? 0, guides };
}

/** The box after dragging one handle by (dx, dy). Edges cannot cross, and the box stays in the page. */
export function resizeBox(
  box: Box,
  handle: Handle,
  dx: number,
  dy: number,
  limits: { minW: number; minH: number; pageW: number; pageH: number },
): Box {
  let left = box.x;
  let top = box.y;
  let right = box.x + box.w;
  let bottom = box.y + box.h;
  if (handle.includes("w")) left = Math.min(Math.max(left + dx, 0), right - limits.minW);
  if (handle.includes("e")) right = Math.max(Math.min(right + dx, limits.pageW), left + limits.minW);
  if (handle.includes("n")) top = Math.min(Math.max(top + dy, 0), bottom - limits.minH);
  if (handle.includes("s")) bottom = Math.max(Math.min(bottom + dy, limits.pageH), top + limits.minH);
  return { x: left, y: top, w: right - left, h: bottom - top };
}

/** Where each box goes when aligned. One box aligns to the page, several to their common bounds. */
export function alignBoxes(boxes: readonly Box[], mode: AlignMode, pageW: number, pageH: number): Box[] {
  const frame = boxes.length === 1 ? { x: 0, y: 0, w: pageW, h: pageH } : bounds(boxes);
  return boxes.map((b) => {
    switch (mode) {
      case "left":
        return { ...b, x: frame.x };
      case "center":
        return { ...b, x: frame.x + (frame.w - b.w) / 2 };
      case "right":
        return { ...b, x: frame.x + frame.w - b.w };
      case "top":
        return { ...b, y: frame.y };
      case "middle":
        return { ...b, y: frame.y + (frame.h - b.h) / 2 };
      default:
        return { ...b, y: frame.y + frame.h - b.h };
    }
  });
}

/** Equal gaps between three or more boxes. The outer two stay where they are. */
export function distributeBoxes(boxes: readonly Box[], axis: "x" | "y"): Box[] {
  if (boxes.length < 3) return boxes.map((b) => ({ ...b }));
  const key = axis === "x" ? "x" : "y";
  const size = axis === "x" ? "w" : "h";
  const order = boxes.map((b, i) => ({ b, i })).sort((p, q) => p.b[key] - q.b[key]);
  const first = order[0]!.b;
  const last = order[order.length - 1]!.b;
  const span = last[key] + last[size] - first[key];
  const total = order.reduce((sum, { b }) => sum + b[size], 0);
  const gap = (span - total) / (order.length - 1);
  const out = boxes.map((b) => ({ ...b }));
  let cursor = first[key];
  for (const { b, i } of order) {
    out[i] = { ...b, [key]: cursor } as Box;
    cursor += b[size] + gap;
  }
  return out;
}

/** The smallest nudge that puts any of `values` on a line in `targets`, within `threshold`. */
export function snapValues(values: readonly number[], targets: readonly number[], threshold: number): { delta: number; at: number } | null {
  return nearest([...values], [...targets], threshold);
}
