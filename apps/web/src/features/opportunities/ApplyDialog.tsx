import { useEffect, useState } from "react";
import { ConfirmDialog, TextField } from "../../ui";

export function todayLocal(): string {
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${now.getFullYear()}-${month}-${day}`;
}

/** Confirms "I applied", naming the company and role, and asks which day. Reversible. */
export function ApplyDialog({
  open,
  label,
  busy,
  onCancel,
  onConfirm,
}: {
  open: boolean;
  /** The job as a person would say it: "Backend engineer at Acme". */
  label: string;
  busy: boolean;
  onCancel: () => void;
  onConfirm: (day: string) => void;
}) {
  const [day, setDay] = useState(todayLocal());
  useEffect(() => {
    if (open) setDay(todayLocal());
  }, [open]);
  return (
    <ConfirmDialog
      open={open}
      title="Mark this job as applied?"
      confirmLabel="Mark applied"
      busy={busy}
      onCancel={onCancel}
      onConfirm={() => onConfirm(day || todayLocal())}
    >
      <p>
        This records that you applied for {label} on the employer's site. Provenance never applies for you. You can undo
        this later.
      </p>
      <TextField
        label="The day you applied"
        type="date"
        value={day}
        max={todayLocal()}
        onChange={(event) => setDay(event.target.value)}
      />
    </ConfirmDialog>
  );
}
