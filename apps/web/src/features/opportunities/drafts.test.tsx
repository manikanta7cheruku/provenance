import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { daysAgo } from "../../lib/format";
import { describeClaimKind, isWriting, unsupportedClaims } from "../../lib/drafts-api";
import type { Draft, Drafts as DraftsData } from "../../lib/drafts-api";
import { Drafts } from "./Drafts";

const api = vi.hoisted(() => ({
  fetchDrafts: vi.fn(),
  startDraft: vi.fn(),
  saveDraft: vi.fn(),
  deleteDraft: vi.fn(),
}));
vi.mock("../../lib/drafts-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../lib/drafts-api")>()),
  fetchDrafts: api.fetchDrafts,
  startDraft: api.startDraft,
  saveDraft: api.saveDraft,
  deleteDraft: api.deleteDraft,
}));

const LABEL = "Draft. Written by AI from your own evidence. Check every line. Nothing is sent anywhere.";

function draft(overrides: Partial<Draft> = {}): Draft {
  return {
    id: "d1",
    kind: "cover_note",
    question: "",
    body: "I built 30 REST endpoints with FastAPI.",
    ui_state: "ready",
    origin: "model",
    error_message: null,
    claims: [{ text: "30", kind: "number", supported: true, source: "evidence" }],
    unsupported_count: 0,
    word_count: 7,
    evidence: [{ text: "Built 30 REST endpoints.", source: "profile", cited: true }],
    updated_at: "2026-11-04T09:00:00Z",
    ...overrides,
  };
}

function drafts(list: Draft[] = [], overrides: Partial<DraftsData> = {}): DraftsData {
  return {
    drafts: list,
    can_write: true,
    blocker: null,
    questions: [{ key: "why_role", text: "Why are you interested in this role?" }],
    max_drafts: 8,
    label: LABEL,
    ...overrides,
  };
}

beforeEach(() => {
  vi.resetAllMocks();
});

describe("helpers", () => {
  it("names the unsupported claims in a draft and what kind each is", () => {
    const d = draft({ claims: [{ text: "30", kind: "number", supported: true, source: "evidence" }, { text: "kubernetes", kind: "name", supported: false, source: null }] });
    expect(unsupportedClaims(d)).toEqual(["kubernetes"]);
    expect(describeClaimKind("number")).toBe("a number");
    expect(describeClaimKind("job term")).toBe("a word the job asks for");
    expect(describeClaimKind("whatever")).toBe("a claim");
  });
  it("knows when something is still being written", () => {
    expect(isWriting(null)).toBe(false);
    expect(isWriting(drafts([draft({ ui_state: "working" })]))).toBe(true);
    expect(isWriting(drafts([draft()]))).toBe(false);
  });
  it("says how long ago in words and never throws", () => {
    const now = new Date("2026-11-04T12:00:00Z");
    expect(daysAgo("2026-11-04T08:00:00Z", now)).toBe("today");
    expect(daysAgo("2026-11-03T08:00:00Z", now)).toBe("1 day ago");
    expect(daysAgo("2026-10-26T08:00:00Z", now)).toBe("9 days ago");
    expect(daysAgo(null, now)).toBe("");
    expect(daysAgo("not a date", now)).toBe("");
  });
});

describe("Drafts", () => {
  it("always says it is a draft and that nothing is sent", async () => {
    api.fetchDrafts.mockResolvedValue(drafts());
    render(<Drafts jobId="j1" />);
    expect(await screen.findByText(LABEL)).toBeTruthy();
    expect(screen.getByText(/No drafts yet/)).toBeTruthy();
  });

  it("says what is needed when the job has not been checked and offers no way to write", async () => {
    api.fetchDrafts.mockResolvedValue(drafts([], { can_write: false, blocker: "Check this job against your evidence first." }));
    render(<Drafts jobId="j1" />);
    expect(await screen.findByText("Check this job against your evidence first.")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Write a cover note" })).toBeNull();
  });

  it("asks for a cover note and for an answer to the chosen question", async () => {
    api.fetchDrafts.mockResolvedValue(drafts());
    api.startDraft.mockResolvedValue(drafts([draft({ ui_state: "working" })]));
    const user = userEvent.setup();
    render(<Drafts jobId="j1" />);
    await user.click(await screen.findByRole("button", { name: "Write a cover note" }));
    await waitFor(() => expect(api.startDraft).toHaveBeenCalledWith("j1", "cover_note", ""));
    await user.click(screen.getByRole("button", { name: "Write an answer" }));
    await waitFor(() => expect(api.startDraft).toHaveBeenCalledWith("j1", "answer", "Why are you interested in this role?"));
  });

  it("names every claim that is not in the evidence, and the kind it is", async () => {
    api.fetchDrafts.mockResolvedValue(
      drafts([draft({ unsupported_count: 1, claims: [{ text: "kubernetes", kind: "name", supported: false, source: null }] })]),
    );
    render(<Drafts jobId="j1" />);
    expect(await screen.findByText("Check these before you use this draft")).toBeTruthy();
    expect(screen.getByText("kubernetes")).toBeTruthy();
    expect(screen.getByText(/a name or tool/)).toBeTruthy();
  });

  it("says when every claim is supported", async () => {
    api.fetchDrafts.mockResolvedValue(drafts([draft()]));
    render(<Drafts jobId="j1" />);
    expect(await screen.findByText(/Every number, name and tool in this draft is in your evidence/)).toBeTruthy();
  });

  it("saves only when the text changed, and shows the server's refusal", async () => {
    api.fetchDrafts.mockResolvedValue(drafts([draft()]));
    const { ApiError } = await import("../../lib/api");
    api.saveDraft.mockRejectedValue(new ApiError(422, "VALIDATION_FAILED", "Some details need fixing.", { body: "A draft can be up to 6,000 characters and cannot be empty." }, null));
    const user = userEvent.setup();
    render(<Drafts jobId="j1" />);
    const save = (await screen.findByRole("button", { name: "Save changes" })) as HTMLButtonElement;
    expect(save.disabled).toBe(true);
    await user.type(screen.getByLabelText("Draft text"), " More.");
    expect(save.disabled).toBe(false);
    await user.click(save);
    expect(await screen.findByText(/cannot be empty/)).toBeTruthy();
  });

  it("asks before writing an edited draft again, and sends replace only after the person agrees", async () => {
    api.fetchDrafts.mockResolvedValue(drafts([draft({ origin: "edited" })]));
    api.startDraft.mockResolvedValue(drafts([draft({ ui_state: "working" })]));
    const user = userEvent.setup();
    render(<Drafts jobId="j1" />);
    await user.click(await screen.findByRole("button", { name: /Write it again/ }));
    expect(api.startDraft).not.toHaveBeenCalled();
    expect(await screen.findByText(/replaces your edits with new text/)).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Replace my edits" }));
    await waitFor(() => expect(api.startDraft).toHaveBeenCalledWith("j1", "cover_note", "", true));
  });

  it("shows why a draft failed and keeps the earlier text", async () => {
    api.fetchDrafts.mockResolvedValue(drafts([draft({ ui_state: "failed", error_message: "The writing service did not answer." })]));
    render(<Drafts jobId="j1" />);
    expect(await screen.findByText("The writing service did not answer.")).toBeTruthy();
    expect(screen.getByText("The earlier text is still below.")).toBeTruthy();
  });

  it("offers a retry when drafts cannot be loaded", async () => {
    api.fetchDrafts.mockRejectedValue(new Error("The server is not answering."));
    render(<Drafts jobId="j1" />);
    expect(await screen.findByText(/could not be loaded/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Try again" })).toBeTruthy();
  });
});

