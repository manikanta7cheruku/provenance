import type { Editor } from "@tiptap/react";
import { useRef, useState } from "react";
import type { PointerEvent as ReactPointerEvent } from "react";
import type { RichDoc } from "../../../lib/studio-api";
import { mm } from "./css";
import { ElementView } from "./ElementView";
import { bounds, clampDelta, resizeBox, snapMove, snapTargets, snapValues } from "./geometry";
import type { Box, Guide, Handle } from "./geometry";
import { expandSelection, setBoxes } from "./edit";
import { LIMITS, allElements, pageSize } from "./types";
import type { CanvasDoc, CanvasElement } from "./types";

const CSS_PX_PER_MM = 96 / 25.4;
const SNAP_PX = 6;
const DRAG_START_PX = 3;

const HANDLES: Record<string, Handle[]> = {
  shape: ["nw", "n", "ne", "e", "se", "s", "sw", "w"],
  text: ["w", "e"],
};

interface StageProps {
  doc: CanvasDoc;
  selection: string[];
  editing: string | null;
  zoom: number;
  showMargins: boolean;
  readOnly: boolean;
  onSelect: (ids: string[]) => void;
  /** Change the document. `key` joins quick changes into one undo step. */
  onApply: (next: CanvasDoc, key?: string) => void;
  onBody: (id: string, body: RichDoc | null) => void;
  onHeight: (id: string, h: number) => void;
  onEditor: (editor: Editor | null) => void;
  onEdit: (id: string | null) => void;
  onMoved: (ids: string[], box: Box) => void;
}

type Drag =
  | { kind: "move"; startX: number; startY: number; ids: string[]; origin: Record<string, Box>; page: number; key: string; started: boolean }
  | { kind: "resize"; startX: number; startY: number; id: string; handle: Handle; origin: Box; page: number; key: string; isText: boolean }
  | { kind: "marquee"; page: number; startX: number; startY: number; additive: boolean; base: string[] };

let dragCounter = 0;

/**
 * The pages and everything done to them with a pointer: select, move with snapping, resize,
 * marquee select, and double-click to edit. Positions are in millimetres; screen distances are
 * converted with the zoom. Keyboard control lives one level up, in the editor.
 */
