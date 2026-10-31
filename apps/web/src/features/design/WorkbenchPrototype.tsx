import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useDocumentTitle } from "../../lib/useDocumentTitle";
import {
  ActionButton,
  DataTable,
  Dialog,
  EmptyState,
  Notice,
  PageHeader,
  SegmentedControl,
  Select,
  Skeleton,
  Status,
  TextField,
} from "../../ui";
import { BAND_TONE, SAMPLE_JOBS } from "./fixtures";
import type { Band, SampleJob, WorkMode } from "./fixtures";

type SampleState = "populated" | "loading" | "empty" | "error";
type ModeFilter = "all" | WorkMode;

const STATE_OPTIONS = [
  { value: "populated", label: "Populated" },
  { value: "loading", label: "Loading" },
  { value: "empty", label: "Empty" },
  { value: "error", label: "Error" },
] as const;

const MODE_OPTIONS = [
  { value: "all", label: "All" },
  { value: "Remote", label: "Remote" },
  { value: "Hybrid", label: "Hybrid" },
  { value: "On-site", label: "On-site" },
] as const;

const BANDS: Band[] = ["Strong match", "Good match", "Review", "Not recommended", "Not eligible"];

interface Message {
  text: string;
  undo?: () => void;
}

function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName);
}

/**
 * Prototype of the opportunities workbench with sample data. It shows the density, the filters,
 * the selection model, the keyboard flow and the state set before the real screen is built (2.9).
 */
