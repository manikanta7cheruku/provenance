import { EditorContent, useEditor } from "@tiptap/react";
import type { Editor } from "@tiptap/react";
import { memo, useEffect, useLayoutEffect, useRef } from "react";
import type { RichDoc } from "../../../lib/studio-api";
import { richExtensions } from "../RichToolbar";
import { elementCss, reactStyle } from "./css";
import { RichView, richText } from "./rich";
import type { CanvasElement, CanvasStyle, TextElement } from "./types";

const PX_PER_MM = 96 / 25.4;

interface ElementViewProps {
  el: CanvasElement;
  style: CanvasStyle;
  z: number;
  selected: boolean;
  editing: boolean;
  readOnly: boolean;
  onBody: (id: string, body: RichDoc | null) => void;
  onHeight: (id: string, h: number) => void;
  onEditor: (editor: Editor | null) => void;
  onExitEdit: () => void;
}

function describe(el: CanvasElement): string {
  const where = `${el.x.toFixed(1)} millimetres across, ${el.y.toFixed(1)} down`;
  if (el.kind === "text") {
    const text = richText(el.body).replace(/\s+/g, " ").trim();
    return `${el.name}. Text${text ? `: ${text.slice(0, 60)}` : ", empty"}. ${where}.${el.locked ? " Locked." : ""}`;
  }
  return `${el.name}. Shape. ${where}.${el.locked ? " Locked." : ""}`;
}

function InPlaceEditor({
  el,
  onBody,
  onEditor,
  onExit,
}: {
  el: TextElement;
  onBody: (id: string, body: RichDoc | null) => void;
  onEditor: (editor: Editor | null) => void;
  onExit: () => void;
}) {
  const editor = useEditor({
    extensions: richExtensions,
    content: el.body ?? undefined,
    autofocus: "end",
    editorProps: {
      attributes: {
        class: "cv-text-inner cv-editing",
        role: "textbox",
        "aria-multiline": "true",
        "aria-label": `Editing ${el.name}. Press Escape when you are done.`,
      },
      handleKeyDown: (_view, event) => {
        if (event.key === "Escape") {
          event.preventDefault();
          onExit();
          return true;
        }
        return false;
      },
    },
    onUpdate: ({ editor: e }) => onBody(el.id, e.isEmpty ? null : (e.getJSON() as RichDoc)),
    onBlur: ({ event }) => {
      const next = (event as FocusEvent).relatedTarget as HTMLElement | null;
      // Clicking the formatting bar keeps the editor; going anywhere else ends the edit.
      if (next?.closest(".cv-formatbar")) return;
      onExit();
    },
  });
  useEffect(() => {
    onEditor(editor);
    return () => onEditor(null);
  }, [editor, onEditor]);
  return <EditorContent editor={editor} />;
}

/**
 * One box on the page. Its look comes from css.ts (the server draws the same declarations for the
 * PDF). Text boxes are as tall as their text: the box measures its content and reports the height,
 * so nothing is cut off and the PDF has the same box.
 */
function ElementViewBase({ el, style, z, selected, editing, readOnly, onBody, onHeight, onEditor, onExitEdit }: ElementViewProps) {
  const inner = useRef<HTMLDivElement>(null);
  const css = reactStyle(elementCss(el, style, z));
  const text = el.kind === "text" ? el : null;

  useLayoutEffect(() => {
    const node = inner.current;
    if (el.kind !== "text" || !node) return;
    const report = () => {
      const h = Math.round(((node.offsetHeight / PX_PER_MM) * 10)) / 10;
      if (h >= 1 && Math.abs(h - el.h) > 0.15) onHeight(el.id, h);
    };
    report();
    const observer = new ResizeObserver(report);
    observer.observe(node);
    return () => observer.disconnect();
  }, [el.kind, el.id, el.h, el.w, text?.body, text?.size, text?.line_height, text?.font, text?.caps, style.font_pair, onHeight]);

  const common = {
    "data-el": el.id,
    role: "group" as const,
    "aria-label": `${describe(el)}${selected ? " Selected." : ""}`,
    "aria-roledescription": el.kind === "text" ? "text box" : "shape",
    tabIndex: readOnly ? -1 : 0,
    className: `cv-el cv-el--${el.kind}${selected ? " is-selected" : ""}${el.locked ? " is-locked" : ""}${editing ? " is-editing" : ""}`,
    style: css,
  };

  if (el.kind === "shape") return <div {...common} />;
  return (
    <div {...common}>
      <div ref={inner} className="cv-wrap">
        {editing ? (
          <InPlaceEditor el={el} onBody={onBody} onEditor={onEditor} onExit={onExitEdit} />
        ) : (
          <div className={`cv-text-inner${el.body ? "" : " is-empty"}`} data-placeholder={`Click to add ${el.name.toLowerCase()}`}>
            <RichView doc={el.body} />
          </div>
        )}
      </div>
    </div>
  );
}

export const ElementView = memo(ElementViewBase);
