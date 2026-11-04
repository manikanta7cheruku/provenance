import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { ApiError } from "../../lib/api";
import { useAsync } from "../../lib/useAsync";
import {
  activeFilterCount,
  bulkDecide,
  decideJob,
  fetchWorkbench,
  paramsToQuery,
  queryToParams,
  SORT_LABELS,
  SORTS,
  VIEW_LABELS,
  VIEWS,
} from "../../lib/workbench-api";
import type { DecisionAction, DecisionResult, Query, WorkRow } from "../../lib/workbench-api";
import { ActionButton, EmptyState, Notice, Select, Skeleton, TextField } from "../../ui";
import { ApplyDialog } from "./ApplyDialog";
import { jobLabel } from "./DecisionBar";
import { JobPane } from "./JobPane";
import { SavedViews } from "./SavedViews";
import { ShortcutsDialog } from "./ShortcutsDialog";
import { UndoToast } from "./UndoToast";
import type { ToastState } from "./UndoToast";
import { WorkbenchFilters } from "./WorkbenchFilters";
import { WorkbenchTable } from "./WorkbenchTable";

const REFRESH_MS = 2000;
const WIDE = "(min-width: 1100px)";

const DONE_WORDS: Record<DecisionAction, string> = {
  save: "Saved",
  unsave: "Removed from Saved",
  dismiss: "Dismissed",
  undo_dismiss: "Brought back",
  approve: "Approved for preparation",
  mark_applied: "Marked as applied",
  undo_applied: "Applied record removed",
  archive: "Archived",
};

const EMPTY: Record<string, { title: string; why: string; next: string }> = {
  active: {
    title: "No jobs to look at",
    why: "Jobs you add are read for what they ask for and checked against your answers, so you can skip the ones that are not for you.",
    next: "Add a job above: paste it, type it in, give a link or bring a spreadsheet. Or find jobs on the Find jobs page.",
  },
  saved: {
    title: "Nothing saved",
    why: "Saving keeps the jobs you want to come back to in one place.",
    next: "Save a job from your Active list with the Save button or the S key.",
  },
  applications: {
    title: "No applications recorded",
    why: "Marking a job as applied keeps a record of where you applied and when. Provenance never applies for you.",
    next: "When you apply on an employer's site, open the job here and choose Mark applied.",
  },
  dismissed: {
    title: "Nothing dismissed",
    why: "Dismissing hides a job you do not want without deleting it, and you can bring it back.",
    next: "Dismiss a job from your Active list with the Dismiss button or the D key.",
  },
  archived: {
    title: "Nothing archived",
    why: "Archiving tidies away applied or dismissed jobs you are finished with.",
    next: "Archive an applied or dismissed job when you no longer need to see it.",
  },
  all: {
    title: "No jobs yet",
    why: "Every job you add appears here, whatever you decided about it.",
    next: "Add a job above.",
  },
};

function useWide(): boolean {
  const [wide, setWide] = useState(() => (typeof window.matchMedia === "function" ? window.matchMedia(WIDE).matches : true));
  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const list = window.matchMedia(WIDE);
    const onChange = () => setWide(list.matches);
    list.addEventListener("change", onChange);
    return () => list.removeEventListener("change", onChange);
  }, []);
  return wide;
}

function inField(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName);
}

