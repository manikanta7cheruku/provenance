import { useEffect, useRef } from "react";
import { Link } from "react-router-dom";
import { daysAgo, formatDateTime } from "../../lib/format";
import { describeBand, describeEligibility, describeJobState } from "../../lib/states";
import type { Band } from "../../lib/states";
import { decisionTone } from "../../lib/workbench-api";
import type { WorkRow } from "../../lib/workbench-api";
import { DataTable, Status } from "../../ui";
import { workLine } from "./labels";

function Fit({ row }: { row: WorkRow }) {
  if (row.band) {
    const info = describeBand(row.band as Band);
    return <Status tone={info.tone} label={info.label} />;
  }
  return <span className="row-sub">Not checked yet</span>;
}

function Eligibility({ row }: { row: WorkRow }) {
  if (row.reading !== "ready" || !row.eligibility) {
    const info = describeJobState(row.reading);
    return <Status tone={info.tone} label={info.label} />;
  }
  const info = describeEligibility(row.eligibility);
  return <Status tone={info.tone} label={info.label} />;
}

interface Props {
  rows: WorkRow[];
  caption: string;
  selectedId: string | null;
  checked: ReadonlySet<string>;
  /** The page says on which date to show for each row: when it was added, or when it was applied. */
  dateOf: (row: WorkRow) => string | null;
  dateLabel: string;
  onSelect: (id: string) => void;
  onCheck: (id: string, on: boolean) => void;
  onCheckAll: (on: boolean) => void;
}

export function WorkbenchTable({ rows, caption, selectedId, checked, dateOf, dateLabel, onSelect, onCheck, onCheckAll }: Props) {
  const selectedRef = useRef<HTMLTableRowElement | null>(null);
  // Keep the selected row in view when the keys move the selection.
  useEffect(() => {
    selectedRef.current?.scrollIntoView?.({ block: "nearest" });
  }, [selectedId]);
  const allChecked = rows.length > 0 && rows.every((r) => checked.has(r.id));
  return (
    <DataTable caption={caption}>
      <thead>
        <tr>
          <th scope="col" className="bench__check">
            <input
              type="checkbox"
              aria-label="Select every job shown"
              checked={allChecked}
              onChange={(event) => onCheckAll(event.target.checked)}
            />
          </th>
          <th scope="col">Job</th>
          <th scope="col">Fit</th>
          <th scope="col">Can you take it</th>
          <th scope="col">Work</th>
          <th scope="col">State</th>
          <th scope="col">{dateLabel}</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => {
          const isSelected = row.id === selectedId;
          const date = dateOf(row);
          return (
            <tr
              key={row.id}
              ref={isSelected ? selectedRef : undefined}
              className="bench__row"
              data-selected={isSelected || undefined}
              aria-current={isSelected ? "true" : undefined}
              onClick={(event) => {
                if ((event.target as HTMLElement).closest("a,input,button,label")) return;
                onSelect(row.id);
              }}
            >
              <td className="bench__check">
                <input
                  type="checkbox"
                  aria-label={`Select ${row.title ?? "untitled posting"}${row.company ? ` at ${row.company}` : ""}`}
                  checked={checked.has(row.id)}
                  onChange={(event) => onCheck(row.id, event.target.checked)}
                />
              </td>
              <th scope="row">
                <Link to={`/opportunities/${row.id}`} className="jobs__link" onFocus={() => onSelect(row.id)}>
                  {row.title ?? "Untitled posting"}
                </Link>
                <span className="row-sub">{row.company ?? "Company not stated"}</span>
                {row.has_note ? <span className="row-sub">Has a note</span> : null}
              </th>
              <td>
                <Fit row={row} />
              </td>
              <td>
                <Eligibility row={row} />
              </td>
              <td>{workLine({ work_mode: row.work_mode, location: row.location })}</td>
              <td>
                <Status tone={decisionTone(row.decision.state)} label={row.decision.state_label} />
              </td>
              <td>
                {date ? formatDateTime(date) : ""}
                {row.decision.state === "applied" && date ? <span className="row-sub">{daysAgo(date)}</span> : null}
              </td>
            </tr>
          );
        })}
      </tbody>
    </DataTable>
  );
}
