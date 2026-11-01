import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { analyzeAts } from "../ats";
import { contrastOnWhite, contrastRatio, FONT_PAIR_FAMILIES } from "../css";
import { LIMITS, allElements, pageSize } from "../types";
import type { CanvasDoc, TextElement } from "../types";
import { contactHref, fromCanvas, SAMPLE_CONTENT, toContacts } from "./content";
import type { TemplateContent } from "./content";
import { contactsDoc, layoutTemplate } from "./layout";
import { PALETTES, matchingPalette, paletteById } from "./palettes";
import { TEMPLATES, templateById } from "./specs";

/** A stand-in for the browser: every line of text is 5 mm, and a bullet list counts each item. */
const measure = (el: TextElement) => {
  const lines = (el.body?.content ?? []).reduce((n, node) => n + (node.type === "paragraph" ? 1 : (node.content?.length ?? 1)), 0);
  return Math.max(1, lines) * 5;
};

const FIXTURE = resolve(process.cwd(), "../../tests/fixtures/template_docs.json");

/** Ids are random, so the fixture uses their position instead. */
function normalised(doc: CanvasDoc): CanvasDoc {
  let n = 0;
  return {
    ...doc,
    pages: doc.pages.map((page, pi) => ({ id: `p${pi}`, elements: page.elements.map((el) => ({ ...el, id: `e${(n += 1)}` })) })),
  };
}

const SAFE = ["ledger", "modern-plain", "compact-page", "executive", "graduate", "technical", "editorial", "centered-classic", "bold-name", "right-aligned", "quiet-minimal", "heavy-rule", "classic-serif", "split-header", "timeline", "accent-edge"];

describe("the library", () => {
  it("has at least twenty templates with their own names and ids", () => {
    expect(TEMPLATES.length).toBeGreaterThanOrEqual(20);
    expect(new Set(TEMPLATES.map((t) => t.id)).size).toBe(TEMPLATES.length);
    expect(new Set(TEMPLATES.map((t) => t.name)).size).toBe(TEMPLATES.length);
    expect(templateById("ledger")?.name).toBe("Ledger");
    expect(templateById("nope")).toBeUndefined();
  });

  it("uses fonts and palettes that exist", () => {
    for (const t of TEMPLATES) {
      expect(FONT_PAIR_FAMILIES[t.fontPair], t.id).toBeDefined();
      expect(PALETTES.some((p) => p.id === t.palette), t.id).toBe(true);
    }
  });

  it("uses a good spread of fonts, colors and header layouts", () => {
    expect(new Set(TEMPLATES.map((t) => t.fontPair)).size).toBeGreaterThanOrEqual(8);
    expect(new Set(TEMPLATES.map((t) => t.palette)).size).toBeGreaterThanOrEqual(10);
    expect(new Set(TEMPLATES.map((t) => t.header.layout)).size).toBeGreaterThanOrEqual(5);
  });
});

describe("palettes", () => {
  it.each(PALETTES.map((p) => [p.name, p] as const))("%s is readable", (_name, p) => {
    expect(contrastOnWhite(p.accent)).toBeGreaterThanOrEqual(4.5);
    expect(contrastOnWhite(p.ink)).toBeGreaterThanOrEqual(4.5);
    expect(contrastOnWhite(p.muted)).toBeGreaterThanOrEqual(4.5);
    expect(contrastRatio(p.ink, p.tint)).toBeGreaterThanOrEqual(4.5);
    expect(contrastRatio(p.muted, p.tint)).toBeGreaterThanOrEqual(4.5);
    expect(contrastRatio(p.accent, p.tint)).toBeGreaterThanOrEqual(4.5);
  });

  it("finds a palette from a style and none when colors were mixed by hand", () => {
    const navy = paletteById("navy");
    expect(matchingPalette(navy)?.id).toBe("navy");
    expect(matchingPalette({ ...navy, accent: "#123456" })).toBeNull();
  });
});