/** The person's list of jobs: views, search, filters, sorting, bulk moves, a detail pane and keys. */
export function Workbench({ version }: { version: number }) {
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const wide = useWide();
  const paramText = params.toString();
  const query = useMemo(() => paramsToQuery(new URLSearchParams(paramText)), [paramText]);
  const data = useAsync((signal) => fetchWorkbench(query, signal), [paramText, version]);
  const rows = useMemo(() => data.data?.rows ?? [], [data.data]);

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [checked, setChecked] = useState<ReadonlySet<string>>(new Set());
  const [toast, setToast] = useState<ToastState | null>(null);
  const [undoJob, setUndoJob] = useState<{ ids: string[]; action: DecisionAction } | null>(null);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const [applyFor, setApplyFor] = useState<WorkRow | null>(null);
  const [help, setHelp] = useState(false);
  const [announce, setAnnounce] = useState("");
  const toastId = useRef(0);
  const searchRef = useRef<HTMLInputElement>(null);
  const [searchText, setSearchText] = useState(query.q);

  const { reload } = data;
  const reading = rows.some((r) => r.reading === "reading");
  useEffect(() => {
    if (!reading) return;
    const timer = window.setInterval(reload, REFRESH_MS);
    return () => window.clearInterval(timer);
  }, [reading, reload]);

  // Keep what is selected valid as the list changes: the same job if it is still there, otherwise
  // the job that took its place.
  const lastIndex = useRef(0);
  useEffect(() => {
    if (rows.length === 0) {
      setSelectedId(null);
      return;
    }
    const at = rows.findIndex((r) => r.id === selectedId);
    if (at >= 0) {
      lastIndex.current = at;
      return;
    }
    const next = rows[Math.min(lastIndex.current, rows.length - 1)];
    setSelectedId(next ? next.id : null);
  }, [rows, selectedId]);

  // Checks that no longer point at a shown job are dropped.
  useEffect(() => {
    setChecked((current) => {
      const shown = new Set(rows.map((r) => r.id));
      const kept = [...current].filter((id) => shown.has(id));
      return kept.length === current.size ? current : new Set(kept);
    });
  }, [rows]);

  useEffect(() => setSearchText(query.q), [query.q]);
  useEffect(() => {
    if (searchText === query.q) return;
    const timer = window.setTimeout(() => update({ q: searchText }), 300);
    return () => window.clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchText, query.q]);

  const selected = rows.find((r) => r.id === selectedId) ?? null;

  function update(patch: Partial<Query>, push = false) {
    setParams(queryToParams({ ...query, ...patch }), { replace: !push });
  }

  function say(message: string, undo: { ids: string[]; action: DecisionAction; label: string } | null) {
    toastId.current += 1;
    setToast({ id: toastId.current, message, undoLabel: undo ? undo.label : null });
    setUndoJob(undo ? { ids: undo.ids, action: undo.action } : null);
  }

  const afterDecision = useCallback(
    (row: WorkRow, action: DecisionAction, result: DecisionResult) => {
      say(`${DONE_WORDS[action]}: ${row.title ?? "this job"}.`, result.undo && result.undo_label ? { ids: [row.id], action: result.undo, label: result.undo_label } : null);
      reload();
    },
    [reload],
  );

  async function act(row: WorkRow, action: DecisionAction, day?: string) {
    setBusy(true);
    setProblem(null);
    try {
      const result = await decideJob(row.id, action, day);
      setApplyFor(null);
      afterDecision(row, action, result);
    } catch (caught) {
      setApplyFor(null);
      setProblem(caught instanceof ApiError ? caught.message : "Something unexpected happened. Nothing was changed.");
    } finally {
      setBusy(false);
    }
  }

  async function bulk(action: DecisionAction) {
    const ids = [...checked];
    setBusy(true);
    setProblem(null);
    try {
      const result = await bulkDecide(ids, action);
      const doneIds = result.results.filter((r) => r.ok).map((r) => r.id);
      const skipped = result.skipped > 0 ? ` ${result.skipped} could not be changed.` : "";
      say(
        `${DONE_WORDS[action]}: ${result.done} ${result.done === 1 ? "job" : "jobs"}.${skipped}`,
        result.undo && result.undo_label && doneIds.length > 0 ? { ids: doneIds, action: result.undo, label: result.undo_label } : null,
      );
      setChecked(new Set());
      reload();
    } catch (caught) {
      setProblem(caught instanceof ApiError ? caught.message : "Something unexpected happened. Nothing was changed.");
    } finally {
      setBusy(false);
    }
  }

  async function undo() {
    if (!undoJob) return;
    setBusy(true);
    try {
      const result = await bulkDecide(undoJob.ids, undoJob.action);
      say(result.done > 0 ? "Undone." : "That could not be undone. The job has changed since.", null);
      reload();
    } catch (caught) {
      setProblem(caught instanceof ApiError ? caught.message : "The undo did not work. Nothing was changed.");
    } finally {
      setBusy(false);
    }
  }

  const move = useCallback(
    (delta: number) => {
      if (rows.length === 0) return;
      const at = rows.findIndex((r) => r.id === selectedId);
      const next = rows[Math.max(0, Math.min(rows.length - 1, (at < 0 ? -1 : at) + delta))];
      if (!next) return;
      setSelectedId(next.id);
      const label = `${next.title ?? "Untitled posting"}${next.company ? `, ${next.company}` : ""}. ${next.decision.state_label}.`;
      setAnnounce(`Current job: ${label}`);
    },
    [rows, selectedId],
  );

  // The shortcuts. They stay off while a person types, while a window is open, and with modifier keys.
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.metaKey || event.ctrlKey || event.altKey) return;
      if (inField(event.target) || document.querySelector("dialog[open]")) return;
      const onControl = event.target instanceof HTMLElement && event.target.closest("a,button,summary") !== null;
      const key = event.key;
      if (key === "/") {
        event.preventDefault();
        searchRef.current?.focus();
      } else if (key === "?") {
        event.preventDefault();
        setHelp(true);
      } else if (key === "Escape") {
        setChecked(new Set());
      } else if (key === "j" || (key === "ArrowDown" && !onControl)) {
        event.preventDefault();
        move(1);
      } else if (key === "k" || (key === "ArrowUp" && !onControl)) {
        event.preventDefault();
        move(-1);
      } else if (selected) {
        const offered = new Set(selected.decision.actions.map((a) => a.action));
        const pick = (...names: DecisionAction[]) => names.find((n) => offered.has(n));
        if (key === "Enter" && !onControl) navigate(`/opportunities/${selected.id}`);
        else if (key === "s" && pick("save", "unsave")) void act(selected, pick("save", "unsave") as DecisionAction);
        else if (key === "d" && pick("dismiss", "undo_dismiss")) void act(selected, pick("dismiss", "undo_dismiss") as DecisionAction);
        else if (key === "p" && pick("approve")) void act(selected, "approve");
        else if (key === "a" && pick("mark_applied")) setApplyFor(selected);
        else if (key === "x") toggleCheck(selected.id, !checked.has(selected.id));
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  function toggleCheck(id: string, on: boolean) {
    setChecked((current) => {
      const next = new Set(current);
      if (on) next.add(id);
      else next.delete(id);
      return next;
    });
  }

  // The actions every checked job offers. Mark applied is one job at a time, because it asks for a day.
  const bulkActions = useMemo(() => {
    const picked = rows.filter((r) => checked.has(r.id));
    if (picked.length === 0) return [];
    const [first, ...rest] = picked;
    if (!first) return [];
    return first.decision.actions.filter(
      (a) => a.action !== "mark_applied" && rest.every((r) => r.decision.actions.some((b) => b.action === a.action)),
    );
  }, [rows, checked]);

  const counts = data.data?.facets.views ?? {};
  const filters = activeFilterCount(query) + (query.q ? 1 : 0);
  const dateOf = (row: WorkRow) => (query.view === "applications" ? row.decision.applied_at : row.created_at);

  return (
    <div className="bench">
      <nav aria-label="Views" className="bench__views-nav">
        <ul className="bench__tabs">
          {VIEWS.map((view) => (
            <li key={view}>
              <button
                type="button"
                className="bench__tab"
                aria-current={query.view === view ? "page" : undefined}
                onClick={() => update({ view }, true)}
              >
                {VIEW_LABELS[view]}
                <span className="bench__count"> {counts[view] ?? 0}</span>
              </button>
            </li>
          ))}
        </ul>
      </nav>

      <div className="bench__toolbar">
        <TextField
          ref={searchRef}
          label="Search your jobs"
          hint="Press / to jump here. Searches title, company, place, source and your notes."
          type="search"
          value={searchText}
          onChange={(event) => setSearchText(event.target.value)}
        />
        <Select label="Sort by" value={query.sort} onChange={(event) => update({ sort: event.target.value as Query["sort"], desc: null })}>
          {SORTS.map((sort) => (
            <option key={sort} value={sort}>
              {SORT_LABELS[sort]}
            </option>
          ))}
        </Select>
        <ActionButton
          onClick={() => {
            const natural = query.sort === "added" || query.sort === "applied";
            const current = query.desc ?? natural;
            update({ desc: !current });
          }}
          aria-label={`Reverse order, now sorted ${(query.desc ?? (query.sort === "added" || query.sort === "applied")) ? "highest or newest first" : "lowest or oldest first"}`}
        >
          Reverse order
        </ActionButton>
        <ActionButton onClick={() => setHelp(true)}>Keyboard shortcuts</ActionButton>
      </div>

      {data.data ? (
        <WorkbenchFilters
          query={query}
          facets={data.data.facets}
          onChange={(patch) => update(patch)}
          onClear={() => update({ work_mode: [], eligibility: [], band: [], employment_type: [], seniority: [], source: [], company: "", location: "", q: "" })}
        />
      ) : null}
      <SavedViews query={query} onApply={(next) => setParams(queryToParams(next))} />

      <UndoToast toast={toast} busy={busy} onUndo={() => void undo()} onClose={() => setToast(null)} />
      <p className="visually-hidden" role="status" aria-live="polite">
        {announce}
      </p>
      {problem ? (
        <Notice tone="warn" title="That did not work">
          <p>{problem}</p>
        </Notice>
      ) : null}

      {checked.size > 0 ? (
        <div className="bench__bulk" role="group" aria-label="Actions for the selected jobs">
          <span>
            {checked.size} {checked.size === 1 ? "job" : "jobs"} selected
          </span>
          {bulkActions.map((entry) => (
            <ActionButton key={entry.action} disabled={busy} onClick={() => void bulk(entry.action)}>
              {entry.label}
            </ActionButton>
          ))}
          <ActionButton onClick={() => setChecked(new Set())}>Clear selection</ActionButton>
        </div>
      ) : null}

      {data.error ? (
        <Notice tone="danger" title="Your jobs could not be loaded">
          <p>{data.error.message} Nothing was changed.</p>
          <p>
            <ActionButton onClick={reload}>Try again</ActionButton>
          </p>
        </Notice>
      ) : !data.data ? (
        <Skeleton label="Loading your jobs" lines={4} />
      ) : rows.length === 0 ? (
        filters > 0 ? (
          <EmptyState
            title="No jobs match"
            why="Your filters or search leave nothing in this view."
            next="Clear the filters, or try fewer words."
          >
            <ActionButton
              onClick={() => update({ work_mode: [], eligibility: [], band: [], employment_type: [], seniority: [], source: [], company: "", location: "", q: "" })}
            >
              Clear filters
            </ActionButton>
          </EmptyState>
        ) : (
          <EmptyState {...(EMPTY[query.view] ?? EMPTY.all!)} />
        )
      ) : (
        <div className="bench__split" data-pane={wide && selected ? "on" : "off"}>
          <div className="bench__list">
            <WorkbenchTable
              rows={rows}
              caption={`${VIEW_LABELS[query.view]} jobs, ${data.data.total} shown`}
              selectedId={selectedId}
              checked={checked}
              dateOf={dateOf}
              dateLabel={query.view === "applications" ? "Applied" : "Added"}
              onSelect={setSelectedId}
              onCheck={toggleCheck}
              onCheckAll={(on) => setChecked(on ? new Set(rows.map((r) => r.id)) : new Set())}
            />
            {data.data.truncated ? (
              <p className="job__note">Only the newest 500 jobs are shown. Use the filters or archive older jobs.</p>
            ) : null}
          </div>
          {wide && selected ? <JobPane row={selected} onDecided={afterDecision} onNoteSaved={() => reload()} /> : null}
        </div>
      )}

      <ApplyDialog
        open={applyFor !== null}
        label={applyFor ? jobLabel(applyFor) : ""}
        busy={busy}
        onCancel={() => setApplyFor(null)}
        onConfirm={(day) => applyFor && void act(applyFor, "mark_applied", day)}
      />
      <ShortcutsDialog open={help} onClose={() => setHelp(false)} />
    </div>
  );
}
