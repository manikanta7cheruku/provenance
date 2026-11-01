import { describe, expect, it } from "vitest";
import type { ResumeContent } from "../../../lib/studio-api";
import { analyzeAts } from "./ats";
import { structuredToCanvas } from "./convert";
import { richText } from "./rich";
import { allElements, pageSize } from "./types";
import type { TextElement } from "./types";

/** A stand-in for the browser: every line of text is 5 mm, and a bullet list counts each item. */
const measure = (el: TextElement) => {
  const lines = (el.body?.content ?? []).reduce((n, node) => n + (node.type === "paragraph" ? 1 : (node.content?.length ?? 1)), 0);
  return Math.max(1, lines) * 5;
};

function resume(overrides: Partial<ResumeContent> = {}): ResumeContent {
  const block = (heading: string, dates: string, lines: string[] = []) => ({
    id: heading,
    heading,
    subheading: "Kestrel",
    dates,
    location: "",
    body: lines.length
      ? {
          type: "doc" as const,
          content: [
            {
              type: "bulletList",
              content: lines.map((l) => ({ type: "listItem", content: [{ type: "paragraph", content: [{ type: "text", text: l }] }] })),
            },
          ],
        }
      : null,
  });
  return {
    version: 1,
    style: { template: "classic", font_pair: "plex-newsreader", size: "medium", spacing: "normal", margins: "normal", accent: "#222222", divider: "thin", paper: "a4" },
    header: { name: "Asha Rao", headline: "Data analyst", contacts: ["asha@example.com", "Bengaluru"] },
    sections: [
      { id: "s1", kind: "experience", title: "Experience", blocks: [block("Data Intern", "2025", ["Cleaned data", "Wrote SQL"]), block("Backend Intern", "2024")] },
      { id: "s2", kind: "education", title: "Education", blocks: [block("B.E. Computer Science", "")] },
    ],
    ...overrides,
  };
}

describe("laying a guided resume out on the canvas", () => {
  it("makes version 2 with the same paper, fonts and accent", () => {
    const doc = structuredToCanvas(resume(), measure);
    expect(doc.version).toBe(2);
    expect(doc.style).toMatchObject({ font_pair: "plex-newsreader", accent: "#222222", paper: "a4", margin_mm: 16 });
  });

  it("puts the name, headline and contacts first, in the heading font and the accent color", () => {
    const [name, headline, contacts] = allElements(structuredToCanvas(resume(), measure)) as TextElement[];
    expect([name?.name, headline?.name, contacts?.name]).toEqual(["Name", "Headline", "Contacts"]);
    expect(richText(name!.body)).toBe("Asha Rao");
    expect(name).toMatchObject({ font: "heading", color: "accent" });
    expect(richText(contacts!.body)).toContain("asha@example.com");
  });

  it("stacks everything top to bottom with no overlap and stays inside the margins", () => {
    const doc = structuredToCanvas(resume(), measure);
    const [pw, ph] = pageSize(doc.style);
    for (const page of doc.pages) {
      const els = page.elements;
      for (const el of els) {
        expect(el.x).toBeGreaterThanOrEqual(16 - 0.01);
        expect(el.x + el.w).toBeLessThanOrEqual(pw - 16 + 0.01);
        expect(el.y + el.h).toBeLessThanOrEqual(ph - 16 + 0.5);
      }
    }
    expect(analyzeAts(doc)).toEqual({ safe: true, issues: [] });
  });

  it("puts a date in its own right-aligned box on the same row as its item", () => {
    const els = allElements(structuredToCanvas(resume(), measure)) as TextElement[];
    const item = els.find((e) => e.name === "Data Intern")!;
    const date = els.find((e) => e.name === "Data Intern dates")!;
    expect(date.align).toBe("right");
    expect(date.y).toBe(item.y);
    expect(date.x).toBeGreaterThan(item.x + item.w - 5);
    expect(richText(date.body)).toBe("2025");
    expect(els.some((e) => e.name === "B.E. Computer Science dates")).toBe(false);
  });

  it("writes the heading in bold and the second part in italic, then the bullets", () => {
    const els = allElements(structuredToCanvas(resume(), measure)) as TextElement[];
    const item = els.find((e) => e.name === "Data Intern")!;
    const first = item.body!.content[0]!.content!;
    expect(first.map((n) => n.marks?.[0]?.type)).toEqual(["bold", undefined, "italic"]);
    expect(item.body!.content[1]!.type).toBe("bulletList");
  });

  it("adds a thin rule under each section title", () => {
    const els = allElements(structuredToCanvas(resume(), measure));
    expect(els.filter((e) => e.kind === "shape" && e.h < 1)).toHaveLength(2);
  });

  it("starts a new page instead of running past the bottom, up to the limit", () => {
    const many = resume({
      sections: [
        {
          id: "s",
          kind: "experience",
          title: "Experience",
          blocks: Array.from({ length: 30 }, (_, i) => ({
            id: `b${i}`, heading: `Role ${i}`, subheading: "Co", dates: "2024", location: "",
            body: { type: "doc" as const, content: [{ type: "paragraph", content: [{ type: "text", text: "Did a thing" }] }] },
          })),
        },
      ],
    });
    const doc = structuredToCanvas(many, measure);
    expect(doc.pages.length).toBeGreaterThan(1);
    expect(doc.pages.length).toBeLessThanOrEqual(3);
    const [, ph] = pageSize(doc.style);
    for (const page of doc.pages.slice(0, -1)) {
      for (const el of page.elements) expect(el.y + el.h).toBeLessThanOrEqual(ph - 16 + 1);
    }
  });

  it("keeps empty fields as boxes to click into, and skips empty items", () => {
    const empty = resume({
      header: { name: "", headline: "", contacts: [] },
      sections: [{ id: "s", kind: "custom", title: "", blocks: [{ id: "b", heading: "", subheading: "", dates: "", location: "", body: null }] }],
    });
    const els = allElements(structuredToCanvas(empty, measure)) as TextElement[];
    expect(els.map((e) => e.name)).toEqual(["Name", "Headline", "Contacts"]);
    expect(els.every((e) => e.body === null)).toBe(true);
  });

  it("follows the chosen spacing and margins", () => {
    const tight = resume();
    tight.style = { ...tight.style, spacing: "tight", margins: "narrow", size: "small", template: "compact" };
    const doc = structuredToCanvas(tight, measure);
    expect(doc.style.margin_mm).toBe(12);
    expect((allElements(doc)[0] as TextElement).x).toBe(12);
  });
});
