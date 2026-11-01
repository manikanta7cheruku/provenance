import { useEditor, EditorContent } from "@tiptap/react";
import { useEffect, useId } from "react";
import type { RichDoc } from "../../lib/studio-api";
import { richExtensions, RichToolbar } from "./RichToolbar";

interface RichFieldProps {
  label: string;
  hint?: string;
  value: RichDoc | null;
  onChange: (value: RichDoc | null) => void;
}

/**
 * Rich text for one block: bold, italic, underline, highlight and two kinds of list, nothing else.
 * The stored value is the editor's JSON. The server validates it again.
 */
export function RichField({ label, hint, value, onChange }: RichFieldProps) {
  const id = useId();
  const editor = useEditor({
    extensions: richExtensions,
    content: value ?? undefined,
    editorProps: {
      attributes: {
        id: `${id}-editor`,
        class: "rich__editor",
        role: "textbox",
        "aria-multiline": "true",
        "aria-labelledby": `${id}-label`,
        ...(hint ? { "aria-describedby": `${id}-hint` } : {}),
      },
    },
    onUpdate: ({ editor: e }) => onChange(e.isEmpty ? null : (e.getJSON() as RichDoc)),
  });

  // The same text can also be edited on the page. Keep this field in step with it, without
  // echoing the change back and without moving the caret while the person types here.
  useEffect(() => {
    if (!editor) return;
    const now = editor.isEmpty ? null : editor.getJSON();
    if (JSON.stringify(now) !== JSON.stringify(value)) {
      editor.commands.setContent(value ?? "", { emitUpdate: false });
    }
  }, [editor, value]);

  return (
    <div className="rich">
      <p className="field__label" id={`${id}-label`}>
        {label}
      </p>
      {hint ? (
        <p className="field__hint" id={`${id}-hint`}>
          {hint}
        </p>
      ) : null}
      <RichToolbar editor={editor} label={`Formatting for ${label}`} controls={`${id}-editor`} />
      <EditorContent editor={editor} />
    </div>
  );
}
