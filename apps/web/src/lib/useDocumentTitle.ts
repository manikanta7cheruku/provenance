import { useEffect } from "react";

/** Screen reader users learn about navigation from the document title. */
export function useDocumentTitle(title: string): void {
  useEffect(() => {
    document.title = `${title} \u00b7 Provenance`;
  }, [title]);
}
