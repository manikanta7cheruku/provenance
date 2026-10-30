import "./controls.css";

interface SkeletonProps {
  /** Names what is loading. Announced politely; the shapes themselves are hidden from assistive technology. */
  label: string;
  /** Number of text lines to draw. */
  lines?: number;
}

/** A placeholder for content on its way. Never an unlabeled spinner: the label says what is loading. */
export function Skeleton({ label, lines = 3 }: SkeletonProps) {
  return (
    <div className="skeleton" role="status">
      <span className="visually-hidden">{label}</span>
      <div aria-hidden="true">
        {Array.from({ length: lines }, (_, index) => (
          <span key={index} className="skeleton__line" data-last={index === lines - 1 && lines > 1} />
        ))}
      </div>
    </div>
  );
}
