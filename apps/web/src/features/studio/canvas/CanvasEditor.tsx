import type { Editor } from "@tiptap/react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { KeyboardEvent } from "react";
import type { RichDoc, StudioOptions } from "../../../lib/studio-api";
import { ActionButton } from "../../../ui";
import { analyzeAts } from "./ats";
import { CanvasToolbar } from "./CanvasToolbar";
import type { CanvasActions } from "./CanvasToolbar";
import {
  addElement,
  addPage,
  alignElements,
  deleteElements,
  distributeElements,
  duplicateElements,
  expandSelection,
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
import type { Order } from "./edit";
import type { AlignMode, Box } from "./geometry";
import { History } from "./history";
import { Inspector } from "./Inspector";
import { Stage } from "./Stage";
import { allElements, findElement, pageSize } from "./types";
import type { CanvasDoc, CanvasElement, CanvasStyle } from "./types";
import { fontFaceCss } from "./css";

const CSS_PX_PER_MM = 96 / 25.4;

interface CanvasEditorProps {
  doc: CanvasDoc;
  onChange: (next: CanvasDoc) => void;
  options: StudioOptions;
  /** Changes when the document is replaced from outside (restore, reload). Undo history starts over. */
  epoch: number;
  announce: (message: string) => void;
}

function useWide(): boolean {
  const query = "(min-width: 980px)";
  const [wide, setWide] = useState(() => (typeof window.matchMedia === "function" ? window.matchMedia(query).matches : true));
  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const media = window.matchMedia(query);
    const update = () => setWide(media.matches);
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);
  return wide;
}

function isTyping(target: EventTarget | null): boolean {
  const node = target as HTMLElement | null;
  if (!node) return false;
  return node.matches?.("input, textarea, select, [contenteditable='true']") || !!node.closest?.("[contenteditable='true']");
}

/**
 * The free canvas editor: tools above, the pages in the middle, the properties on the right.
 * It is controlled: the document comes in as a prop and every change goes out through onChange,
 * where the studio autosaves it. All drawing is local, so typing and dragging are instant.
 */
