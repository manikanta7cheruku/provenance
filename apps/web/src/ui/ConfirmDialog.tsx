import type { ReactNode } from "react";
import { ActionButton } from "./ActionButton";
import { Dialog } from "./Dialog";

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
 * A confirmation built on Dialog. Focus starts on Cancel so a stray Enter never confirms a
 * destructive action, and Escape is ignored while the action is running.
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
  return (
    <Dialog
      open={open}
      title={title}
      onClose={() => {
        if (!busy) onCancel();
      }}
      actions={
        <>
          <ActionButton onClick={onCancel} disabled={busy} autoFocus>
            Cancel
          </ActionButton>
          <ActionButton variant={danger ? "danger" : "primary"} onClick={onConfirm} disabled={busy}>
            {busy ? "Working…" : confirmLabel}
          </ActionButton>
        </>
      }
    >
      {children}
    </Dialog>
  );
}