export function Stage(props: StageProps) {
  const { doc, selection, editing, zoom, showMargins, readOnly, onSelect, onApply, onBody, onHeight, onEditor, onEdit, onMoved } = props;
  const [guides, setGuides] = useState<{ page: number; lines: Guide[] } | null>(null);
  const [marquee, setMarquee] = useState<{ page: number; box: Box } | null>(null);
  const drag = useRef<Drag | null>(null);
  const lastDown = useRef<{ id: string; at: number; x: number; y: number } | null>(null);
  const root = useRef<HTMLDivElement>(null);
  const [pw, ph] = pageSize(doc.style);
  const pxPerMm = CSS_PX_PER_MM * zoom;

  const pageOf = (id: string) => doc.pages.findIndex((p) => p.elements.some((e) => e.id === id));

  function pageMm(page: number, clientX: number, clientY: number) {
    const node = root.current?.querySelector<HTMLElement>(`[data-page="${page}"]`);
    const rect = node?.getBoundingClientRect();
    if (!rect) return { x: 0, y: 0 };
    return { x: (clientX - rect.left) / pxPerMm, y: (clientY - rect.top) / pxPerMm };
  }

  function onPointerDown(event: ReactPointerEvent<HTMLDivElement>) {
    if (readOnly || event.button !== 0) return;
    const target = event.target as HTMLElement;
    if (editing && target.closest(".cv-el.is-editing")) return;
    const handleNode = target.closest<HTMLElement>("[data-handle]");
    const elNode = target.closest<HTMLElement>("[data-el]");

    if (handleNode && selection.length === 1) {
      const id = selection[0]!;
      const found = allElements(doc).find((e) => e.id === id);
      if (!found || found.locked) return;
      event.preventDefault();
      root.current?.setPointerCapture(event.pointerId);
      dragCounter += 1;
      drag.current = {
        kind: "resize",
        startX: event.clientX,
        startY: event.clientY,
        id,
        handle: handleNode.dataset.handle as Handle,
        origin: { x: found.x, y: found.y, w: found.w, h: found.h },
        page: pageOf(id),
        key: `resize-${dragCounter}`,
        isText: found.kind === "text",
      };
      return;
    }

    if (editing) onEdit(null);

    if (elNode) {
      const id = elNode.dataset.el!;
      // A second press on the same text box within a moment starts editing it. The browser's own
      // double-click event is retargeted to the stage while the pointer is captured.
      const previous = lastDown.current;
      lastDown.current = { id, at: event.timeStamp, x: event.clientX, y: event.clientY };
      if (previous && previous.id === id && event.timeStamp - previous.at < 450 && Math.hypot(event.clientX - previous.x, event.clientY - previous.y) < 6) {
        const target = allElements(doc).find((e) => e.id === id);
        if (target && target.kind === "text" && !target.locked && !event.shiftKey) {
          lastDown.current = null;
          onSelect([id]);
          onEdit(id);
          return;
        }
      }
      const group = expandSelection(doc, [id]);
      let next = selection;
      if (event.shiftKey) {
        next = group.every((g) => selection.includes(g)) ? selection.filter((s) => !group.includes(s)) : [...new Set([...selection, ...group])];
      } else if (!selection.includes(id)) {
        next = group;
      }
      if (next !== selection) onSelect(next);
      const movable = allElements(doc).filter((e) => next.includes(e.id) && !e.locked);
      if (movable.length === 0 || event.shiftKey) return;
      root.current?.setPointerCapture(event.pointerId);
      dragCounter += 1;
      drag.current = {
        kind: "move",
        startX: event.clientX,
        startY: event.clientY,
        ids: movable.map((e) => e.id),
        origin: Object.fromEntries(movable.map((e) => [e.id, { x: e.x, y: e.y, w: e.w, h: e.h }])),
        page: pageOf(id),
        key: `move-${dragCounter}`,
        started: false,
      };
      return;
    }

    const pageNode = target.closest<HTMLElement>("[data-page]");
    if (pageNode) {
      const page = Number(pageNode.dataset.page);
      const p = pageMm(page, event.clientX, event.clientY);
      root.current?.setPointerCapture(event.pointerId);
      drag.current = { kind: "marquee", page, startX: p.x, startY: p.y, additive: event.shiftKey, base: event.shiftKey ? selection : [] };
      if (!event.shiftKey) onSelect([]);
    } else {
      onSelect([]);
    }
  }

  function onPointerMove(event: ReactPointerEvent<HTMLDivElement>) {
    const d = drag.current;
    if (!d) return;

    if (d.kind === "marquee") {
      const p = pageMm(d.page, event.clientX, event.clientY);
      const box: Box = { x: Math.min(d.startX, p.x), y: Math.min(d.startY, p.y), w: Math.abs(p.x - d.startX), h: Math.abs(p.y - d.startY) };
      setMarquee({ page: d.page, box });
      const hit = doc.pages[d.page]!.elements.filter(
        (e) => e.x < box.x + box.w && box.x < e.x + e.w && e.y < box.y + box.h && box.y < e.y + e.h,
      );
      const ids = expandSelection(doc, hit.map((e) => e.id));
      onSelect([...new Set([...d.base, ...ids])]);
      return;
    }

    let dx = (event.clientX - d.startX) / pxPerMm;
    let dy = (event.clientY - d.startY) / pxPerMm;
    if (d.kind === "move") {
      if (!d.started) {
        if (Math.hypot(event.clientX - d.startX, event.clientY - d.startY) < DRAG_START_PX) return;
        d.started = true;
      }
      if (event.shiftKey) {
        if (Math.abs(dx) > Math.abs(dy)) dy = 0;
        else dx = 0;
      }
      const frame = bounds(Object.values(d.origin));
      const clamped = clampDelta(frame, dx, dy, pw, ph);
      let ddx = clamped.dx;
      let ddy = clamped.dy;
      let lines: Guide[] = [];
      if (!event.altKey) {
        const others = (doc.pages[d.page]?.elements ?? []).filter((e) => !d.ids.includes(e.id)).map((e) => ({ x: e.x, y: e.y, w: e.w, h: e.h }));
        const targets = snapTargets(pw, ph, doc.style.margin_mm, others);
        const snapped = snapMove({ ...frame, x: frame.x + ddx, y: frame.y + ddy }, targets, SNAP_PX / pxPerMm);
        const again = clampDelta(frame, ddx + snapped.dx, ddy + snapped.dy, pw, ph);
        ddx = again.dx;
        ddy = again.dy;
        lines = snapped.guides;
      }
      const boxes: Record<string, Box> = {};
      for (const id of d.ids) {
        const o = d.origin[id]!;
        boxes[id] = { ...o, x: o.x + ddx, y: o.y + ddy };
      }
      onApply(setBoxes(doc, boxes), d.key);
      setGuides({ page: d.page, lines });
      return;
    }

    // resize
    let box = resizeBox(d.origin, d.handle, dx, dy, { minW: LIMITS.minSizeMm * 5, minH: LIMITS.minSizeMm, pageW: pw, pageH: ph });
    if (!event.altKey) {
      const others = (doc.pages[d.page]?.elements ?? []).filter((e) => e.id !== d.id).map((e) => ({ x: e.x, y: e.y, w: e.w, h: e.h }));
      const targets = snapTargets(pw, ph, doc.style.margin_mm, others);
      const threshold = SNAP_PX / pxPerMm;
      const lines: Guide[] = [];
      if (d.handle.includes("e")) {
        const s = snapValues([box.x + box.w], targets.xs, threshold);
        if (s) {
          box = { ...box, w: box.w + s.delta };
          lines.push({ axis: "x", at: s.at });
        }
      }
      if (d.handle.includes("w")) {
        const s = snapValues([box.x], targets.xs, threshold);
        if (s) {
          box = { ...box, x: box.x + s.delta, w: box.w - s.delta };
          lines.push({ axis: "x", at: s.at });
        }
      }
      if (!d.isText && d.handle.includes("s")) {
        const s = snapValues([box.y + box.h], targets.ys, threshold);
        if (s) {
          box = { ...box, h: box.h + s.delta };
          lines.push({ axis: "y", at: s.at });
        }
      }
      if (!d.isText && d.handle.includes("n")) {
        const s = snapValues([box.y], targets.ys, threshold);
        if (s) {
          box = { ...box, y: box.y + s.delta, h: box.h - s.delta };
          lines.push({ axis: "y", at: s.at });
        }
      }
      setGuides({ page: d.page, lines });
    }
    // A text box keeps the height of its text. Only its width and left edge change.
    const next = d.isText ? { ...box, y: d.origin.y, h: d.origin.h } : box;
    onApply(setBoxes(doc, { [d.id]: next }), d.key);
  }

  function endDrag(event: ReactPointerEvent<HTMLDivElement>) {
    const d = drag.current;
    drag.current = null;
    setGuides(null);
    setMarquee(null);
    if (root.current?.hasPointerCapture(event.pointerId)) root.current.releasePointerCapture(event.pointerId);
    if (d && d.kind === "move" && d.started) {
      const frame = bounds(allElements(doc).filter((e) => d.ids.includes(e.id)));
      onMoved(d.ids, frame);
    }
  }

  function onDoubleClick(event: React.MouseEvent<HTMLDivElement>) {
    if (readOnly) return;
    const node = (event.target as HTMLElement).closest<HTMLElement>("[data-el]");
    if (!node) return;
    const el = allElements(doc).find((e) => e.id === node.dataset.el);
    if (el && el.kind === "text" && !el.locked) {
      onSelect([el.id]);
      onEdit(el.id);
    }
  }

  const selected = new Set(selection);
  const single = selection.length === 1 ? allElements(doc).find((e) => e.id === selection[0]) : undefined;

  return (
    <div
      ref={root}
      className={`cv-stage${readOnly ? " is-readonly" : ""}`}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={endDrag}
      onPointerCancel={endDrag}
      onDoubleClick={onDoubleClick}
      onFocus={(event) => {
        // Tabbing onto an element selects it when nothing is selected. Once something is selected,
        // moving the focus leaves the selection alone, so several can be gathered with Shift+Space.
        const node = (event.target as HTMLElement).closest<HTMLElement>("[data-el]");
        if (!node || readOnly || editing || selection.length > 0 || !node.matches(":focus-visible")) return;
        onSelect([node.dataset.el!]);
      }}
    >
      {doc.pages.map((page, pi) => {
        const live = page.elements.filter((e) => selected.has(e.id));
        const frame = live.length > 0 ? bounds(live) : null;
        return (
          <section
            key={page.id}
            className="cv-pagewrap"
            aria-label={`Page ${pi + 1} of ${doc.pages.length}`}
            style={{ width: pw * pxPerMm, height: ph * pxPerMm }}
          >
            <div
              className="cv-page"
              data-page={pi}
              style={{ width: mm(pw), height: mm(ph), transform: `scale(${zoom})`, transformOrigin: "top left" }}
            >
              {showMargins ? (
                <div
                  className="cv-margins"
                  aria-hidden="true"
                  style={{ left: mm(doc.style.margin_mm), top: mm(doc.style.margin_mm), right: mm(doc.style.margin_mm), bottom: mm(doc.style.margin_mm) }}
                />
              ) : null}
              {page.elements.map((el: CanvasElement, z) => (
                <ElementView
                  key={el.id}
                  el={el}
                  style={doc.style}
                  z={z + 1}
                  selected={selected.has(el.id)}
                  editing={editing === el.id}
                  readOnly={readOnly}
                  onBody={onBody}
                  onHeight={onHeight}
                  onEditor={onEditor}
                  onExitEdit={() => onEdit(null)}
                />
              ))}
              {!readOnly && frame && editing === null ? (
                <div
                  className={`cv-selection${live.length > 1 ? " is-multi" : ""}`}
                  aria-hidden="true"
                  style={{ left: mm(frame.x), top: mm(frame.y), width: mm(frame.w), height: mm(frame.h), zIndex: 9000 }}
                >
                  {single && !single.locked && live.length === 1
                    ? HANDLES[single.kind]!.map((h) => (
                        <span key={h} className={`cv-handle cv-handle--${h}`} data-handle={h} style={{ transform: `translate(-50%, -50%) scale(${1 / zoom})` }} />
                      ))
                    : null}
                </div>
              ) : null}
              {guides && guides.page === pi
                ? guides.lines.map((g, i) => (
                    <div
                      key={i}
                      className={`cv-guide cv-guide--${g.axis}`}
                      aria-hidden="true"
                      style={g.axis === "x" ? { left: mm(g.at) } : { top: mm(g.at) }}
                    />
                  ))
                : null}
              {marquee && marquee.page === pi ? (
                <div
                  className="cv-marquee"
                  aria-hidden="true"
                  style={{ left: mm(marquee.box.x), top: mm(marquee.box.y), width: mm(marquee.box.w), height: mm(marquee.box.h) }}
                />
              ) : null}
            </div>
          </section>
        );
      })}
    </div>
  );
}
