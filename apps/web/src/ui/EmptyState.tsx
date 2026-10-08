import { useId } from "react";
import type { ReactNode } from "react";

interface EmptyStateProps {
  title: string;
  /** Why this area matters to the user. */
  why: string;
  /** What the user can do next. */
  next: string;
  children?: ReactNode;
}

/** Every empty state answers: what is empty, why it matters, what to do next. */
export function EmptyState({ title, why, next, children }: EmptyStateProps) {
  const titleId = useId();
  return (
    <section className="empty" aria-labelledby={titleId}>
      <h2 id={titleId} className="empty__title">
        {title}
      </h2>
      <dl className="empty__facts">
        <dt>Why it matters</dt>
        <dd>{why}</dd>
        <dt>What to do next</dt>
        <dd>{next}</dd>
      </dl>
      {children ? <div className="empty__actions">{children}</div> : null}
    </section>
  );
}
