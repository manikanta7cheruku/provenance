import { Link } from "react-router-dom";
import { describeImport, kindLabel } from "../../lib/imports-api";
import type { ImportBatch } from "../../lib/imports-api";
import { formatDateTime } from "../../lib/format";
import { DataTable, Section, Status } from "../../ui";

/** The latest imports, newest first. Each one opens its report. */
export function RecentImports({ batches }: { batches: ImportBatch[] }) {
  if (batches.length === 0) return null;
  return (
    <Section title="Recent imports">
      <DataTable caption={`Recent imports, ${batches.length} shown`}>
        <thead>
          <tr>
            <th scope="col">Import</th>
            <th scope="col">Result</th>
            <th scope="col" className="num">
              Added
            </th>
            <th scope="col" className="num">
              Not added
            </th>
            <th scope="col">Started</th>
          </tr>
        </thead>
        <tbody>
          {batches.map((batch) => {
            const state = describeImport(batch);
            const done = batch.status === "done";
            return (
              <tr key={batch.id}>
                <th scope="row">
                  <Link to={`/opportunities/imports/${batch.id}`} className="jobs__link">
                    {batch.label}
                  </Link>
                  <span className="row-sub">{kindLabel(batch.kind)}</span>
                </th>
                <td>
                  <Status tone={state.tone} label={state.label} />
                </td>
                <td className="num">{done ? batch.created_count : ""}</td>
                <td className="num">{done ? batch.rejected_count : ""}</td>
                <td>{formatDateTime(batch.created_at)}</td>
              </tr>
            );
          })}
        </tbody>
      </DataTable>
    </Section>
  );
}
