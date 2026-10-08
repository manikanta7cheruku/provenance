import { Link } from "react-router-dom";
import { useDocumentTitle } from "../../lib/useDocumentTitle";
import { EmptyState, PageHeader } from "../../ui";

export function NotFoundPage() {
  useDocumentTitle("Page not found");
  return (
    <>
      <PageHeader title="Page not found" />
      <EmptyState
        title="That page does not exist"
        why="The address may be mistyped, or the page may have moved."
        next="Go back to your opportunities."
      >
        <Link to="/opportunities">Open Opportunities</Link>
      </EmptyState>
    </>
  );
}
