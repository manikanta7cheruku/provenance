import { useEffect, useRef } from "react";

// On single-page navigation the browser does not announce the new page, so we
// move focus to the heading. The very first load is skipped to avoid stealing focus.
let isFirstRender = true;

interface PageHeaderProps {
  title: string;
  description?: string;
}

export function PageHeader({ title, description }: PageHeaderProps) {
  const headingRef = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    if (isFirstRender) {
      isFirstRender = false;
      return;
    }
    headingRef.current?.focus();
  }, [title]);

  return (
    <header className="page-header">
      <h1 ref={headingRef} tabIndex={-1} className="page-header__title">
        {title}
      </h1>
      {description ? <p className="page-header__description">{description}</p> : null}
    </header>
  );
}