export function CanvasEditor({ doc, onChange, options, epoch, announce }: CanvasEditorProps) {
  const wide = useWide();
  const docRef = useRef(doc);
  docRef.current = doc;
  const history = useRef(new History<CanvasDoc>());
  const [selection, setSelection] = useState<string[]>([]);
  const [editing, setEditing] = useState<string | null>(null);
  const [editor, setEditor] = useState<Editor | null>(null);
  const [zoom, setZoomState] = useState(1);
  const [fitted, setFitted] = useState(true);
  const [showMargins, setShowMargins] = useState(true);
  const [atsOpen, setAtsOpen] = useState(false);
  const [, force] = useState(0);
  const viewport = useRef<HTMLDivElement>(null);
  const announceTimer = useRef<number | null>(null);

  // A document that arrives from outside starts a new undo history.
  useEffect(() => {
    history.current.clear();
    setSelection([]);
    setEditing(null);
    force((n) => n + 1);
  }, [epoch]);

  // Drop selected ids that no longer exist (after undo, delete, restore).
  useEffect(() => {
    const live = new Set(allElements(doc).map((e) => e.id));
    setSelection((current) => (current.every((id) => live.has(id)) ? current : current.filter((id) => live.has(id))));
    setEditing((current) => (current && !live.has(current) ? null : current));
  }, [doc]);

  const say = useCallback(
    (message: string) => {
      if (announceTimer.current !== null) window.clearTimeout(announceTimer.current);
      announceTimer.current = window.setTimeout(() => announce(message), 350);
    },
    [announce],
  );

  const apply = useCallback(
    (next: CanvasDoc, key?: string) => {
      if (next === docRef.current) return;
      history.current.record(docRef.current, key);
      docRef.current = next;
      onChange(next);
      force((n) => n + 1);
    },
    [onChange],
  );

  /** A change that is a result of drawing, not of the person: a text box taking the height of its text. */
  const quiet = useCallback(
    (next: CanvasDoc) => {
      if (next === docRef.current) return;
      docRef.current = next;
      onChange(next);
    },
    [onChange],
  );

  // ---- zoom
  const fit = useCallback(() => {
    const width = viewport.current?.clientWidth ?? 800;
    const [pw] = pageSize(docRef.current.style);
    const z = Math.min(1.5, Math.max(0.25, (width - 40) / (pw * CSS_PX_PER_MM)));
    setZoomState(Math.round(z * 100) / 100);
    setFitted(true);
  }, []);
  useEffect(() => {
    if (!fitted) return;
    fit();
    const node = viewport.current;
    if (!node) return;
    const observer = new ResizeObserver(fit);
    observer.observe(node);
    return () => observer.disconnect();
  }, [fitted, fit, doc.style.paper, wide]);

  const setZoom = useCallback((z: number) => {
    setZoomState(z);
    setFitted(false);
  }, []);

  // ---- selection helpers
  const selectedEls = useMemo(() => allElements(doc).filter((e) => selection.includes(e.id)), [doc, selection]);
  const ats = useMemo(() => analyzeAts(doc), [doc]);
  const pageOfSelection = () => {
    const first = selection[0];
    const found = first ? findElement(docRef.current, first) : null;
    return found?.page ?? 0;
  };

  const select = useCallback((ids: string[]) => setSelection(expandSelection(docRef.current, ids)), []);

  // ---- actions
  const onBody = useCallback(
    (id: string, body: RichDoc | null) => {
      apply(updateElement(docRef.current, id, { body } as Partial<CanvasElement>), `text-${id}`);
    },
    [apply],
  );
  const onHeight = useCallback(
    (id: string, h: number) => {
      quiet(updateElement(docRef.current, id, { h }));
    },
    [quiet],
  );

  const patchSelected = useCallback(
    (patch: Partial<CanvasElement>, key: string) => {
      let next = docRef.current;
      for (const id of selection) next = updateElement(next, id, patch);
      apply(next, key);
    },
    [apply, selection],
  );
  const setBox = useCallback(
    (patch: { x?: number; y?: number; w?: number }, key: string) => {
      const id = selection[0];
      const found = id ? findElement(docRef.current, id) : null;
      if (!found) return;
      const [pw, ph] = pageSize(docRef.current.style);
      const el = found.element;
      const box: Box = { x: patch.x ?? el.x, y: patch.y ?? el.y, w: patch.w ?? el.w, h: el.h };
      box.x = Math.min(Math.max(box.x, 0), pw - 1);
      box.w = Math.min(box.w, pw - box.x);
      box.y = Math.min(Math.max(box.y, 0), ph - 1);
      apply(setBoxes(docRef.current, { [el.id]: box }), key);
    },
    [apply, selection],
  );

  const addAndSelect = useCallback(
    (make: (doc: CanvasDoc) => CanvasElement, what: string) => {
      const page = pageOfSelection();
      const el = make(docRef.current);
      const next = addElement(docRef.current, page, el);
      if (next === docRef.current) {
        announce("The resume has the most elements it can hold.");
        return;
      }
      apply(next);
      setSelection([el.id]);
      if (el.kind === "text") setEditing(el.id);
      say(`${what} added.`);
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [apply, announce, say, selection],
  );

  const ids = selection;
  const actions: CanvasActions = {
    addText: () => addAndSelect((d) => makeText(d, pageOfSelection()), "Text box"),
    addBox: () => addAndSelect((d) => makeShape(d), "Box"),
    addRule: () => addAndSelect((d) => makeRule(d), "Rule"),
    undo: () => {
      const prev = history.current.undo(docRef.current);
      if (prev) {
        docRef.current = prev;
        onChange(prev);
        setEditing(null);
        force((n) => n + 1);
        say("Undone.");
      }
    },
    redo: () => {
      const next = history.current.redo(docRef.current);
      if (next) {
        docRef.current = next;
        onChange(next);
        setEditing(null);
        force((n) => n + 1);
        say("Redone.");
      }
    },
    duplicate: () => {
      if (ids.length === 0) return;
      const result = duplicateElements(docRef.current, ids);
      apply(result.doc);
      setSelection(result.ids);
      say(`${result.ids.length === 1 ? "Duplicated" : `${result.ids.length} elements duplicated`}.`);
    },
    remove: () => {
      if (ids.length === 0) return;
      apply(deleteElements(docRef.current, ids));
      setSelection([]);
      setEditing(null);
      say(`${ids.length === 1 ? "Element" : `${ids.length} elements`} deleted. You can undo.`);
    },
    group: () => {
      apply(groupElements(docRef.current, ids));
      say("Grouped. They now select and move together.");
    },
    ungroup: () => {
      apply(ungroupElements(docRef.current, ids));
      say("Ungrouped.");
    },
    lock: (locked) => {
      apply(lockElements(docRef.current, ids, locked));
      say(locked ? "Locked." : "Editing allowed.");
    },
    order: (how: Order) => {
      apply(reorder(docRef.current, ids, how));
      say(`Moved ${how === "front" ? "to the front" : how === "back" ? "to the back" : how}.`);
    },
    align: (mode: AlignMode) => {
      apply(alignElements(docRef.current, ids, mode));
      say(`Aligned ${mode}.`);
    },
    distribute: (axis) => {
      apply(distributeElements(docRef.current, ids, axis));
      say(axis === "x" ? "Spaced evenly across." : "Spaced evenly down.");
    },
    setZoom,
    fit: () => setFitted(true),
    toggleMargins: () => setShowMargins((v) => !v),
    toggleAts: () => setAtsOpen((v) => !v),
    edit: () => {
      const el = selectedEls[0];
      if (el && el.kind === "text" && !el.locked) setEditing(el.id);
    },
  };

  // ---- keyboard
  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (!wide) return;
    const target = event.target as HTMLElement;
    const inStage = !!viewport.current?.contains(target);
    const mod = event.ctrlKey || event.metaKey;
    const key = event.key.toLowerCase();

    // Undo and redo work everywhere except inside a text field, which has its own.
    if (mod && !isTyping(target) && (key === "z" || key === "y")) {
      event.preventDefault();
      if (key === "y" || event.shiftKey) actions.redo();
      else actions.undo();
      return;
    }
    if (!inStage || editing || isTyping(target)) return;

    const arrows: Record<string, [number, number]> = { arrowleft: [-1, 0], arrowright: [1, 0], arrowup: [0, -1], arrowdown: [0, 1] };
    if (key in arrows && ids.length > 0) {
      event.preventDefault();
      const [ax, ay] = arrows[key]!;
      const step = event.shiftKey ? 5 : mod ? 0.1 : 0.5;
      if (event.altKey && selectedEls.length === 1) {
        const el = selectedEls[0]!;
        if (el.locked) return;
        const w = Math.max(5, el.w + ax * step);
        const h = el.kind === "shape" ? Math.max(0.2, el.h + ay * step) : el.h;
        apply(setBoxes(docRef.current, { [el.id]: { x: el.x, y: el.y, w, h } }), "keysize");
        say(`${el.name} is ${w.toFixed(1)} millimetres wide${el.kind === "shape" ? ` and ${h.toFixed(1)} tall` : ""}.`);
        return;
      }
      const next = moveElements(docRef.current, ids, ax * step, ay * step);
      apply(next, "nudge");
      const el = findElement(next, ids[0]!)?.element;
      if (el) say(`${ids.length > 1 ? `${ids.length} elements` : el.name} at ${el.x.toFixed(1)} across, ${el.y.toFixed(1)} down.`);
      return;
    }
    if ((key === "delete" || key === "backspace") && ids.length > 0) {
      event.preventDefault();
      actions.remove();
    } else if ((key === "enter" || key === "f2") && selectedEls.length === 1 && selectedEls[0]!.kind === "text") {
      event.preventDefault();
      actions.edit();
    } else if (key === " ") {
      // Space selects the focused element. Shift+Space adds it to the selection or removes it,
      // which is the keyboard way to select several.
      const id = target.closest<HTMLElement>("[data-el]")?.dataset.el;
      if (id && !event.shiftKey) {
        event.preventDefault();
        setSelection(expandSelection(docRef.current, [id]));
      } else if (id) {
        event.preventDefault();
        const group = expandSelection(docRef.current, [id]);
        setSelection((current) => (group.every((g) => current.includes(g)) ? current.filter((s) => !group.includes(s)) : [...new Set([...current, ...group])]));
        say(`${selection.includes(id) ? "Removed from" : "Added to"} the selection.`);
      }
    } else if (key === "escape") {
      setSelection([]);
    } else if (mod && key === "a") {
      event.preventDefault();
      const page = docRef.current.pages[pageOfSelection()];
      setSelection(expandSelection(docRef.current, page?.elements.map((e) => e.id) ?? []));
    } else if (mod && key === "d") {
      event.preventDefault();
      actions.duplicate();
    } else if (mod && key === "g") {
      event.preventDefault();
      if (event.shiftKey) actions.ungroup();
      else actions.group();
    } else if (mod && (event.key === "]" || event.key === "[")) {
      event.preventDefault();
      actions.order(event.key === "]" ? (event.shiftKey ? "front" : "forward") : event.shiftKey ? "back" : "backward");
    } else if (mod && (key === "=" || key === "+")) {
      event.preventDefault();
      setZoom(Math.min(3, zoom + 0.25));
    } else if (mod && key === "-") {
      event.preventDefault();
      setZoom(Math.max(0.25, zoom - 0.25));
    }
  }

  const stylePatch = (patch: Partial<CanvasStyle>) => apply(setCanvasStyle(docRef.current, patch), "style");

  return (
    <div className="cv-editor" onKeyDown={onKeyDown}>
      <style>{fontFaceCss()}</style>
      {wide ? (
        <CanvasToolbar
          actions={actions}
          count={selection.length}
          anyGrouped={selectedEls.some((e) => e.group)}
          allLocked={selectedEls.length > 0 && selectedEls.every((e) => e.locked)}
          canUndo={history.current.canUndo}
          canRedo={history.current.canRedo}
          zoom={zoom}
          fitted={fitted}
          showMargins={showMargins}
          ats={ats}
          atsOpen={atsOpen}
          editor={editor}
        />
      ) : (
        <p className="job__note" role="status">
          The free canvas needs a wider screen to edit. You can still see your resume here and make a PDF. Use a laptop or a tablet held sideways to move things around.
        </p>
      )}
      {atsOpen ? (
        <section className="cv-ats" aria-label="Layout check">
          <p className="cv-ats__head">
            {ats.issues.length === 0
              ? "This layout reads well in applicant tracking systems: one column, nothing overlapping, no text on shapes."
              : ats.safe
                ? "Nothing here should confuse a tracking system. A few notes:"
                : "Some systems may misread this layout. This is advice, you can still use it:"}
          </p>
          <ul>
            {ats.issues.map((issue, i) => (
              <li key={`${issue.kind}${i}`}>
                {issue.message}{" "}
                <ActionButton onClick={() => select(issue.ids)}>Show</ActionButton>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
      <div className="cv-body">
        <div className="cv-viewport" ref={viewport}>
          <Stage
            doc={doc}
            selection={selection}
            editing={editing}
            zoom={zoom}
            showMargins={showMargins}
            readOnly={!wide}
            onSelect={select}
            onApply={apply}
            onBody={onBody}
            onHeight={onHeight}
            onEditor={setEditor}
            onEdit={setEditing}
            onMoved={(movedIds, frame) => {
              const el = findElement(docRef.current, movedIds[0]!)?.element;
              say(`Moved ${movedIds.length > 1 ? `${movedIds.length} elements` : (el?.name ?? "element")} to ${frame.x.toFixed(1)} across, ${frame.y.toFixed(1)} down.`);
            }}
          />
        </div>
        {wide ? (
          <Inspector
            doc={doc}
            selected={selectedEls}
            options={options}
            epoch={epoch}
            selection={selection}
            onSelect={select}
            onOrder={(orderIds, how) => apply(reorder(docRef.current, orderIds, how))}
            onLock={(id, locked) => apply(lockElements(docRef.current, [id], locked))}
            onPatch={patchSelected}
            onBox={setBox}
            onBody={onBody}
            onStyle={stylePatch}
            onAddPage={() => apply(addPage(docRef.current))}
            onRemovePage={(index) => {
              apply(removePage(docRef.current, index));
              setSelection([]);
            }}
            onMoveToPage={(page) => {
              apply(moveToPage(docRef.current, selection, page));
              say(`Moved to page ${page + 1}.`);
            }}
          />
        ) : null}
      </div>
    </div>
  );
}
