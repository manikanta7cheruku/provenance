import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { hourLabel, timeZones } from "../../lib/shortlist-api";
import type { Shortlist } from "../../lib/shortlist-api";
import { ShortlistSection } from "./ShortlistSection";

const api = vi.hoisted(() => ({
  fetchShortlist: vi.fn(),
  saveShortlist: vi.fn(),
  fetchPreview: vi.fn(),
  sendShortlistNow: vi.fn(),
}));
vi.mock("../../lib/shortlist-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../lib/shortlist-api")>()),
  ...api,
}));

function shortlist(overrides: Partial<Shortlist> = {}): Shortlist {
  return {
    settings: { enabled: false, frequency: "weekly", weekday: 0, hour: 8, timezone: "UTC", max_items: 5, schedule_text: "Every Monday at 08:00 (UTC)", next_run_at: null, last_run_at: null },
    runs: [],
    email_verified: true,
    blocker: null,
    delivery_note: "Development mode: email is not sent.",
    ...overrides,
  };
}

beforeEach(() => {
  vi.resetAllMocks();
});

describe("shortlist helpers", () => {
  it("lists the persons own time zone first and always has a list", () => {
    const zones = timeZones("Asia/Kolkata");
    expect(zones[0]).toBe("Asia/Kolkata");
    expect(zones).toContain("UTC");
    expect(new Set(zones).size).toBe(zones.length);
    expect(hourLabel(8)).toBe("08:00");
    expect(hourLabel(18)).toBe("18:00");
  });
});

describe("ShortlistSection", () => {
  function renderSection() {
    return render(
      <MemoryRouter>
        <ShortlistSection />
      </MemoryRouter>,
    );
  }

  it("is off by default and says nothing is sent", async () => {
    api.fetchShortlist.mockResolvedValue(shortlist());
    renderSection();
    expect(await screen.findByText("Off. Nothing is sent.")).toBeTruthy();
    expect((screen.getByLabelText("Send me a shortlist email") as HTMLInputElement).checked).toBe(false);
  });

  it("cannot be turned on for an unverified address, and says why", async () => {
    api.fetchShortlist.mockResolvedValue(shortlist({ email_verified: false, blocker: "Verify your email address first. The shortlist is only sent to a verified address." }));
    renderSection();
    expect(await screen.findByText("Verify your email address first")).toBeTruthy();
    expect((screen.getByLabelText("Send me a shortlist email") as HTMLInputElement).disabled).toBe(true);
    expect((screen.getByRole("button", { name: "Send me one now" }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("sends the chosen schedule, and a daily email has no day to choose", async () => {
    api.fetchShortlist.mockResolvedValue(shortlist());
    api.saveShortlist.mockResolvedValue(shortlist({ settings: { ...shortlist().settings, enabled: true, next_run_at: "2026-11-09T02:30:00Z" } }));
    const user = userEvent.setup();
    renderSection();
    await user.click(await screen.findByLabelText("Send me a shortlist email"));
    await user.selectOptions(screen.getByLabelText("How often"), "daily");
    expect(screen.queryByLabelText("Day")).toBeNull();
    await user.selectOptions(screen.getByLabelText("Time", { selector: "select" }), "18");
    await user.click(screen.getByRole("button", { name: "Save shortlist settings" }));
    await waitFor(() => expect(api.saveShortlist).toHaveBeenCalled());
    expect(api.saveShortlist.mock.calls[0]?.[0]).toMatchObject({ enabled: true, frequency: "daily", hour: 18 });
    expect(await screen.findByText("Saved. The shortlist email is on.")).toBeTruthy();
  });

  it("shows a refused field beside it", async () => {
    api.fetchShortlist.mockResolvedValue(shortlist());
    const { ApiError } = await import("../../lib/api");
    api.saveShortlist.mockRejectedValue(new ApiError(422, "VALIDATION_FAILED", "Some details need fixing.", { timezone: "Choose a time zone from the list." }, null));
    const user = userEvent.setup();
    renderSection();
    await user.click(await screen.findByRole("button", { name: "Save shortlist settings" }));
    expect(await screen.findByText("Choose a time zone from the list.")).toBeTruthy();
  });

  it("previews each job with its reason and says when there is nothing", async () => {
    api.fetchShortlist.mockResolvedValue(shortlist());
    api.fetchPreview.mockResolvedValueOnce({ items: [{ id: "a", title: "Backend engineer", company: "Acme", location: "Pune", band: "strong", eligibility: "eligible", reason: "Strong match: 9 of 11 supported." }], note: "These are the jobs that would be in an email now." });
    api.fetchPreview.mockResolvedValueOnce({ items: [], note: "Nothing would be sent now." });
    const user = userEvent.setup();
    renderSection();
    await user.click(await screen.findByRole("button", { name: "Preview what would be sent now" }));
    expect(await screen.findByText("Strong match: 9 of 11 supported.")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Backend engineer" }).getAttribute("href")).toBe("/opportunities/a");
    await user.click(screen.getByRole("button", { name: "Preview what would be sent now" }));
    expect(await screen.findByText("Nothing would be sent now.")).toBeTruthy();
  });

  it("queues one now and says what will happen", async () => {
    api.fetchShortlist.mockResolvedValue(shortlist());
    api.sendShortlistNow.mockResolvedValue({ queued: true, message: "Queued. If anything is worth a look it will arrive shortly." });
    const user = userEvent.setup();
    renderSection();
    await user.click(await screen.findByRole("button", { name: "Send me one now" }));
    expect(await screen.findByText(/Queued\. If anything is worth a look/)).toBeTruthy();
  });

  it("shows the history in words", async () => {
    api.fetchShortlist.mockResolvedValue(shortlist({ runs: [{ outcome: "sent", outcome_text: "Sent", item_count: 3, manual: true, at: "2026-11-02T08:00:00Z" }] }));
    renderSection();
    expect(await screen.findByText("You asked for this one")).toBeTruthy();
    expect(screen.getByText("Sent")).toBeTruthy();
  });
});
