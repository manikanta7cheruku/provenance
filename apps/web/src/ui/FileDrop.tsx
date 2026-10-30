import { useId, useState } from "react";
import type { DragEvent } from "react";
import "./controls.css";

interface FileDropProps {
  label: string;
  /** Help text: what is accepted and why. Linked to the input for screen readers. */
  hint: string;
  /** Allowed extensions, lower case, with the dot. Example: [".pdf", ".docx"]. */
  extensions: readonly string[];
  maxBytes: number;
  /** The file the caller currently holds, shown by name and size. */
  file: { name: string; size: number } | null;
  /** Called with a file that passed the browser-side checks. The server checks again. */
  onSelect: (file: File) => void;
  /** Called with a plain sentence when the browser-side checks reject a file. */
  onReject: (message: string) => void;
  /** Error from the caller (for example from the server). Marks the control invalid. */
  error?: string | undefined;
  disabled?: boolean;
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** The browser-side checks. These improve the experience only; the server is the authority. */
export function checkFile(file: File, extensions: readonly string[], maxBytes: number): string | null {
  const name = file.name.toLowerCase();
  if (!extensions.some((extension) => name.endsWith(extension))) {
    return `This file type is not supported. Choose a ${extensions.join(" or ")} file.`;
  }
  if (file.size === 0) return "This file is empty. Choose a different file.";
  if (file.size > maxBytes) {
    return `This file is ${formatBytes(file.size)}, which is over the ${formatBytes(maxBytes)} limit. Choose a smaller file.`;
  }
  return null;
}

/**
 * Choose or drop one file. The native file input stays in the page, so keyboard and screen
 * reader users get the browser's own control. Dragging is an extra, never the only way.
 */
export function FileDrop({
  label,
  hint,
  extensions,
  maxBytes,
  file,
  onSelect,
  onReject,
  error,
  disabled = false,
}: FileDropProps) {
  const id = useId();
  const hintId = `${id}-hint`;
  const errorId = `${id}-error`;
  const [dragging, setDragging] = useState(false);

  function handle(candidate: File | undefined) {
    if (!candidate) return;
    const problem = checkFile(candidate, extensions, maxBytes);
    if (problem) onReject(problem);
    else onSelect(candidate);
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    if (!disabled) handle(event.dataTransfer.files[0]);
  }

  return (
    <div className="field">
      <label className="field__label" htmlFor={id}>
        {label}
      </label>
      <p id={hintId} className="field__hint">
        {hint}
      </p>
      <div
        className="filedrop"
        data-dragging={dragging}
        data-invalid={error ? true : undefined}
        onDragOver={(event) => {
          event.preventDefault();
          if (!disabled) setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
      >
        <input
          id={id}
          className="filedrop__input"
          type="file"
          accept={extensions.join(",")}
          disabled={disabled}
          aria-invalid={error ? true : undefined}
          aria-describedby={[hintId, error ? errorId : null].filter(Boolean).join(" ")}
          onChange={(event) => {
            handle(event.target.files?.[0]);
            // Allow choosing the same file again after fixing it.
            event.target.value = "";
          }}
        />
        <p className="filedrop__text" aria-live="polite">
          {file ? (
            <>
              <span className="filedrop__name">{file.name}</span> <span>({formatBytes(file.size)})</span>
            </>
          ) : (
            "Drop a file here, or use the button above to choose one."
          )}
        </p>
      </div>
      {error ? (
        <p id={errorId} className="field__error" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}
