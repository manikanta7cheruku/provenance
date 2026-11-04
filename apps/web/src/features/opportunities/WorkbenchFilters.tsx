import { useEffect, useState } from "react";
import { describeBand, describeEligibility } from "../../lib/states";
import type { Band, EligibilityState } from "../../lib/states";
import {
  activeFilterCount,
  EMPLOYMENT_LABELS,
  SENIORITY_LABELS,
  WORK_MODE_LABELS,
} from "../../lib/workbench-api";
import type { Facets, Query } from "../../lib/workbench-api";
import { ActionButton, Checkbox, TextField } from "../../ui";

type ListKey = "work_mode" | "eligibility" | "band" | "employment_type" | "seniority" | "source";

interface Group {
  key: ListKey;
  legend: string;
  counts: Record<string, number>;
  label: (value: string) => string;
}

function groups(facets: Facets): Group[] {
  return [
    { key: "work_mode", legend: "Where the work happens", counts: facets.work_modes, label: (v) => WORK_MODE_LABELS[v] ?? v },
    {
      key: "eligibility",
      legend: "Can you take it",
      counts: facets.eligibility,
      label: (v) => describeEligibility(v as EligibilityState).label,
    },
    { key: "band", legend: "Fit", counts: facets.bands, label: (v) => describeBand(v as Band).label },
    { key: "seniority", legend: "Level", counts: facets.seniorities, label: (v) => SENIORITY_LABELS[v] ?? v },
    { key: "employment_type", legend: "Kind of work", counts: facets.employment_types, label: (v) => EMPLOYMENT_LABELS[v] ?? v },
    { key: "source", legend: "Where you found it", counts: facets.sources, label: (v) => v },
  ];
}

/** A text filter that waits for a pause in typing before it changes the list. */
function TextFilter({ label, value, onCommit }: { label: string; value: string; onCommit: (value: string) => void }) {
  const [text, setText] = useState(value);
  useEffect(() => setText(value), [value]);
  useEffect(() => {
    if (text === value) return;
    const timer = window.setTimeout(() => onCommit(text), 300);
    return () => window.clearTimeout(timer);
  }, [text, value, onCommit]);
  return <TextField label={label} value={text} onChange={(event) => setText(event.target.value)} />;
}

export function WorkbenchFilters({
  query,
  facets,
  onChange,
  onClear,
}: {
  query: Query;
  facets: Facets;
  onChange: (patch: Partial<Query>) => void;
  onClear: () => void;
}) {
  const count = activeFilterCount(query);
  return (
    <details className="bench__filters" open={count > 0 ? true : undefined}>
      <summary>{count > 0 ? `Filters, ${count} set` : "Filters"}</summary>
      <div className="bench__filtergrid">
        {groups(facets).map((group) => {
          // Show the values in this view, and keep any that are chosen even if nothing matches now.
          const values = Array.from(new Set([...Object.keys(group.counts), ...query[group.key]])).sort();
          if (values.length === 0) return null;
          return (
            <fieldset key={group.key} className="bench__group">
              <legend>{group.legend}</legend>
              {values.map((value) => (
                <Checkbox
                  key={value}
                  label={`${group.label(value)} (${group.counts[value] ?? 0})`}
                  checked={query[group.key].includes(value)}
                  onChange={(event) =>
                    onChange({
                      [group.key]: event.target.checked
                        ? [...query[group.key], value]
                        : query[group.key].filter((v) => v !== value),
                    })
                  }
                />
              ))}
            </fieldset>
          );
        })}
        <div className="bench__group">
          <TextFilter label="Company contains" value={query.company} onCommit={(company) => onChange({ company })} />
          <TextFilter label="Place contains" value={query.location} onCommit={(location) => onChange({ location })} />
        </div>
      </div>
      {count > 0 ? (
        <p>
          <ActionButton onClick={onClear}>Clear filters</ActionButton>
        </p>
      ) : null}
    </details>
  );
}
