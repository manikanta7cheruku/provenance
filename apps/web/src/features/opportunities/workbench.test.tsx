import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  activeFilterCount,
  decisionTone,
  EMPTY_QUERY,
  paramsToQuery,
  queryToParams,
  queryToStored,
  storedToQuery,
} from "../../lib/workbench-api";
import type { Decision, DecisionAction, Query, WorkRow } from "../../lib/workbench-api";
import { DecisionBar } from "./DecisionBar";
import { NoteBox } from "./NoteBox";
import { Workbench } from "./Workbench";

const api = vi.hoisted(() => ({
  fetchWorkbench: vi.fn(),
  decideJob: vi.fn(),
  bulkDecide: vi.fn(),
  saveNote: vi.fn(),
  fetchViews: vi.fn(),
  saveView: vi.fn(),
  deleteView: vi.fn(),
}));
vi.mock("../../lib/workbench-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../lib/workbench-api")>()),
  ...api,
}));

const OFFER: Record<string, DecisionAction[]> = {
  new: ["save", "approve", "mark_applied", "dismiss"],
  saved: ["unsave", "approve", "mark_applied", "dismiss"],
};
const LABEL: Record<string, string> = {
  save: "Save",
  unsave: "Unsave",
  approve: "Approve for preparation",
  mark_applied: "Mark applied",
  dismiss: "Dismiss",
};

function decision(state: "new" | "saved" = "new", note = ""): Decision {
  return {
    state,
    state_label: state === "new" ? "New" : "Saved",
    actions: (OFFER[state] ?? []).map((action) => ({ action, label: LABEL[action] ?? action })),
    note,
    applied_at: null,
    updated_at: null,
  };
}

function row(id: string, title: string, overrides: Partial<WorkRow> = {}): WorkRow {
  return {
    id,
    title,
    company: "Acme",
    source_name: "Wellfound",
    acquisition_method: "user_paste",
    work_mode: "remote",
    location: "Pune, India",
    employment_type: "full_time",
    seniority: "mid",
    eligibility: "eligible",
    band: "good",
    reading: "ready",
    decision: decision(),
    has_note: false,
    created_at: "2026-10-30T09:00:00Z",
    ...overrides,
  };
}

function bench(rows: WorkRow[]) {
  return {
    rows,
    total: rows.length,
    query: {},
    truncated: false,
    facets: {
      views: { active: rows.length, saved: 0, applications: 0, dismissed: 0, archived: 0, all: rows.length },
      work_modes: { remote: rows.length },
      eligibility: { eligible: rows.length },
      bands: { good: rows.length },
      employment_types: {},
      seniorities: {},
      sources: { Wellfound: rows.length },
    },
  };
}

function renderBench(path = "/opportunities") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/opportunities" element={<Workbench version={0} />} />
        <Route path="/opportunities/:jobId" element={<p>Job page</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.resetAllMocks();
  api.fetchViews.mockResolvedValue([]);
});

describe("the query in the address", () => {
  it("round-trips through the address and through a saved view", () => {
    const q: Query = {
      ...EMPTY_QUERY,
      view: "saved",
      q: "data",
      work_mode: ["remote", "hybrid"],
      band: ["strong"],
      company: "acme",
      location: "pune",
      sort: "fit",
      desc: true,
    };
    expect(paramsToQuery(queryToParams(q))).toEqual(q);
    expect(storedToQuery(queryToStored(q))).toEqual(q);
  });

  it("leaves out what is the default, so the address stays short", () => {
    expect(queryToParams(EMPTY_QUERY).toString()).toBe("");
  });

  it("ignores values it does not know", () => {
    const q = paramsToQuery(new URLSearchParams("view=bogus&sort=nope&desc=maybe"));
    expect(q.view).toBe("active");
    expect(q.sort).toBe("added");
    expect(q.desc).toBeNull();
  });

  it("counts the filters that are set, not the view or the sort", () => {
    expect(activeFilterCount(EMPTY_QUERY)).toBe(0);
    expect(activeFilterCount({ ...EMPTY_QUERY, work_mode: ["remote"], band: ["good", "strong"], company: "x", sort: "title" })).toBe(4);
  });

  it("gives each state a tone, with the label carrying the meaning", () => {
    expect(decisionTone("applied")).toBe("ok");
    expect(decisionTone("dismissed")).toBe("warn");
    expect(decisionTone("new")).toBe("neutral");
  });
});

