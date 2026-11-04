import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ImportBatch, ImportDetail } from "../../lib/imports-api";
import { describeImport, describeItem, isImportBusy, kindLabel } from "../../lib/imports-api";
import { acquisitionLabel } from "./labels";
import { ImportFileForm } from "./ImportFileForm";
import { ImportReportPage } from "./ImportReportPage";
import { ImportUrlForm } from "./ImportUrlForm";
import { ManualJobForm } from "./ManualJobForm";

const api = vi.hoisted(() => ({
  enterJob: vi.fn(),
  startUrlImport: vi.fn(),
  startFileImport: vi.fn(),
  fetchImport: vi.fn(),
}));
vi.mock("../../lib/imports-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../lib/imports-api")>()),
  ...api,
}));

function batch(overrides: Partial<ImportDetail> = {}): ImportDetail {
  return {
    id: "b1",
    kind: "csv",
    label: "jobs.csv",
    default_source: "Other",
    status: "done",
    error_message: null,
    total_rows: 2,
    created_count: 1,
    duplicate_count: 0,
    rejected_count: 1,
    ignored_columns: ["Salary"],
    created_at: "2026-11-04T09:00:00Z",
    finished_at: "2026-11-04T09:00:02Z",
    items: [
      { row_number: 2, status: "created", code: null, message: null, title: "Backend engineer", source_url: null, posting_id: "p1" },
      { row_number: 3, status: "rejected", code: "bad_link", message: "The link is not a web address.", title: "Broken", source_url: null, posting_id: null },
    ],
    ...overrides,
  };
}

beforeEach(() => {
  vi.resetAllMocks();
});

describe("import words", () => {
  it("says every state in words", () => {
    expect(describeImport({ status: "queued", created_count: 0, rejected_count: 0 }).label).toBe("Waiting to start");
    expect(describeImport({ status: "running", created_count: 0, rejected_count: 0 }).label).toBe("Reading");
    expect(describeImport({ status: "failed", created_count: 0, rejected_count: 0 }).tone).toBe("danger");
    expect(describeImport({ status: "done", created_count: 3, rejected_count: 0 }).label).toBe("Done");
    expect(describeImport({ status: "done", created_count: 3, rejected_count: 1 }).tone).toBe("warn");
    expect(describeImport({ status: "done", created_count: 0, rejected_count: 2 }).label).toBe("Nothing added");
    for (const item of ["queued", "created", "duplicate", "rejected"] as const) {
      expect(describeItem(item).label.length).toBeGreaterThan(0);
    }
    expect(kindLabel("xlsx")).toBe("Excel file");
  });
  it("treats only queued and running as busy", () => {
    expect(isImportBusy({ status: "queued" })).toBe(true);
    expect(isImportBusy({ status: "running" })).toBe(true);
    expect(isImportBusy({ status: "done" })).toBe(false);
    expect(isImportBusy({ status: "failed" })).toBe(false);
  });
  it("labels every way a job arrives", () => {
    expect(acquisitionLabel("manual_entry")).toBe("Typed in by you");
    expect(acquisitionLabel("csv_import")).toBe("From your CSV file");
    expect(acquisitionLabel("xlsx_import")).toBe("From your Excel file");
    expect(acquisitionLabel("url_import")).toBe("Read from a link you gave");
  });
});

describe("ManualJobForm", () => {
  it("asks for a title and enough description before sending", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <ManualJobForm onAdded={() => undefined} />
      </MemoryRouter>,
    );
    await user.click(screen.getByRole("button", { name: "Read this job" }));
    expect(await screen.findByText("Enter the job title.")).toBeTruthy();
    expect(screen.getByText(/Add more of the description/)).toBeTruthy();
    expect(api.enterJob).not.toHaveBeenCalled();
  });

  it("sends the fields and opens the job", async () => {
    api.enterJob.mockResolvedValue({ job: { id: "j9" }, duplicate: false });
    const onAdded = vi.fn();
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/opportunities"]}>
        <Routes>
          <Route path="/opportunities" element={<ManualJobForm onAdded={onAdded} />} />
          <Route path="/opportunities/:jobId" element={<p>Job page</p>} />
        </Routes>
      </MemoryRouter>,
    );
    await user.type(screen.getByLabelText("Job title"), "Backend engineer");
    await user.type(screen.getByLabelText(/Company/), "Acme");
    await user.type(screen.getByLabelText("What the job asks for"), "x".repeat(120));
    await user.click(screen.getByRole("button", { name: "Read this job" }));
    await waitFor(() => expect(api.enterJob).toHaveBeenCalled());
    expect(api.enterJob.mock.calls[0]?.[0]).toMatchObject({ title: "Backend engineer", company: "Acme", source_url: null });
    expect(await screen.findByText("Job page")).toBeTruthy();
    expect(onAdded).toHaveBeenCalled();
  });
});