describe("laying a template out", () => {
  it.each(TEMPLATES.map((t) => [t.id, t] as const))("%s fits the page, in the margins, within the limits", (_id, spec) => {
    const doc = layoutTemplate(SAMPLE_CONTENT, spec, measure);
    const [pw, ph] = pageSize(doc.style);
    expect(doc.version).toBe(2);
    expect(doc.style).toMatchObject({ template: spec.id, font_pair: spec.fontPair });
    expect(doc.pages.length).toBeLessThanOrEqual(LIMITS.maxPages);
    expect(allElements(doc).length).toBeLessThanOrEqual(LIMITS.maxElements);
    for (const el of allElements(doc)) {
      expect(el.x).toBeGreaterThanOrEqual(0);
      expect(el.x + el.w).toBeLessThanOrEqual(pw + 0.01);
      expect(el.y).toBeGreaterThanOrEqual(0);
      if (el.kind === "shape") expect(el.y + el.h).toBeLessThanOrEqual(ph + 0.01);
      if (el.kind === "text") expect(el.y + el.h, el.name).toBeLessThanOrEqual(ph - spec.margin + 0.6);
    }
  });

  it("calls exactly the one-column designs ATS-safe", () => {
    const safe = TEMPLATES.filter((t) => analyzeAts(layoutTemplate(SAMPLE_CONTENT, t, measure)).safe).map((t) => t.id);
    expect(safe.sort()).toEqual([...SAFE].sort());
  });

  it("keeps the words of the person in every template", () => {
    const text = (doc: CanvasDoc) =>
      allElements(doc)
        .filter((e): e is TextElement => e.kind === "text")
        .map((e) => JSON.stringify(e.body))
        .join(" ");
    for (const spec of TEMPLATES) {
      const out = text(layoutTemplate(SAMPLE_CONTENT, spec, measure));
      expect(out, spec.id).toContain("Asha Rao");
      expect(out, spec.id).toContain("Cut weekly reporting");
      expect(out, spec.id).toContain("Visvesvaraya");
    }
  });

  it("puts skills and education in the sidebar of a sidebar template and the story in the main column", () => {
    const left = layoutTemplate(SAMPLE_CONTENT, templateById("sidebar-left")!, measure);
    const side = allElements(left).filter((e) => e.kind === "text" && e.x < 64) as TextElement[];
    expect(side.some((e) => e.meta?.kind === "skills")).toBe(true);
    expect(side.some((e) => e.meta?.kind === "education")).toBe(true);
    expect(side.some((e) => e.meta?.kind === "experience")).toBe(false);
    const right = layoutTemplate(SAMPLE_CONTENT, templateById("sidebar-right")!, measure);
    const [pw] = pageSize(right.style);
    expect(allElements(right).some((e) => e.kind === "text" && e.meta?.kind === "skills" && e.x > pw - 64)).toBe(true);
  });

  it("puts the sidebar background first on every page so it sits under the text", () => {
    const doc = layoutTemplate(SAMPLE_CONTENT, templateById("dark-sidebar")!, measure);
    for (const page of doc.pages) {
      expect(page.elements[0]).toMatchObject({ kind: "shape", name: "Sidebar", fill: "accent" });
    }
    const text = allElements(doc).filter((e): e is TextElement => e.kind === "text" && e.x < 60);
    expect(text.length).toBeGreaterThan(0);
    expect(text.every((e) => e.color === "white")).toBe(true);
  });

  it("makes a banner header with white text on the accent color", () => {
    const doc = layoutTemplate(SAMPLE_CONTENT, templateById("banner")!, measure);
    const name = allElements(doc).find((e) => e.kind === "text" && e.meta?.role === "name") as TextElement;
    expect(name.color).toBe("white");
    expect(allElements(doc).find((e) => e.name === "Header band")).toMatchObject({ fill: "accent", x: 0, y: 0 });
  });

  it("links the email, phone and website in the contacts", () => {
    const doc = layoutTemplate(SAMPLE_CONTENT, templateById("ledger")!, measure);
    const contacts = allElements(doc).find((e) => e.kind === "text" && e.meta?.role === "contacts") as TextElement;
    const hrefs = (contacts.body?.content[0]?.content ?? []).flatMap((n) => n.marks ?? []).map((m) => m.attrs?.href);
    expect(hrefs).toEqual(["mailto:asha.rao@example.com", "tel:+919876543210", "https://linkedin.com/in/asharao"]);
  });

  it("starts a second page instead of running past the bottom, up to the limit", () => {
    const many: TemplateContent = {
      ...SAMPLE_CONTENT,
      sections: [
        {
          kind: "experience",
          title: "Experience",
          items: Array.from({ length: 40 }, (_, i) => ({
            label: `Role ${i}`,
            dates: "2024",
            body: { type: "doc" as const, content: [{ type: "paragraph", content: [{ type: "text", text: `Did thing ${i}` }] }] },
          })),
        },
      ],
    };
    for (const id of ["ledger", "sidebar-left", "timeline"]) {
      const doc = layoutTemplate(many, templateById(id)!, measure);
      expect(doc.pages.length, id).toBeGreaterThan(1);
      expect(doc.pages.length, id).toBeLessThanOrEqual(LIMITS.maxPages);
      const [, ph] = pageSize(doc.style);
      for (const el of allElements(doc)) expect(el.y, id).toBeLessThan(ph);
    }
  });

  it("keeps empty fields as boxes to click into", () => {
    const empty: TemplateContent = { name: "", headline: "", contacts: [], sections: [] };
    const els = allElements(layoutTemplate(empty, templateById("ledger")!, measure)) as TextElement[];
    expect(els.map((e) => e.name)).toEqual(["Name", "Headline", "Contacts"]);
    expect(els.every((e) => e.body === null)).toBe(true);
  });

  it("follows the options it is given", () => {
    const doc = layoutTemplate(SAMPLE_CONTENT, templateById("ledger")!, measure, { paper: "letter", fontPair: "inter", accent: "#222222", margin: 12, base: 9.5 });
    expect(doc.style).toMatchObject({ paper: "letter", font_pair: "inter", accent: "#222222", margin_mm: 12 });
    expect(allElements(doc)[0]!.x).toBe(12);
  });
});