export function WorkbenchPrototype() {
  useDocumentTitle("Workbench prototype");
  const [sample, setSample] = useState<SampleState>("populated");
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState<ModeFilter>("all");
  const [band, setBand] = useState<"all" | Band>("all");
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());
  const [saved, setSaved] = useState<Set<string>>(new Set());
  const [selectedId, setSelectedId] = useState<string>("j1");
  const [message, setMessage] = useState<Message | null>(null);
  const [helpOpen, setHelpOpen] = useState(false);
  const search = useRef<HTMLInputElement>(null);

  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return SAMPLE_JOBS.filter(
      (job) =>
        !dismissed.has(job.id) &&
        (mode === "all" || job.workMode === mode) &&
        (band === "all" || job.band === band) &&
        (needle === "" || `${job.title} ${job.company}`.toLowerCase().includes(needle)),
    );
  }, [query, mode, band, dismissed]);

  const selected: SampleJob | undefined = visible.find((job) => job.id === selectedId) ?? visible[0];

  function toggleSaved(job: SampleJob) {
    const wasSaved = saved.has(job.id);
    const next = new Set(saved);
    if (wasSaved) next.delete(job.id);
    else next.add(job.id);
    setSaved(next);
    setMessage({
      text: wasSaved ? `Removed ${job.title} from Saved.` : `Saved ${job.title} at ${job.company}.`,
      undo: () => setSaved(saved),
    });
  }

  function dismiss(job: SampleJob) {
    const before = dismissed;
    setDismissed(new Set(before).add(job.id));
    setMessage({
      text: `Dismissed ${job.title} at ${job.company}.`,
      undo: () => setDismissed(before),
    });
  }

  // Keyboard flow from the design system: J and K move, S saves, D dismisses, / searches, ? helps.
  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.ctrlKey || event.metaKey || event.altKey || isTypingTarget(event.target)) return;
      const index = selected ? visible.findIndex((job) => job.id === selected.id) : -1;
      if (event.key === "j") {
        const next = visible[Math.min(index + 1, visible.length - 1)];
        if (next) setSelectedId(next.id);
      } else if (event.key === "k") {
        const next = visible[Math.max(index - 1, 0)];
        if (next) setSelectedId(next.id);
      } else if (event.key === "s" && selected) toggleSaved(selected);
      else if (event.key === "d" && selected) dismiss(selected);
      else if (event.key === "/") {
        event.preventDefault();
        search.current?.focus();
      } else if (event.key === "?") setHelpOpen(true);
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  });

  return (
    <>
      <PageHeader
        title="Opportunities"
        description="Prototype with sample data. Your ranked work queue, with the reason behind every ranking."
      />

      <div className="proto-bar">
        <SegmentedControl
          legend="Sample state to preview"
          showLegend
          options={STATE_OPTIONS}
          value={sample}
          onChange={setSample}
        />
        <ActionButton onClick={() => setHelpOpen(true)}>Keyboard shortcuts</ActionButton>
      </div>

      <div className="workbench-filters" role="search" aria-label="Filter opportunities">
        <TextField
          ref={search}
          label="Search role or company"
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          hint="Press / to jump here."
        />
        <SegmentedControl legend="Work mode" showLegend options={MODE_OPTIONS} value={mode} onChange={setMode} />
        <Select label="Fit" value={band} onChange={(event) => setBand(event.target.value as "all" | Band)}>
          <option value="all">All fits</option>
          {BANDS.map((name) => (
            <option key={name} value={name}>
              {name}
            </option>
          ))}
        </Select>
      </div>

      <div className="proto-live" role="status" aria-live="polite">
        {message ? (
          <p>
            {message.text}{" "}
            {message.undo ? (
              <ActionButton
                onClick={() => {
                  message.undo?.();
                  setMessage(null);
                }}
              >
                Undo
              </ActionButton>
            ) : null}
          </p>
        ) : null}
      </div>

      {sample === "loading" ? (
        <Skeleton label="Loading your opportunities" lines={6} />
      ) : sample === "error" ? (
        <Notice tone="danger" title="Opportunities could not be loaded">
          <p>Your data is safe. We could not reach the server, and nothing was changed.</p>
          <p>
            <ActionButton onClick={() => setSample("populated")}>Try again</ActionButton>
          </p>
        </Notice>
      ) : sample === "empty" || visible.length === 0 ? (
        <EmptyState
          title={sample === "empty" ? "No opportunities yet" : "No jobs match these filters"}
          why={
            sample === "empty"
              ? "This is where the jobs worth your time appear, each with the reason it was ranked."
              : "Filters narrow the list. Nothing was removed."
          }
          next={
            sample === "empty"
              ? "Paste a job description to analyze your first job."
              : "Clear the filters or widen the search."
          }
        >
          {sample === "empty" ? null : (
            <ActionButton
              onClick={() => {
                setQuery("");
                setMode("all");
                setBand("all");
              }}
            >
              Clear filters
            </ActionButton>
          )}
        </EmptyState>
      ) : (
        <div className="workbench" data-density="compact">
          <div>
            <DataTable caption={`Opportunities, ${visible.length} shown`}>
              <thead>
                <tr>
                  <th scope="col">Role</th>
                  <th scope="col">Fit</th>
                  <th scope="col" className="num">
                    Met
                  </th>
                  <th scope="col">Work</th>
                  <th scope="col">Source</th>
                </tr>
              </thead>
              <tbody>
                {visible.map((job) => (
                  <tr key={job.id} aria-current={selected?.id === job.id ? "true" : undefined}>
                    <th scope="row">
                      <button type="button" className="row-button" onClick={() => setSelectedId(job.id)}>
                        {job.title}
                      </button>
                      <span className="row-sub">
                        {job.company}
                        {" · " + job.updated}
                        {saved.has(job.id) ? " · Saved" : ""}
                      </span>
                    </th>
                    <td>
                      <Status tone={BAND_TONE[job.band]} label={job.band} />
                    </td>
                    <td className="num">
                      {job.met}/{job.required}
                    </td>
                    <td>
                      {job.workMode}
                      <span className="row-sub">{job.place}</span>
                    </td>
                    <td>
                      {job.source}
                      <span className="row-sub">{job.acquisition}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </DataTable>
          </div>

          {selected ? (
            <aside className="workbench__pane" aria-label="Selected job">
              <h2 className="pane__title">{selected.title}</h2>
              <p className="pane__sub">
                {selected.company}
                {" · "}
                {selected.place}
              </p>
              <p className="pane__fit">
                <Status tone={BAND_TONE[selected.band]} label={selected.band} />
              </p>
              <p>{selected.reason}</p>
              <h3 className="pane__heading">Eligibility checks</h3>
              <ul className="pane__gates">
                {selected.gates.map((gate) => (
                  <li key={gate.name}>
                    <Status
                      tone={gate.result === "Passed" ? "ok" : gate.result === "Blocked" ? "danger" : "warn"}
                      label={`${gate.name}: ${gate.result}`}
                    />
                  </li>
                ))}
              </ul>
              <p className="pane__source">
                Source: {selected.source}. {selected.acquisition}.
              </p>
              <div className="pane__actions">
                <Link className="action action--primary" to="/design/job">
                  Open full analysis
                </Link>
                <ActionButton onClick={() => toggleSaved(selected)}>
                  {saved.has(selected.id) ? "Unsave" : "Save"}
                </ActionButton>
                <ActionButton onClick={() => dismiss(selected)}>Dismiss</ActionButton>
              </div>
            </aside>
          ) : null}
        </div>
      )}

      <Dialog
        open={helpOpen}
        title="Keyboard shortcuts"
        onClose={() => setHelpOpen(false)}
        actions={
          <ActionButton variant="primary" onClick={() => setHelpOpen(false)} autoFocus>
            Close
          </ActionButton>
        }
      >
        <dl className="shortcuts">
          <dt>J and K</dt>
          <dd>Move down and up the list</dd>
          <dt>S</dt>
          <dd>Save or unsave the selected job</dd>
          <dt>D</dt>
          <dd>Dismiss the selected job (you can undo)</dd>
          <dt>/</dt>
          <dd>Jump to search</dd>
          <dt>?</dt>
          <dd>Show this list</dd>
          <dt>Escape</dt>
          <dd>Close this dialog</dd>
        </dl>
        <p>Shortcuts are off while you type in a field. Every action also has a visible button.</p>
      </Dialog>
    </>
  );
}
