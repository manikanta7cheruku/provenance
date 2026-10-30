import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { EvidenceHit, EvidenceStatus } from "../../lib/evidence-api";
import { describeStatus, EvidenceSection, matchedLabel } from "./EvidenceSection";

const api = vi.hoisted(() => ({ fetchEvidenceStatus: vi.fn(), searchEvidence: vi.fn() }));
vi.mock("../../lib/evidence-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../lib/evidence-api")>()),
  ...api,
}));

function status(overrides: Partial<EvidenceStatus> = {}): EvidenceStatus {
  return { indexed: 3, embedded: 0, pending: 3, meaning_search_configured: false, ...overrides };
}

function hit(overrides: Partial<EvidenceHit> = {}): EvidenceHit {
  return {
    chunk_id: "c1",
    entry_id: "e1",
    source_type: "profile_entry",
    entry_type: "skill",
    text: "Skill: Python",
    score: 0.03,
    matched_by: ["keyword"],
    keyword_rank: 1,
    meaning_rank: null,
    similarity: null,
    ...overrides,
  };
}

describe("describeStatus", () => {
  it("says there is nothing to search with no entries", () => {
    expect(describeStatus(status({ indexed: 0, pending: 0 }))).toContain("Nothing to search yet");
  });
  it("is honest that meaning search needs a key", () => {
    expect(describeStatus(status())).toBe(
      "3 entries are searchable by keyword. Meaning search is off until an AI key is set up.",
    );
  });
  it("shows indexing progress and readiness", () => {
    const configured = { meaning_search_configured: true };
    expect(describeStatus(status({ ...configured, embedded: 1, pending: 2 }))).toContain("1 of 3 done");
    expect(describeStatus(status({ ...configured, embedded: 3, pending: 0 }))).toContain(
      "Meaning search is ready.",
    );
  });
  it("uses the singular for one entry", () => {
    expect(describeStatus(status({ indexed: 1, pending: 1 }))).toContain("1 entry is searchable");
  });
});

describe("matchedLabel", () => {
  it("names how a result was found", () => {
    expect(matchedLabel(hit())).toBe("Found by keyword");
    expect(matchedLabel(hit({ matched_by: ["meaning"] }))).toBe("Found by meaning");
    expect(matchedLabel(hit({ matched_by: ["keyword", "meaning"] }))).toBe(
      "Found by keyword and by meaning",
    );
  });
});

describe("EvidenceSection", () => {
  beforeEach(() => {
    api.fetchEvidenceStatus.mockReset().mockResolvedValue(status());
    api.searchEvidence.mockReset();
  });

  it("asks for a query before searching and moves focus to the field", async () => {
    render(<EvidenceSection version={0} />);
    await userEvent.click(await screen.findByRole("button", { name: "Search" }));
    expect(screen.getByText("Enter a word, a phrase or a question.")).toBeTruthy();
    expect(api.searchEvidence).not.toHaveBeenCalled();
    expect(document.activeElement).toBe(screen.getByLabelText("Search your entries"));
  });

  it("shows matches with where they came from and the note from the server", async () => {
    api.searchEvidence.mockResolvedValue({
      query: "python",
      meaning_search_used: false,
      note: "Meaning search needs an AI key. Showing keyword matches only.",
      hits: [hit()],
    });
    render(<EvidenceSection version={0} />);
    await userEvent.type(await screen.findByLabelText("Search your entries"), "python{Enter}");
    expect(await screen.findByText("1 match, best first.")).toBeTruthy();
    expect(screen.getByText("Skill: Python")).toBeTruthy();
    expect(screen.getByText(/From your profile/)).toBeTruthy();
    expect(screen.getByText(/Meaning search needs an AI key/)).toBeTruthy();
    expect(screen.getByRole("link", { name: "Show in your entries" }).getAttribute("href")).toBe(
      "#entry-e1",
    );
  });

  it("says plainly when nothing matches", async () => {
    api.searchEvidence.mockResolvedValue({ query: "x", meaning_search_used: false, note: null, hits: [] });
    render(<EvidenceSection version={0} />);
    await userEvent.type(await screen.findByLabelText("Search your entries"), "x{Enter}");
    expect(await screen.findByText("No entry matches that.")).toBeTruthy();
  });

  it("disables search when there is nothing to search", async () => {
    api.fetchEvidenceStatus.mockResolvedValue(status({ indexed: 0, pending: 0 }));
    render(<EvidenceSection version={0} />);
    await waitFor(() => {
      const button = screen.getByRole("button", { name: "Search" }) as HTMLButtonElement;
      expect(button.disabled).toBe(true);
    });
  });

  it("shows a retry when the status cannot be loaded", async () => {
    api.fetchEvidenceStatus.mockRejectedValue(new Error("Could not reach the server."));
    render(<EvidenceSection version={0} />);
    expect(await screen.findByText(/Search could not be loaded/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Try again" })).toBeTruthy();
  });
});