describe("changing the template", () => {
  it.each(TEMPLATES.map((t) => [t.id, t] as const))("%s keeps every word it was given", (_id, spec) => {
    const doc = layoutTemplate(SAMPLE_CONTENT, spec, measure);
    const back = fromCanvas(doc);
    expect(back.labelled).toBe(true);
    expect(back.dropped).toBe(0);
    expect(back.content.name).toBe(SAMPLE_CONTENT.name);
    expect(back.content.headline).toBe(SAMPLE_CONTENT.headline);
    expect(back.content.contacts).toEqual(SAMPLE_CONTENT.contacts);
    const shape = (c: TemplateContent) =>
      c.sections.map((s) => ({ kind: s.kind, title: s.title, items: s.items.map((i) => ({ body: i.body, dates: i.dates })) }));
    expect(shape(back.content)).toEqual(shape(SAMPLE_CONTENT));
  });

  it("survives going through several templates in a row", () => {
    let content = SAMPLE_CONTENT;
    for (const id of ["banner", "sidebar-left", "timeline", "ledger", "dark-sidebar"]) {
      content = fromCanvas(layoutTemplate(content, templateById(id)!, measure)).content;
    }
    expect(content.sections[1]!.items[0]!.dates).toBe("2024 to now");
    expect(content.contacts[0]).toEqual({ text: "asha.rao@example.com", href: "mailto:asha.rao@example.com" });
  });

  it("counts the boxes the person added by hand, which are not carried over", () => {
    const doc = layoutTemplate(SAMPLE_CONTENT, templateById("ledger")!, measure);
    const extra: TextElement = { ...(allElements(doc).find((e) => e.kind === "text") as TextElement), id: "mine", name: "My note" };
    delete (extra as { meta?: unknown }).meta;
    doc.pages[0]!.elements.push(extra);
    expect(fromCanvas(doc).dropped).toBe(1);
  });

  it("says when a resume has no labels, as one made before templates would not", () => {
    const doc = layoutTemplate(SAMPLE_CONTENT, templateById("ledger")!, measure);
    for (const el of allElements(doc)) delete (el as { meta?: unknown }).meta;
    expect(fromCanvas(doc).labelled).toBe(false);
  });
});

describe("contact links", () => {
  it("links emails, phone numbers and websites and leaves plain places alone", () => {
    expect(contactHref("a@b.co")).toBe("mailto:a@b.co");
    expect(contactHref("+91 98765 43210")).toBe("tel:+919876543210");
    expect(contactHref("github.com/asha-rao")).toBe("https://github.com/asha-rao");
    expect(contactHref("https://example.com/me")).toBe("https://example.com/me");
    expect(contactHref("www.example.com")).toBe("https://www.example.com");
    expect(contactHref("Bengaluru, India")).toBeUndefined();
    expect(contactHref("Bengaluru")).toBeUndefined();
    expect(contactHref("12345")).toBeUndefined();
  });

  it("drops empty lines and writes them as a line or a stack", () => {
    const contacts = toContacts(["a@b.co", "  ", "Pune"]);
    expect(contacts).toEqual([{ text: "a@b.co", href: "mailto:a@b.co" }, { text: "Pune" }]);
    expect(contactsDoc(contacts, "stack")?.content).toHaveLength(2);
    expect(contactsDoc(contacts, "line")?.content).toHaveLength(1);
    expect(contactsDoc([], "line")).toBeNull();
  });
});

describe("what the server is sent", () => {
  const docs = TEMPLATES.map((t) => normalised(layoutTemplate(SAMPLE_CONTENT, t, measure)));

  it("matches the saved documents that the server's own tests validate", () => {
    if (process.env.WRITE_TEMPLATE_FIXTURES) {
      mkdirSync(dirname(FIXTURE), { recursive: true });
      writeFileSync(FIXTURE, JSON.stringify(docs) + "\n", "utf-8");
    }
    expect(JSON.parse(readFileSync(FIXTURE, "utf-8"))).toEqual(JSON.parse(JSON.stringify(docs)));
  });
});
