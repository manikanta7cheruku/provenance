import { useEffect, useRef } from "react";

/**
 * Sets the document title and moves focus to the page heading when the page changes, so
 * keyboard and screen reader users land at the top of the new content.
 * Attach the returned ref to the page's <h1 tabIndex={-1}>.
 */
export function usePageChrome(title: string) {
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    document.title = `${title} \u00b7 Provenance`;
    heading.current?.focus();
  }, [title]);
  return heading;
}
