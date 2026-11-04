import { useEffect } from "react";
import { ActionButton } from "../../ui";

export interface ToastState {
  id: number;
  message: string;
  undoLabel: string | null;
}

const SHOW_MS = 12_000;

/** What just happened, with Undo when the action can be taken back. It stays long enough to read,
 * is announced politely, and is plain buttons so the keyboard reaches it. */
export function UndoToast({
  toast,
  busy,
  onUndo,
  onClose,
}: {
  toast: ToastState | null;
  busy: boolean;
  onUndo: () => void;
  onClose: () => void;
}) {
  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(onClose, SHOW_MS);
    return () => window.clearTimeout(timer);
  }, [toast, onClose]);

  return (
    <div className="bench__toastslot" role="status" aria-live="polite">
      {toast ? (
        <p className="bench__toast">
          <span>{toast.message}</span>
          {toast.undoLabel ? (
            <ActionButton disabled={busy} onClick={onUndo}>
              {toast.undoLabel}
            </ActionButton>
          ) : null}
          <ActionButton onClick={onClose} aria-label="Close this message">
            Close
          </ActionButton>
        </p>
      ) : null}
    </div>
  );
}
