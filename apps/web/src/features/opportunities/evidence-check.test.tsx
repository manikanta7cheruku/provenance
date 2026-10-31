import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Analysis, VerdictRow } from "../../lib/analysis-api";
import { describeAnalysisState, describeBand, describeVerdict, isAnalysisBusy } from "../../lib/states";
import { EvidenceCheck } from "./EvidenceCheck";

const api = vi.hoisted(() => ({
  fetchAnalysis: vi.fn(),
  startAnalysis: vi.fn(),
  answerQuestion: vi.fn(),
  skipQuestion: vi.fn(),
  giveFeedback: vi.fn(),
}));
vi.mock("../../lib/analysis-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../lib/analysis-api")>()),
  ...api,
}));

function row(overrides: Partial<VerdictRow> = {}): VerdictRow {
  return {
    requirement_id: "r1",
    requirement: "Write SQL",
    kind: "required",
    category: "skill",
    posting_quote: "You will write SQL",
    verdict: "met",
    evidence_kind: "direct",
    confidence: "high",
    citations: [{ chunk_id: "c1", quote: "Skill: SQL", source: "profile", entry_type: "skill", changed: false }],
    reason: "Your skills list names SQL.",
    capped: false,
    feedback: null,
    ...overrides,
  };
}

function analysis(overrides: Partial<Analysis> = {}): Analysis {
  return {
    ui_state: "ready",
    can_start: true,
    blocker: null,
    error_message: null,
    checked: 2,
    total: 2,
    score: {
      scoring_version: "scoring-1",
      band: "good",
      required_total: 2,
      met: 1,
      partial: 1,
      conflicting: 0,
      not_verified: 0,
      preferred_total: 0,
      preferred_supported: 0,
      reasons: ["2 of 2 required requirements supported (1 fully, 1 partly)."],
    },
    verdicts: [
      row(),
      row({
        requirement_id: "r2",
        requirement: "Statistics",
        verdict: "not_verified",
        confidence: "none",
        evidence_kind: null,
        citations: [],
        reason: "Nothing in your profile supports this yet.",
      }),
    ],
    gate_requirements: [],
    questions: [],
    gaps: [],
    stale: false,
    recommendation_feedback: null,
    scoring_version: "scoring-1",
    prompt_version: "evidence-agent-1",
    ...overrides,
  };
}

function show(value: Analysis) {
  api.fetchAnalysis.mockResolvedValue(value);
  return render(
    <MemoryRouter>
      <EvidenceCheck jobId="j1" />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.resetAllMocks();
});

describe("vocabularies", () => {
  it("labels every verdict, band and check state in plain words", () => {
    expect(describeVerdict("not_verified").label).toBe("Not verified");
    expect(describeVerdict("partial").label).toBe("Partly met");
    expect(describeBand("strong").label).toBe("Strong match");
    expect(describeBand("not_eligible").tone).toBe("danger");
    expect(describeAnalysisState("needs_answer").tone).toBe("warn");
  });
  it("treats only working as busy", () => {
    expect(isAnalysisBusy("working")).toBe(true);
    for (const state of ["not_started", "needs_answer", "ready", "failed"] as const) {
      expect(isAnalysisBusy(state)).toBe(false);
    }
  });
});

describe("before the check", () => {
  it("offers to start it", async () => {
    api.startAnalysis.mockResolvedValue(analysis({ ui_state: "working" }));
    const user = userEvent.setup();
    show(analysis({ ui_state: "not_started", score: null, checked: 0 }));
    await user.click(await screen.findByRole("button", { name: "Check my evidence" }));
    await waitFor(() => expect(api.startAnalysis).toHaveBeenCalledWith("j1"));
  });

  it("says what blocks it and disables the button", async () => {
    show(analysis({ ui_state: "not_started", score: null, can_start: false, blocker: "Add your resume or a profile entry first." }));
    expect(await screen.findByText("Add your resume or a profile entry first.")).toBeTruthy();
    expect((screen.getByRole("button", { name: "Check my evidence" }) as HTMLButtonElement).disabled).toBe(true);
  });
});

describe("while it runs and when it stops", () => {
  it("shows progress and the results found so far", async () => {
    show(analysis({ ui_state: "working", score: null, checked: 1, total: 2, verdicts: [row(), row({ requirement_id: "r2", requirement: "Statistics", verdict: null })] }));
    expect(await screen.findByText(/1 of 2 checked/)).toBeTruthy();
    expect(screen.getByText("Waiting")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Check/ })).toBeNull();
  });

  it("explains a failure and offers to continue", async () => {
    show(analysis({ ui_state: "failed", score: null, error_message: "The checking service did not answer." }));
    expect(await screen.findByText("The checking service did not answer.")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Continue checking" })).toBeTruthy();
  });

  it("warns when a cited entry changed", async () => {
    show(analysis({ stale: true }));
    expect(await screen.findByText(/Something you cited changed after this check/)).toBeTruthy();
  });
});