describe("DecisionBar", () => {
  it("offers only what the server offers and names the job on each button", () => {
    render(<DecisionBar job={{ id: "j1", title: "Backend engineer", company: "Acme" }} decision={decision("saved")} onDecided={() => undefined} />);
    expect(screen.getByRole("button", { name: "Unsave: Backend engineer at Acme" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: /^Save:/ })).toBeNull();
  });

  it("sends the action, reports the answer, and shows its own undo on the job page", async () => {
    api.decideJob.mockResolvedValue({ decision: decision("saved"), undo: "unsave", undo_label: "Unsave" });
    const onDecided = vi.fn();
    const user = userEvent.setup();
    render(<DecisionBar ownUndo job={{ id: "j1", title: "Backend engineer", company: "Acme" }} decision={decision()} onDecided={onDecided} />);
    await user.click(screen.getByRole("button", { name: /^Save:/ }));
    await waitFor(() => expect(onDecided).toHaveBeenCalled());
    expect(api.decideJob).toHaveBeenCalledWith("j1", "save", undefined);
    expect(await screen.findByRole("button", { name: "Unsave" })).toBeTruthy();
  });

  it("says why when the server refuses", async () => {
    const { ApiError } = await import("../../lib/api");
    api.decideJob.mockRejectedValue(new ApiError(409, "NOT_ELIGIBLE", "A hard requirement stands in the way.", {}, null));
    const user = userEvent.setup();
    render(<DecisionBar job={{ id: "j1", title: "Backend engineer", company: "Acme" }} decision={decision()} onDecided={() => undefined} />);
    await user.click(screen.getByRole("button", { name: /^Approve for preparation:/ }));
    expect(await screen.findByText("A hard requirement stands in the way.")).toBeTruthy();
  });

  it("asks before marking applied, naming the company and role, and sends the day", async () => {
    api.decideJob.mockResolvedValue({ decision: decision(), undo: "undo_applied", undo_label: "Undo applied" });
    const user = userEvent.setup();
    render(<DecisionBar job={{ id: "j1", title: "Backend engineer", company: "Acme" }} decision={decision()} onDecided={() => undefined} />);
    await user.click(screen.getByRole("button", { name: /^Mark applied:/ }));
    expect(api.decideJob).not.toHaveBeenCalled();
    expect(await screen.findByText(/Backend engineer at Acme on the employer's site/)).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Mark applied" }));
    await waitFor(() => expect(api.decideJob).toHaveBeenCalled());
    expect(api.decideJob.mock.calls[0]?.[1]).toBe("mark_applied");
    expect(api.decideJob.mock.calls[0]?.[2]).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });
});

describe("NoteBox", () => {
  it("saves only when asked and says so", async () => {
    api.saveNote.mockResolvedValue(decision("new", "call Friday"));
    const onSaved = vi.fn();
    const user = userEvent.setup();
    render(<NoteBox jobId="j1" note="" onSaved={onSaved} />);
    const save = screen.getByRole("button", { name: "Save note" }) as HTMLButtonElement;
    expect(save.disabled).toBe(true);
    await user.type(screen.getByLabelText("Your note"), "call Friday");
    await user.click(save);
    await waitFor(() => expect(api.saveNote).toHaveBeenCalledWith("j1", "call Friday"));
    expect(await screen.findByText("Note saved.")).toBeTruthy();
    expect(onSaved).toHaveBeenCalled();
  });

  it("refuses a note over the limit before sending", async () => {
    const user = userEvent.setup();
    render(<NoteBox jobId="j1" note="" onSaved={() => undefined} />);
    await user.click(screen.getByLabelText("Your note"));
    await user.paste("x".repeat(2100));
    expect(await screen.findByText(/up to 2,000 characters/)).toBeTruthy();
    expect((screen.getByRole("button", { name: "Save note" }) as HTMLButtonElement).disabled).toBe(true);
  });
});

describe("Workbench", () => {
  it("shows the views with counts, the rows and the first job in the pane", async () => {
    api.fetchWorkbench.mockResolvedValue(bench([row("a", "Backend engineer"), row("b", "Data analyst")]));
    renderBench();
    expect(await screen.findByRole("link", { name: "Backend engineer" })).toBeTruthy();
    expect(screen.getByRole("button", { name: /^Active/ }).textContent).toContain("2");
    expect(screen.getByRole("button", { name: /^Active/ }).getAttribute("aria-current")).toBe("page");
    expect(screen.getByRole("complementary", { name: "Selected job" })).toBeTruthy();
  });

  it("asks the server for the view and the filters in the address", async () => {
    api.fetchWorkbench.mockResolvedValue(bench([]));
    renderBench("/opportunities?view=saved&work_mode=remote&q=data");
    await waitFor(() => expect(api.fetchWorkbench).toHaveBeenCalled());
    const query = api.fetchWorkbench.mock.calls[0]?.[0] as Query;
    expect(query.view).toBe("saved");
    expect(query.work_mode).toEqual(["remote"]);
    expect(query.q).toBe("data");
  });

  it("explains an empty view and an empty search differently", async () => {
    api.fetchWorkbench.mockResolvedValue(bench([]));
    renderBench();
    expect(await screen.findByRole("heading", { name: "No jobs to look at" })).toBeTruthy();
    renderBench("/opportunities?company=zzz");
    expect(await screen.findByRole("heading", { name: "No jobs match" })).toBeTruthy();
  });

  it("says when the list cannot be loaded and offers a retry", async () => {
    api.fetchWorkbench.mockRejectedValue(new Error("The server is not answering."));
    renderBench();
    expect(await screen.findByText(/could not be loaded/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Try again" })).toBeTruthy();
  });

  it("moves with the keys, saves with S and offers an undo that works", async () => {
    api.fetchWorkbench.mockResolvedValue(bench([row("a", "Backend engineer"), row("b", "Data analyst")]));
    api.decideJob.mockResolvedValue({ decision: decision("saved"), undo: "unsave", undo_label: "Unsave" });
    api.bulkDecide.mockResolvedValue({ results: [{ id: "b", ok: true, state: "new", message: null }], done: 1, skipped: 0, undo: null, undo_label: null });
    const user = userEvent.setup();
    renderBench();
    await screen.findByRole("link", { name: "Data analyst" });
    await user.keyboard("j");
    await user.keyboard("s");
    await waitFor(() => expect(api.decideJob).toHaveBeenCalledWith("b", "save", undefined));
    expect(await screen.findByText("Saved: Data analyst.")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Unsave" }));
    await waitFor(() => expect(api.bulkDecide).toHaveBeenCalledWith(["b"], "unsave"));
    expect(await screen.findByText("Undone.")).toBeTruthy();
  });

  it("does not treat typing in the search box as a shortcut", async () => {
    api.fetchWorkbench.mockResolvedValue(bench([row("a", "Backend engineer")]));
    const user = userEvent.setup();
    renderBench();
    await screen.findByRole("link", { name: "Backend engineer" });
    await user.click(screen.getByLabelText("Search your jobs"));
    await user.keyboard("sdp");
    expect(api.decideJob).not.toHaveBeenCalled();
    expect((screen.getByLabelText("Search your jobs") as HTMLInputElement).value).toBe("sdp");
  });

  it("acts on the checked jobs together, only with actions they all have", async () => {
    api.fetchWorkbench.mockResolvedValue(
      bench([row("a", "Backend engineer"), row("b", "Data analyst", { decision: decision("saved") })]),
    );
    api.bulkDecide.mockResolvedValue({
      results: [
        { id: "a", ok: true, state: "dismissed", message: null },
        { id: "b", ok: true, state: "dismissed", message: null },
      ],
      done: 2,
      skipped: 0,
      undo: "undo_dismiss",
      undo_label: "Undo dismiss",
    });
    const user = userEvent.setup();
    renderBench();
    await user.click(await screen.findByLabelText(/^Select Backend engineer/));
    await user.click(screen.getByLabelText(/^Select Data analyst/));
    const group = screen.getByRole("group", { name: "Actions for the selected jobs" });
    expect(group.textContent).toContain("2 jobs selected");
    expect(screen.queryByRole("button", { name: "Save" })).toBeNull(); // one is saved already
    expect(screen.queryByRole("button", { name: "Mark applied" })).toBeNull(); // asks for a day, so one at a time
    await user.click(screen.getByRole("button", { name: "Dismiss" }));
    await waitFor(() => expect(api.bulkDecide).toHaveBeenCalledWith(["a", "b"], "dismiss"));
    expect(await screen.findByText(/Dismissed: 2 jobs\./)).toBeTruthy();
  });

  it("opens the shortcut list from the button", async () => {
    api.fetchWorkbench.mockResolvedValue(bench([row("a", "Backend engineer")]));
    const user = userEvent.setup();
    renderBench();
    await user.click(await screen.findByRole("button", { name: "Keyboard shortcuts" }));
    expect(await screen.findByText(/Shortcuts work when you are not typing/)).toBeTruthy();
  });
});
