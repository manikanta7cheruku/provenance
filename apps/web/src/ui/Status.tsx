export type Tone = "ok" | "warn" | "danger" | "neutral";

interface StatusProps {
  tone: Tone;
  label: string;
}

/** A dot and a label. The dot shape differs by tone and the label carries the meaning. */
export function Status({ tone, label }: StatusProps) {
  return (
    <span className={`status status--${tone}`}>
      <span className="status__dot" aria-hidden="true" />
      <span>{label}</span>
    </span>
  );
}
