import { useRef } from "react";
import type { KeyboardEvent, ReactNode } from "react";
import type { Editor } from "@tiptap/react";
import { RichToolbar } from "../RichToolbar";
import type { AtsReport } from "./ats";
import type { Order } from "./edit";
import type { AlignMode } from "./geometry";

export interface CanvasActions {
  addText: () => void;
  addBox: () => void;
  addRule: () => void;
  undo: () => void;
  redo: () => void;
  duplicate: () => void;
  remove: () => void;
  group: () => void;
  ungroup: () => void;
  lock: (locked: boolean) => void;
  order: (how: Order) => void;
  align: (mode: AlignMode) => void;
  distribute: (axis: "x" | "y") => void;
  setZoom: (zoom: number) => void;
  fit: () => void;
  toggleMargins: () => void;
  toggleAts: () => void;
  edit: () => void;
}

interface CanvasToolbarProps {
  actions: CanvasActions;
  count: number;
  anyGrouped: boolean;
  allLocked: boolean;
  canUndo: boolean;
  canRedo: boolean;
  zoom: number;
  fitted: boolean;
  showMargins: boolean;
  ats: AtsReport;
  atsOpen: boolean;
  /** The on-page editor while text is being edited. Its formatting bar replaces the arrange tools. */
  editor: Editor | null;
}

const ZOOMS = [0.5, 0.75, 1, 1.25, 1.5, 2];

function Group({ label, children }: { label: string; children: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    const items = Array.from(ref.current?.querySelectorAll<HTMLButtonElement>("button:not(:disabled)") ?? []);
    const index = items.findIndex((b) => b === document.activeElement);
    if (index < 0) return;
    let next = index;
    if (event.key === "ArrowRight") next = (index + 1) % items.length;
    else if (event.key === "ArrowLeft") next = (index - 1 + items.length) % items.length;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = items.length - 1;
    else return;
    event.preventDefault();
    items.forEach((b, i) => (b.tabIndex = i === next ? 0 : -1));
    items[next]?.focus();
  }
  return (
    <div ref={ref} className="cv-group" role="toolbar" aria-label={label} onKeyDown={onKeyDown}>
      {children}
    </div>
  );
}

function Btn({ children, label, disabled, pressed, onClick, primary }: { children: ReactNode; label?: string; disabled?: boolean; pressed?: boolean; onClick: () => void; primary?: boolean }) {
  return (
    <button type="button" className={`cv-btn${primary ? " cv-btn--primary" : ""}`} aria-label={label} aria-pressed={pressed} disabled={disabled} onClick={onClick}>
      {children}
    </button>
  );
}

/** The tools above the page. Every group is a toolbar: one tab stop, arrow keys inside it. */
export function CanvasToolbar(props: CanvasToolbarProps) {
  const { actions: a, count, anyGrouped, allLocked, canUndo, canRedo, zoom, fitted, showMargins, ats, atsOpen, editor } = props;
  const some = count > 0;
  const several = count > 1;
  const issues = ats.issues.length;
  return (
    <div className="cv-toolbar">
      {editor ? (
        <div className="cv-formatbar">
          <RichToolbar editor={editor} label="Formatting for the text being edited" />
          <span className="field__hint">Press Escape to finish editing.</span>
        </div>
      ) : null}
      <Group label="Add">
        <Btn onClick={a.addText} primary>
          Add text
        </Btn>
        <Btn onClick={a.addBox}>Add box</Btn>
        <Btn onClick={a.addRule}>Add rule</Btn>
      </Group>
      <Group label="History">
        <Btn disabled={!canUndo} onClick={a.undo} label="Undo">
          Undo
        </Btn>
        <Btn disabled={!canRedo} onClick={a.redo} label="Redo">
          Redo
        </Btn>
      </Group>
      <Group label="Selection">
        <Btn disabled={count !== 1} onClick={a.edit} label="Edit text">
          Edit text
        </Btn>
        <Btn disabled={!some} onClick={a.duplicate}>
          Duplicate
        </Btn>
        <Btn disabled={!some} onClick={a.remove}>
          Delete
        </Btn>
        <Btn disabled={!several} onClick={a.group}>
          Group
        </Btn>
        <Btn disabled={!anyGrouped} onClick={a.ungroup}>
          Ungroup
        </Btn>
        <Btn disabled={!some} onClick={() => a.lock(!allLocked)} pressed={allLocked} label={allLocked ? "Allow edits" : "Lock"}>
          {allLocked ? "Allow edits" : "Lock"}
        </Btn>
      </Group>
      <Group label="Stacking">
        <Btn disabled={!some} onClick={() => a.order("forward")}>
          Forward
        </Btn>
        <Btn disabled={!some} onClick={() => a.order("backward")}>
          Backward
        </Btn>
        <Btn disabled={!some} onClick={() => a.order("front")} label="To front">
          To front
        </Btn>
        <Btn disabled={!some} onClick={() => a.order("back")} label="To back">
          To back
        </Btn>
      </Group>
      <Group label="Align">
        {(["left", "center", "right", "top", "middle", "bottom"] as AlignMode[]).map((mode) => (
          <Btn key={mode} disabled={!some} onClick={() => a.align(mode)} label={`Align ${mode}`}>
            {mode[0]!.toUpperCase() + mode.slice(1)}
          </Btn>
        ))}
        <Btn disabled={count < 3} onClick={() => a.distribute("x")}>
          Space across
        </Btn>
        <Btn disabled={count < 3} onClick={() => a.distribute("y")}>
          Space down
        </Btn>
      </Group>
      <Group label="View">
        <Btn onClick={() => a.setZoom(Math.max(0.25, Math.round((zoom - 0.25) * 100) / 100))} label="Zoom out">
          Zoom out
        </Btn>
        <label className="cv-zoom">
          <span className="visually-hidden">Zoom</span>
          <select
            className="cv-select"
            value={fitted ? "fit" : String(zoom)}
            onChange={(e) => (e.target.value === "fit" ? a.fit() : a.setZoom(Number(e.target.value)))}
          >
            <option value="fit">Fit width</option>
            {ZOOMS.map((z) => (
              <option key={z} value={z}>
                {Math.round(z * 100)}%
              </option>
            ))}
            {!fitted && !ZOOMS.includes(zoom) ? <option value={zoom}>{Math.round(zoom * 100)}%</option> : null}
          </select>
        </label>
        <Btn onClick={() => a.setZoom(Math.min(3, Math.round((zoom + 0.25) * 100) / 100))} label="Zoom in">
          Zoom in
        </Btn>
        <Btn onClick={a.toggleMargins} pressed={showMargins} label="Show margins">
          Show margins
        </Btn>
      </Group>
      <Group label="Layout check">
        <Btn onClick={a.toggleAts} pressed={atsOpen}>
          {ats.safe && issues === 0 ? "Layout check: reads well" : ats.safe ? `Layout check: ${issues} ${issues === 1 ? "note" : "notes"}` : `Layout check: ${issues} ${issues === 1 ? "issue" : "issues"}`}
        </Btn>
      </Group>
    </div>
  );
}
