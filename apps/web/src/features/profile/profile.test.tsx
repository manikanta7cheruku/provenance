import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { EntrySpec, ProfileEntry } from "../../lib/profile-api";
import type { Resume } from "../../lib/resume-api";
import { flagLabels, provenanceLabel, summarize } from "./describe";
import { EntryForm } from "./EntryForm";
import { ResumeSection } from "./ResumeSection";

const WORK_SPEC: EntrySpec = {
  entry_type: "work",
  label: "Work experience",
  plural: "Work experience",
  primary_field: "company",
  fields: [
    { name: "company", label: "Company", kind: "text", max_length: 120, required: true, recommended: false, hint: "" },
    { name: "title", label: "Role", kind: "text", max_length: 120, required: true, recommended: false, hint: "" },
    { name: "start_date", label: "Start", kind: "date", max_length: 7, required: false, recommended: true, hint: "YYYY or YYYY-MM" },
    { name: "highlights", label: "What you did", kind: "list", max_length: 400, required: false, recommended: true, hint: "One per line." },
  ],
};

function entry(overrides: Partial<ProfileEntry> = {}): ProfileEntry {
  return {
    id: "e1",
    entry_type: "work",
    data: { company: "Kestrel Analytics", title: "Data Intern", start_date: "2024-06", end_date: "2024-08" },
    user_edited: false,
    source: "resume",
    flags: [],
    created_at: "2026-10-30T09:00:00Z",
    updated_at: "2026-10-30T09:00:00Z",
    ...overrides,
  };
}

describe("describe", () => {
  it("summarizes a work entry with its period", () => {
    const info = summarize(entry(), WORK_SPEC);
    expect(info.title).toBe("Kestrel Analytics");
    expect(info.subtitle).toBe("Data Intern · 2024-06 to 2024-08");
  });

  it("never shows an empty title", () => {
    expect(summarize(entry({ data: {} }), WORK_SPEC).title).toBe("Untitled");
  });

  it("says where an entry came from, and that an edit makes it the person's own", () => {
    expect(provenanceLabel(entry())).toBe("From your resume");
    expect(provenanceLabel(entry({ user_edited: true }))).toBe("Added or edited by you");
    expect(provenanceLabel(entry({ source: "user" }))).toBe("Added or edited by you");
  });

  it("names missing fields with their labels", () => {
    expect(flagLabels(entry({ flags: ["start_date", "highlights"] }), WORK_SPEC)).toEqual([
      "Start",
      "What you did",
    ]);
  });
});

describe("EntryForm", () => {
  it("draws its fields from the spec and marks optional ones", () => {
    render(<EntryForm spec={WORK_SPEC} initial={null} onSave={vi.fn()} onCancel={vi.fn()} />);
    expect(screen.getByLabelText("Company")).toBeTruthy();
    expect(screen.getByLabelText("Start (optional)")).toBeTruthy();
    expect(screen.getByText("YYYY or YYYY-MM")).toBeTruthy();
  });

  it("blocks saving without the required fields and says which", async () => {
    const onSave = vi.fn();
    render(<EntryForm spec={WORK_SPEC} initial={null} onSave={onSave} onCancel={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(onSave).not.toHaveBeenCalled();
    expect(screen.getAllByText("This is required.")).toHaveLength(2);
    expect(document.activeElement).toBe(screen.getByLabelText("Company"));
  });

  it("sends trimmed values and turns one-per-line text into a list", async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    render(<EntryForm spec={WORK_SPEC} initial={null} onSave={onSave} onCancel={vi.fn()} />);
    await userEvent.type(screen.getByLabelText("Company"), "  Kestrel  ");
    await userEvent.type(screen.getByLabelText("Role"), "Intern");
    await userEvent.type(screen.getByLabelText("What you did (optional)"), "Built a report{Enter}Cleaned data");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(onSave).toHaveBeenCalledOnce());
    expect(onSave).toHaveBeenCalledWith({
      company: "Kestrel",
      title: "Intern",
      highlights: ["Built a report", "Cleaned data"],
    });
  });

  it("shows the server's field messages beside the field", async () => {
    const { ApiError } = await import("../../lib/api");
    const onSave = vi.fn().mockRejectedValue(
      new ApiError(422, "VALIDATION_FAILED", "Some details need fixing.", {
        start_date: "Use YYYY or YYYY-MM, or the word present for an end date.",
      }),
    );
    render(
      <EntryForm
        spec={WORK_SPEC}
        initial={{ company: "Kestrel", title: "Intern", start_date: "June 2024" }}
        onSave={onSave}
        onCancel={vi.fn()}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByText(/Use YYYY or YYYY-MM/)).toBeTruthy();
  });

  it("cancels on Escape without saving", async () => {
    const onCancel = vi.fn();
    const onSave = vi.fn();
    render(<EntryForm spec={WORK_SPEC} initial={null} onSave={onSave} onCancel={onCancel} />);
    await userEvent.type(screen.getByLabelText("Company"), "x{Escape}");
    expect(onCancel).toHaveBeenCalledOnce();
    expect(onSave).not.toHaveBeenCalled();
  });
});

