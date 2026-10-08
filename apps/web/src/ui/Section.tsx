import { useId } from "react";
import type { ReactNode } from "react";

interface SectionProps {
  title: string;
  children: ReactNode;
}

export function Section({ title, children }: SectionProps) {
  const headingId = useId();
  return (
    <section className="section" aria-labelledby={headingId}>
      <h2 id={headingId} className="section__title">
        {title}
      </h2>
      {children}
    </section>
  );
}
