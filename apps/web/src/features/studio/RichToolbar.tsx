import { useEditorState } from "@tiptap/react";
import type { Editor } from "@tiptap/react";
import Highlight from "@tiptap/extension-highlight";
import StarterKit from "@tiptap/starter-kit";
import { useRef } from "react";
import type { KeyboardEvent, ReactNode } from "react";

/**
 * The formatting toolbar and the editor schema shared by the side field and the on-page editor.
 * The schema has no headings, links or images, so pasted content cannot bring them in.
 */
export const richExtensions = [
  StarterKit.configure({
    heading: false,
    blockquote: false,
    codeBlock: false,
    code: false,
    strike: false,
    horizontalRule: false,
    link: false,
    trailingNode: false,
  }),
  Highlight.configure({ multicolor: false }),
];

interface Command {
  key: string;
  label: string;
  shortcut: string;
  active: (editor: Editor) => boolean;
  run: (editor: Editor) => void;
  glyph: ReactNode;
  glyphClass: string;
}

/** Picture buttons carry no visible text, so their accessible names cannot disagree with it. */
function ListIcon({ numbered }: { numbered: boolean }) {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="currentColor" focusable="false">
      {[3, 9, 15].map((y) =>
        numbered ? (
          <rect key={y} x="1" y={y - 1.5} width="3" height="3" rx="0.5" />
        ) : (
          <circle key={y} cx="2.5" cy={y} r="1.6" />
        ),
      )}
      {[3, 9, 15].map((y) => (
        <rect key={`l${y}`} x="7" y={y - 1} width="10" height="2" rx="0.5" />
      ))}
    </svg>
  );
}

const COMMANDS: Command[] = [
  { key: "bold", label: "Bold", shortcut: "Ctrl+B", active: (e) => e.isActive("bold"), run: (e) => e.chain().focus().toggleBold().run(), glyph: "B", glyphClass: "rich__g--bold" },
  { key: "italic", label: "Italic", shortcut: "Ctrl+I", active: (e) => e.isActive("italic"), run: (e) => e.chain().focus().toggleItalic().run(), glyph: "I", glyphClass: "rich__g--italic" },
  { key: "underline", label: "Underline", shortcut: "Ctrl+U", active: (e) => e.isActive("underline"), run: (e) => e.chain().focus().toggleUnderline().run(), glyph: "U", glyphClass: "rich__g--underline" },
  { key: "highlight", label: "Highlight", shortcut: "Ctrl+Shift+H", active: (e) => e.isActive("highlight"), run: (e) => e.chain().focus().toggleHighlight().run(), glyph: "H", glyphClass: "rich__g--highlight" },
  { key: "bullets", label: "Bulleted list", shortcut: "Ctrl+Shift+8", active: (e) => e.isActive("bulletList"), run: (e) => e.chain().focus().toggleBulletList().run(), glyph: <ListIcon numbered={false} />, glyphClass: "" },
  { key: "numbers", label: "Numbered list", shortcut: "Ctrl+Shift+7", active: (e) => e.isActive("orderedList"), run: (e) => e.chain().focus().toggleOrderedList().run(), glyph: <ListIcon numbered />, glyphClass: "" },
];

interface RichToolbarProps {
  editor: Editor | null;
  label: string;
  controls?: string;
}

/** An ARIA toolbar: one tab stop, arrow keys, Home and End move between the buttons. */
export function RichToolbar({ editor, label, controls }: RichToolbarProps) {
  const toolbar = useRef<HTMLDivElement>(null);
  const state = useEditorState({
    editor,
    selector: ({ editor: e }) =>
      Object.fromEntries(COMMANDS.map((c) => [c.key, e ? c.active(e) : false])) as Record<string, boolean>,
  });

  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    const buttons = Array.from(toolbar.current?.querySelectorAll<HTMLButtonElement>("button") ?? []);
    const index = buttons.findIndex((b) => b === document.activeElement);
    if (index < 0) return;
    let next = index;
    if (event.key === "ArrowRight") next = (index + 1) % buttons.length;
    else if (event.key === "ArrowLeft") next = (index - 1 + buttons.length) % buttons.length;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = buttons.length - 1;
    else return;
    event.preventDefault();
    buttons.forEach((b, i) => (b.tabIndex = i === next ? 0 : -1));
    buttons[next]?.focus();
  }

  return (
    <div
      ref={toolbar}
      className="rich__toolbar"
      role="toolbar"
      aria-label={label}
      aria-controls={controls}
      onKeyDown={onKeyDown}
    >
      {COMMANDS.map((command, index) => (
        <button
          key={command.key}
          type="button"
          className="rich__btn"
          tabIndex={index === 0 ? 0 : -1}
          aria-pressed={state?.[command.key] ?? false}
          aria-label={command.label}
          title={`${command.label} (${command.shortcut})`}
          disabled={!editor}
          onMouseDown={(event) => event.preventDefault()}
          onClick={() => editor && command.run(editor)}
        >
          <span aria-hidden="true" className={command.glyphClass}>
            {command.glyph}
          </span>
        </button>
      ))}
    </div>
  );
}