const api = vi.hoisted(() => ({
  fetchResume: vi.fn(),
  uploadResume: vi.fn(),
  deleteResume: vi.fn(),
  reparseResume: vi.fn(),
  confirmResume: vi.fn(),
}));

vi.mock("../../lib/resume-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../lib/resume-api")>()),
  ...api,
}));

function resume(overrides: Partial<Resume> = {}): Resume {
  return {
    id: "r1",
    original_filename: "Asha CV.pdf",
    file_kind: "pdf",
    size_bytes: 52_000,
    ui_state: "parsed",
    can_retry: true,
    error_message: null,
    kept_entry_count: 6,
    dropped_entry_count: 0,
    flagged_entry_count: 0,
    page_count: 1,
    run_id: "run1",
    created_at: "2026-10-30T09:00:00Z",
    parsed_at: "2026-10-30T09:00:10Z",
    confirmed_at: null,
    ...overrides,
  };
}

describe("ResumeSection", () => {
  beforeEach(() => {
    for (const mock of Object.values(api)) mock.mockReset();
  });

  it("offers an upload when there is no resume, with the limits stated", async () => {
    api.fetchResume.mockResolvedValue(null);
    render(<ResumeSection onChanged={vi.fn()} />);
    expect(await screen.findByLabelText("Resume")).toBeTruthy();
    expect(screen.getByText(/PDF or DOCX, up to 5\.0 MB/)).toBeTruthy();
    expect(screen.getByText(/add your entries by hand/i)).toBeTruthy();
  });

  it("uploads a chosen file and then shows the server's state", async () => {
    api.fetchResume.mockResolvedValueOnce(null).mockResolvedValue(resume({ ui_state: "uploaded", parsed_at: null }));
    api.uploadResume.mockResolvedValue(resume({ ui_state: "uploaded", parsed_at: null }));
    render(<ResumeSection onChanged={vi.fn()} />);
    const input = await screen.findByLabelText("Resume");
    await userEvent.upload(input, new File(["%PDF-1.4 test"], "cv.pdf"));
    await waitFor(() => expect(api.uploadResume).toHaveBeenCalledOnce());
    expect(await screen.findByText("Uploaded")).toBeTruthy();
  });

  it("shows the server's plain message when an upload is refused", async () => {
    const { ApiError } = await import("../../lib/api");
    api.fetchResume.mockResolvedValue(null);
    api.uploadResume.mockRejectedValue(
      new ApiError(415, "UNSUPPORTED_FILE", "This file type is not supported. Choose a PDF or DOCX file."),
    );
    render(<ResumeSection onChanged={vi.fn()} />);
    await userEvent.upload(await screen.findByLabelText("Resume"), new File(["x"], "cv.pdf"));
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(screen.getByRole("alert").textContent).toContain("not supported");
  });

  it("explains what was left out because it was not in the resume", async () => {
    api.fetchResume.mockResolvedValue(resume({ dropped_entry_count: 2 }));
    render(<ResumeSection onChanged={vi.fn()} />);
    expect(await screen.findByText(/2 suggested items were not in your resume text/)).toBeTruthy();
  });

  it("offers Confirm my profile when parsed and Confirm anyway when it needs correction", async () => {
    api.fetchResume.mockResolvedValue(resume());
    const first = render(<ResumeSection onChanged={vi.fn()} />);
    expect(await screen.findByRole("button", { name: "Confirm my profile" })).toBeTruthy();
    first.unmount();
    api.fetchResume.mockResolvedValue(resume({ ui_state: "needs_correction", flagged_entry_count: 3 }));
    render(<ResumeSection onChanged={vi.fn()} />);
    expect(await screen.findByRole("button", { name: "Confirm anyway" })).toBeTruthy();
  });

  it("shows a failure with the reason and a way forward", async () => {
    api.fetchResume.mockResolvedValue(
      resume({
        ui_state: "failed",
        error_message: "The reading service did not answer. Your file is safe. Try again in a few minutes.",
        parsed_at: null,
      }),
    );
    render(<ResumeSection onChanged={vi.fn()} />);
    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText(/Your file is safe/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Read it again" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Confirm/ })).toBeNull();
  });

  it("asks before deleting and says what is kept", async () => {
    api.fetchResume.mockResolvedValue(resume());
    api.deleteResume.mockResolvedValue(undefined);
    render(<ResumeSection onChanged={vi.fn()} />);
    await userEvent.click(await screen.findByRole("button", { name: "Delete resume" }));
    expect(await screen.findByText(/entries in your profile stay/)).toBeTruthy();
    expect(api.deleteResume).not.toHaveBeenCalled();
  });

  it("links the download to the owner-only route", async () => {
    api.fetchResume.mockResolvedValue(resume());
    render(<ResumeSection onChanged={vi.fn()} />);
    const link = await screen.findByRole("link", { name: "Download my file" });
    expect(link.getAttribute("href")).toBe("/api/v1/resume/file");
  });
});