describe("ImportUrlForm", () => {
  it("refuses an address that is not https before sending", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <ImportUrlForm onStarted={() => undefined} />
      </MemoryRouter>,
    );
    await user.type(screen.getByLabelText(/Web address/), "http://jobs.example.com/1");
    await user.click(screen.getByRole("button", { name: "Read this page" }));
    expect(await screen.findByText("Enter an address that starts with https://.")).toBeTruthy();
    expect(api.startUrlImport).not.toHaveBeenCalled();
  });

  it("starts the import and opens its report", async () => {
    api.startUrlImport.mockResolvedValue(batch({ id: "b7", kind: "url", status: "queued" }));
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/opportunities"]}>
        <Routes>
          <Route path="/opportunities" element={<ImportUrlForm onStarted={() => undefined} />} />
          <Route path="/opportunities/imports/:batchId" element={<p>Report page</p>} />
        </Routes>
      </MemoryRouter>,
    );
    await user.type(screen.getByLabelText(/Web address/), "https://jobs.acme-careers.com/1");
    await user.click(screen.getByRole("button", { name: "Read this page" }));
    expect(await screen.findByText("Report page")).toBeTruthy();
    expect(api.startUrlImport).toHaveBeenCalledWith("https://jobs.acme-careers.com/1", "Company career page");
  });

  it("shows the sentence the server gives for a refused address", async () => {
    const { ApiError } = await import("../../lib/api");
    api.startUrlImport.mockRejectedValue(
      new ApiError(422, "VALIDATION_FAILED", "Some details need fixing.", { url: "That address is not on the public internet." }, null),
    );
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <ImportUrlForm onStarted={() => undefined} />
      </MemoryRouter>,
    );
    await user.type(screen.getByLabelText(/Web address/), "https://localhost/");
    await user.click(screen.getByRole("button", { name: "Read this page" }));
    expect(await screen.findByText("That address is not on the public internet.")).toBeTruthy();
  });
});

describe("ImportFileForm", () => {
  it("needs a file before it sends", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <ImportFileForm onStarted={() => undefined} />
      </MemoryRouter>,
    );
    await user.click(screen.getByRole("button", { name: "Import these jobs" }));
    expect(await screen.findByText("Choose a CSV or Excel file first.")).toBeTruthy();
    expect(api.startFileImport).not.toHaveBeenCalled();
  });

  it("refuses a file of the wrong type in the browser", async () => {
    const user = userEvent.setup({ applyAccept: false });
    render(
      <MemoryRouter>
        <ImportFileForm onStarted={() => undefined} />
      </MemoryRouter>,
    );
    await user.upload(screen.getByLabelText("Spreadsheet"), new File(["x"], "jobs.pdf", { type: "application/pdf" }));
    expect(await screen.findByText(/This file type is not supported/)).toBeTruthy();
  });

  it("uploads a chosen file with the source label and opens the report", async () => {
    api.startFileImport.mockResolvedValue(batch({ id: "b8", status: "queued" }));
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/opportunities"]}>
        <Routes>
          <Route path="/opportunities" element={<ImportFileForm onStarted={() => undefined} />} />
          <Route path="/opportunities/imports/:batchId" element={<p>Report page</p>} />
        </Routes>
      </MemoryRouter>,
    );
    await user.upload(screen.getByLabelText("Spreadsheet"), new File(["Description\nx"], "jobs.csv", { type: "text/csv" }));
    await user.click(screen.getByRole("button", { name: "Import these jobs" }));
    expect(await screen.findByText("Report page")).toBeTruthy();
    expect(api.startFileImport.mock.calls[0]?.[0].name).toBe("jobs.csv");
    expect(api.startFileImport.mock.calls[0]?.[1]).toBe("Other");
  });
});

describe("ImportReportPage", () => {
  function renderReport() {
    return render(
      <MemoryRouter initialEntries={["/opportunities/imports/b1"]}>
        <Routes>
          <Route path="/opportunities/imports/:batchId" element={<ImportReportPage />} />
        </Routes>
      </MemoryRouter>,
    );
  }

  it("shows the counts, every row with its words, and the unused columns", async () => {
    api.fetchImport.mockResolvedValue(batch());
    renderReport();
    expect(await screen.findByText("Done, some rows need fixing")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Backend engineer" }).getAttribute("href")).toBe("/opportunities/p1");
    expect(screen.getByText("The link is not a web address.")).toBeTruthy();
    expect(screen.getAllByText("Added").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Not added").length).toBeGreaterThan(0);
    expect(screen.getByText(/Columns that were not used: Salary/)).toBeTruthy();
  });

  it("says what to do when the whole file failed", async () => {
    api.fetchImport.mockResolvedValue(
      batch({ status: "failed", items: [], error_message: "No column holds the job description." }),
    );
    renderReport();
    expect(await screen.findByText("No column holds the job description.")).toBeTruthy();
    expect(screen.getByText(/Nothing was added/)).toBeTruthy();
  });

  it("tells the person they can leave while it is reading", async () => {
    api.fetchImport.mockResolvedValue(batch({ status: "running", items: [] }));
    renderReport();
    expect(await screen.findByText(/You can leave this page/)).toBeTruthy();
  });

  it("offers a retry when the report cannot be loaded", async () => {
    api.fetchImport.mockRejectedValue(new Error("The server is not answering."));
    renderReport();
    expect(await screen.findByText(/could not be loaded/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Try again" })).toBeTruthy();
  });
});
