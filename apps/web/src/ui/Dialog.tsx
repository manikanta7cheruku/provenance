import { useEffect, useId, useRef } from "react";
import type { ReactNode } from "react";
import "./data.css";

interface DialogProps {
  open: boolean;
  title: string;
  children: ReactNode;
  /** Buttons for the bottom row. Put the safest action first. */
  actions: ReactNode;
  /** Called when the user presses Escape. The caller decides whether closing is allowed. */
  onClose: () => void;
}

/**
 * A modal on the native <dialog>: the browser traps focus, makes the rest of the page inert,
 * closes on Escape and returns focus to the element that opened it. Nothing here re-implements that.
 * Give the safest button `autoFocus` so a stray Enter cannot confirm anything destructive.
 */
export function Dialog({ open, title, children, actions, onClose }: DialogProps) {
  const dialog = useRef<HTMLDialogElement>(null);
  const titleId = useId();

  useEffect(() => {
    const element = dialog.current;
    if (!element) return;
    if (open && !element.open) element.showModal();
    if (!open && element.open) element.close();
  }, [open]);

  return (
    <dialog
      ref={dialog}
      className="dialog"
      aria-labelledby={titleId}
      onCancel={(event) => {
        // Escape fires "cancel". Keep the open state in the caller's hands.
        event.preventDefault();
        onClose();
      }}
    >
      <h2 id={titleId} className="dialog__title">
        {title}
      </h2>
      <div className="dialog__body">{children}</div>
      <div className="dialog__actions">{actions}</div>
    </dialog>
  );
}
