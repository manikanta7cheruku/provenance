import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { JobDetail } from "../../lib/jobs-api";
import { describeEligibility, describeJobState, isJobBusy } from "../../lib/states";
import { JobDetailPage } from "./JobDetailPage";
import { acquisitionLabel, factText, workLine } from "./labels";
import { PasteJobForm } from "./PasteJobForm";

const api = vi.hoisted(() => ({
  pasteJob: vi.fn(),
  fetchJob: vi.fn(),
  reanalyzeJob: vi.fn(),
  deleteJob: vi.fn(),
}));
vi.mock("../../lib/jobs-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../lib/jobs-api")>()),
  ...api,
}));

function job(overrides: Partial<JobDetail> = {}): JobDetail {
  return {
    id: "j1",
    title: "Data Analyst",
    company: "Fernlight Systems",
    source_name: "Wellfound",
    acquisition_method: "user_paste",
    ui_state: "ready",
    can_retry: true,
    error_message: null,
    eligibility: "requires_user_input",
    work_mode: "hybrid",
    location: "Bengaluru, India",
    requirement_count: 1,
    created_at: "2026-10-30T09:00:00Z",
    source_url: null,
    visibility: "private",
    facts: { work_mode: { value: "hybrid", quote: "Bengaluru, India (Hybrid)" } },
    requirements: [
      {
        id: "q1",
        ordinal: 0,
        text: "Write SQL",
        kind: "required",
        category: "skill",
        years_min: null,
        quote: "You will write SQL",
        quote_start: 0,
        quote_end: 18,
      },
    ],
    eligibility_detail: {
      state: "requires_user_input",
      rules_version: "eligibility-1",
      gates: [
        {
          gate: "authorization",
          label: "Work authorization and sponsorship",
          state: "requires_user_input",
          reason: "Add the countries where you can work.",
          posting_quote: "Must be authorized to work in India.",
        },
      ],
    },
    facts_dropped: 0,
    requirements_dropped: 0,
    prompt_version: "job-extract-1",
    run_id: "run1",
    extracted_at: "2026-10-30T09:00:00Z",
    text: "You will write SQL",
    ...overrides,
  } as JobDetail;
}

function renderDetail() {
  return render(
    <MemoryRouter initialEntries={["/opportunities/j1"]}>
      <Routes>
        <Route path="/opportunities/:jobId" element={<JobDetailPage />} />
        <Route path="/opportunities" element={<p>Your jobs list</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.resetAllMocks();
});

describe("labels", () => {
  it("says how the text arrived without the word searched", () => {
    expect(acquisitionLabel("user_paste")).toBe("Pasted by you");
  });
  it("builds the work line from what is known", () => {
    expect(workLine({ work_mode: "onsite", location: "Pune" })).toBe("On-site · Pune");
    expect(workLine({ work_mode: null, location: null })).toBe("");
  });
  it("words each fact for a person", () => {
    expect(factText("min_years_experience", { value: 1, quote: "q" })).toBe("1 year");
    expect(factText("min_years_experience", { value: 3, quote: "q" })).toBe("3 years");
    expect(factText("sponsorship", { value: "not_offered", quote: "q" })).toBe("Does not sponsor visas");
    expect(factText("work_authorization_countries", { value: ["India", "UK"], quote: "q" })).toBe("India, UK");
  });
});

describe("state vocabularies", () => {
  it("treats only reading as busy", () => {
    expect(isJobBusy("reading")).toBe(true);
    expect(isJobBusy("ready")).toBe(false);
    expect(isJobBusy("failed")).toBe(false);
  });
  it("gives every job and eligibility state a plain label", () => {
    for (const state of ["reading", "ready", "failed"] as const) {
      expect(describeJobState(state).label.length).toBeGreaterThan(0);
    }
    for (const state of ["eligible", "uncertain", "requires_user_input", "not_eligible"] as const) {
      expect(describeEligibility(state).label.length).toBeGreaterThan(0);
    }
  });
});

describe("PasteJobForm", () => {
  it("refuses a posting that is too short and focuses nothing it did not check", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <PasteJobForm onPasted={() => undefined} />
      </MemoryRouter>,
    );
    await user.type(screen.getByLabelText(/Job description/), "too short");
    await user.click(screen.getByRole("button", { name: "Read this job" }));
    expect(await screen.findByText(/looks too short to be a job posting/)).toBeTruthy();
    expect(api.pasteJob).not.toHaveBeenCalled();
  });

  it("sends the label, the optional link and the text", async () => {
    api.pasteJob.mockResolvedValue({ job: job(), duplicate: false });
    const onPasted = vi.fn();
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <PasteJobForm onPasted={onPasted} />
      </MemoryRouter>,
    );
    const text = "Data Analyst. ".repeat(12);
    await user.click(screen.getByLabelText(/Job description/));
    await user.paste(text);
    await user.click(screen.getByRole("button", { name: "Read this job" }));
    await waitFor(() => expect(api.pasteJob).toHaveBeenCalledTimes(1));
    expect(api.pasteJob).toHaveBeenCalledWith({ source_name: "LinkedIn", source_url: null, text });
    expect(onPasted).toHaveBeenCalled();
  });
});

describe("JobDetailPage", () => {
  it("shows each gate with the posting's own words and a way to answer it", async () => {
    api.fetchJob.mockResolvedValue(job());
    renderDetail();
    expect(await screen.findByText("Can you take this job?")).toBeTruthy();
    expect(screen.getByText("Must be authorized to work in India.")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Answer this in your profile" }).getAttribute("href")).toBe("/profile");
    expect(screen.getByText("You will write SQL", { selector: "blockquote" })).toBeTruthy();
  });

  it("says how many suggestions were left out because the posting did not contain them", async () => {
    api.fetchJob.mockResolvedValue(job({ requirements_dropped: 2, facts_dropped: 1 }));
    renderDetail();
    expect(await screen.findByText(/3 suggested items were not found in the posting text/)).toBeTruthy();
  });

  it("explains a failed reading and offers to read again", async () => {
    api.fetchJob.mockResolvedValue(
      job({
        ui_state: "failed",
        title: null,
        company: null,
        error_message: "The reading service did not answer.",
        requirements: [],
        facts: {},
        eligibility_detail: null,
      }),
    );
    renderDetail();
    expect(await screen.findByText("The reading service did not answer.")).toBeTruthy();
    expect((screen.getByRole("button", { name: "Read it again" }) as HTMLButtonElement).disabled).toBe(false);
  });

  it("reads again on request", async () => {
    api.fetchJob.mockResolvedValue(job({ ui_state: "failed", eligibility_detail: null, error_message: "x" }));
    api.reanalyzeJob.mockResolvedValue(job({ ui_state: "reading" }));
    const user = userEvent.setup();
    renderDetail();
    await user.click(await screen.findByRole("button", { name: "Read it again" }));
    await waitFor(() => expect(api.reanalyzeJob).toHaveBeenCalledWith("j1"));
  });

  it("asks before deleting and goes back to the list", async () => {
    api.fetchJob.mockResolvedValue(job());
    api.deleteJob.mockResolvedValue(undefined);
    const user = userEvent.setup();
    renderDetail();
    await user.click(await screen.findByRole("button", { name: "Delete this job" }));
    expect(api.deleteJob).not.toHaveBeenCalled();
    await user.click(await screen.findByRole("button", { name: "Delete job" }));
    await waitFor(() => expect(api.deleteJob).toHaveBeenCalledWith("j1"));
    expect(await screen.findByText("Your jobs list")).toBeTruthy();
  });
});
