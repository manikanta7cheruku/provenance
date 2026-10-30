import { describe, expect, it } from "vitest";
import { BAND_TONE, SAMPLE_JOBS, SAMPLE_REQUIREMENTS, VERDICT_TONE } from "./fixtures";

describe("sample data", () => {
  it("never claims more requirements met than required", () => {
    for (const job of SAMPLE_JOBS) expect(job.met).toBeLessThanOrEqual(job.required);
  });

  it("has unique job ids and every band has a tone", () => {
    expect(new Set(SAMPLE_JOBS.map((job) => job.id)).size).toBe(SAMPLE_JOBS.length);
    for (const job of SAMPLE_JOBS) expect(BAND_TONE[job.band]).toBeDefined();
  });

  it("keeps source and acquisition method as separate honest statements", () => {
    for (const job of SAMPLE_JOBS) {
      expect(job.source.length).toBeGreaterThan(0);
      expect(job.acquisition.length).toBeGreaterThan(0);
    }
  });

  it("gives every verdict a tone and quotes the posting for every requirement", () => {
    for (const requirement of SAMPLE_REQUIREMENTS) {
      expect(VERDICT_TONE[requirement.verdict]).toBeDefined();
      expect(requirement.postingQuote.length).toBeGreaterThan(0);
    }
  });

  it("never lets inferred or missing evidence alone stand behind a Met verdict", () => {
    for (const requirement of SAMPLE_REQUIREMENTS.filter((r) => r.verdict === "Met")) {
      expect(requirement.evidence.some((item) => item.kind === "Direct")).toBe(true);
    }
  });

  it("uses no em dashes in the copy", () => {
    expect(JSON.stringify([SAMPLE_JOBS, SAMPLE_REQUIREMENTS])).not.toContain("—");
  });
});
