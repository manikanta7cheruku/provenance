import type { ReactNode } from "react";
import "./data.css";

interface DataTableProps {
  /** Visible title that also names the table for screen readers. */
  caption: string;
  children: ReactNode;
}

/** A semantic table in a scroll container: wide tables scroll inside it, never the page. */
export function DataTable({ caption, children }: DataTableProps) {
  return (
    <div className="data-table__scroll" tabIndex={0} role="region" aria-label={caption}>
      <table className="data-table">
        <caption className="data-table__caption">{caption}</caption>
        {children}
      </table>
    </div>
  );
}
