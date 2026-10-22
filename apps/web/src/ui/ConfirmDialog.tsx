import { useEffect, useId, useRef } from "react";
import type { ReactNode } from "react";
import { ActionButton } from "./ActionButton";
import "./data.css";

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  children: ReactNode;
  confirmLabel: string;
  danger?: boolean;
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

/**
 * A confirmation on the native <dialog>: the browser traps focus, makes the rest of the page
 * inert, closes on Escape and returns focus to the button that opened it.
 * Focus starts on Cancel so a stray Enter never confirms a destructive action.
 */
export function ConfirmDialog({
  open,
  title,
  children,
  confirmLabel,
  danger = false,
  busy = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
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
      className="confirm"
      aria-labelledby={titleId}
      onCancel={(event) => {
        event.preventDefault();
        if (!busy) onCancel();
      }}
    >
      <h2 id={titleId} className="confirm__title">
        {title}
      </h2>
      <div className="confirm__body">{children}</div>
      <div className="confirm__actions">
        <ActionButton onClick={onCancel} disabled={busy} autoFocus>
          Cancel
        </ActionButton>
        <ActionButton variant={danger ? "danger" : "primary"} onClick={onConfirm} disabled={busy}>
          {busy ? "Working\u2026" : confirmLabel}
        </ActionButton>
      </div>
    </dialog>
  );
}