describe("the result", () => {
  it("leads with the band, the count and the reasons, with counts and not percentages", async () => {
    show(analysis());
    expect(await screen.findByText("Good match")).toBeTruthy();
    expect(screen.getByText("2 of 2 required requirements supported")).toBeTruthy();
    expect(screen.getByText(/2 of 2 required requirements supported \(1 fully, 1 partly\)/)).toBeTruthy();
    expect(screen.getByText(/Numbers are counts, not percentages/)).toBeTruthy();
    expect(screen.queryByText(/%/)).toBeNull();
  });

  it("shows the posting's words and the person's own evidence apart, each with a label", async () => {
    show(analysis());
    await screen.findByText("Write SQL");
    expect(screen.getAllByText("The posting says").length).toBeGreaterThan(0);
    expect(screen.getByText("From your profile, skill entry")).toBeTruthy();
    expect(screen.getByText("Skill: SQL", { selector: "blockquote" })).toBeTruthy();
    expect(screen.getByText("The reader's note:")).toBeTruthy();
  });

  it("says not verified means no proof was found, with the reason", async () => {
    show(analysis());
    await screen.findByText("Statistics");
    expect(screen.getByText("Nothing in your profile supports this yet.")).toBeTruthy();
    expect(screen.getByText("No evidence from your profile is cited for this requirement.")).toBeTruthy();
  });

  it("lists what would count as proof for each gap", async () => {
    show(
      analysis({
        gaps: [
          {
            requirement_id: "r2",
            requirement: "Statistics",
            state: "not_verified",
            proof_needed: "An entry that shows you using it.",
            next_step: "Add a project entry.",
          },
        ],
      }),
    );
    expect(await screen.findByText("What would change this")).toBeTruthy();
    expect(screen.getByText("An entry that shows you using it.")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Open your profile" }).getAttribute("href")).toBe("/profile");
  });

  it("notes requirements that eligibility decides", async () => {
    show(analysis({ gate_requirements: [{ requirement_id: "g1", requirement: "Authorized to work in India", kind: "required" }] }));
    expect(await screen.findByText(/decided by the eligibility checks above/)).toBeTruthy();
  });
});

describe("feedback", () => {
  it("records an answer for one verdict and shows which button is chosen", async () => {
    api.giveFeedback.mockResolvedValue(analysis());
    const user = userEvent.setup();
    show(analysis({ verdicts: [row({ feedback: "right" })] }));
    const group = await screen.findByRole("group", { name: "Feedback on: Write SQL" });
    expect(within(group).getByRole("button", { name: "Yes, this is right" }).getAttribute("aria-pressed")).toBe("true");
    await user.click(within(group).getByRole("button", { name: "No, this is wrong" }));
    await waitFor(() =>
      expect(api.giveFeedback).toHaveBeenCalledWith("j1", { requirement_id: "r1", answer: "wrong" }),
    );
  });

  it("can rate the whole recommendation", async () => {
    api.giveFeedback.mockResolvedValue(analysis());
    const user = userEvent.setup();
    show(analysis());
    const group = await screen.findByRole("group", { name: "Feedback on this recommendation" });
    await user.click(within(group).getByRole("button", { name: "Yes, this is right" }));
    await waitFor(() =>
      expect(api.giveFeedback).toHaveBeenCalledWith("j1", { requirement_id: null, answer: "right" }),
    );
  });
});

describe("the agent's question", () => {
  const asking = () =>
    analysis({
      ui_state: "needs_answer",
      score: null,
      questions: [
        {
          id: "q1",
          requirement_id: "r2",
          requirement: "Statistics",
          question: "Did you use statistics at college?",
          status: "pending",
          answer: null,
        },
      ],
    });

  it("asks it with a label, and refuses an empty answer next to the field", async () => {
    const user = userEvent.setup();
    show(asking());
    expect(await screen.findByLabelText("Did you use statistics at college?")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Use this answer" }));
    expect(await screen.findByText("Write a short answer, or skip this question.")).toBeTruthy();
    expect(api.answerQuestion).not.toHaveBeenCalled();
  });

  it("sends the answer", async () => {
    api.answerQuestion.mockResolvedValue(analysis({ ui_state: "working" }));
    const user = userEvent.setup();
    show(asking());
    await user.type(await screen.findByLabelText("Did you use statistics at college?"), "Yes, in my thesis.");
    await user.click(screen.getByRole("button", { name: "Use this answer" }));
    await waitFor(() => expect(api.answerQuestion).toHaveBeenCalledWith("j1", "q1", "Yes, in my thesis."));
  });

  it("lets the person skip", async () => {
    api.skipQuestion.mockResolvedValue(analysis());
    const user = userEvent.setup();
    show(asking());
    await user.click(await screen.findByRole("button", { name: "Skip, leave it unverified" }));
    await waitFor(() => expect(api.skipQuestion).toHaveBeenCalledWith("j1", "q1"));
  });
});
