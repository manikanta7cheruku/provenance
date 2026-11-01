import type { ResumeBlock, ResumeContent, RichDoc, RichNode } from "../../../../lib/studio-api";
import { inlineDoc, plainRich, richText } from "../rich";
import { allElements } from "../types";
import type { CanvasDoc, ElementMeta, TextElement } from "../types";

/**
 * What a template lays out: the words of a resume with no positions. A guided resume converts into
 * this, and so does a canvas resume that a template made (each element carries a label saying what
 * it is), which is how a template can be changed without losing anything the person wrote.
 */

export interface Contact {
  text: string;
  href?: string;
}

export interface TemplateItem {
  label: string;
  body: RichDoc | null;
  dates: string;
}

export interface TemplateSection {
  kind: string;
  title: string;
  items: TemplateItem[];
}

export interface TemplateContent {
  name: string;
  headline: string;
  contacts: Contact[];
  sections: TemplateSection[];
}

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const SITE = /^(https?:\/\/)?(www\.)?[a-z0-9-]+(\.[a-z0-9-]+)+(\/\S*)?$/i;
const PHONE = /^\+?[\d\s().-]{8,}$/;

/** A link for a contact line, or nothing when it is just text such as a city. */
export function contactHref(text: string): string | undefined {
  const value = text.trim();
  if (EMAIL.test(value)) return `mailto:${value}`;
  if (PHONE.test(value) && (value.match(/\d/g)?.length ?? 0) >= 8) return `tel:${value.replace(/[^\d+]/g, "")}`;
  if (SITE.test(value) && !value.includes("@")) return /^https?:\/\//i.test(value) ? value : `https://${value}`;
  return undefined;
}

export function toContacts(lines: string[]): Contact[] {
  return lines
    .map((line) => line.trim())
    .filter(Boolean)
    .map((text) => {
      const href = contactHref(text);
      return href ? { text, href } : { text };
    });
}

export function blockBody(block: ResumeBlock): RichDoc | null {
  const nodes: RichNode[] = [];
  const parts: { text: string; marks?: ("bold" | "italic")[] }[] = [];
  if (block.heading) parts.push({ text: block.heading, marks: ["bold"] });
  if (block.subheading) {
    parts.push({ text: block.heading ? ", " : "" });
    parts.push({ text: block.subheading, marks: ["italic"] });
  }
  if (parts.length > 0) nodes.push(...inlineDoc(parts).content);
  if (block.location) nodes.push(...(plainRich(block.location)?.content ?? []));
  if (block.body) nodes.push(...block.body.content);
  return nodes.length > 0 ? { type: "doc", content: nodes } : null;
}

export function fromStructured(content: ResumeContent): TemplateContent {
  return {
    name: content.header.name,
    headline: content.header.headline,
    contacts: toContacts(content.header.contacts),
    sections: content.sections.map((section) => ({
      kind: section.kind,
      title: section.title,
      items: section.blocks
        .map((block) => ({ label: block.heading || block.subheading || "Item", body: blockBody(block), dates: block.dates }))
        .filter((item) => item.body !== null || item.dates !== ""),
    })),
  };
}

const SEPARATOR = /\s*\|\s*/;

/** The contacts of a contact box: every linked piece is one contact, plain text is split at bars. */
function readContacts(el: TextElement): Contact[] {
  const found: Contact[] = [];
  for (const paragraph of el.body?.content ?? []) {
    for (const node of paragraph.content ?? []) {
      if (node.type !== "text" || !node.text) continue;
      const href = node.marks?.find((m) => m.type === "link")?.attrs?.href;
      if (href) {
        found.push({ text: node.text.trim(), href });
        continue;
      }
      for (const piece of node.text.split(SEPARATOR)) if (piece.trim()) found.push({ text: piece.trim() });
    }
  }
  return found;
}

export interface Extracted {
  content: TemplateContent;
  /** Text boxes the person added by hand. They have no label and are not carried over. */
  dropped: number;
  /** False when the resume has no labels at all, such as one made before templates existed. */
  labelled: boolean;
}

/** Read the words back out of a canvas resume that a template laid out. */
export function fromCanvas(doc: CanvasDoc): Extracted {
  const texts = allElements(doc).filter((e): e is TextElement => e.kind === "text");
  const labelled = texts.some((e) => e.meta && e.meta.role !== "decor");
  const byRole = (role: ElementMeta["role"]) => texts.filter((e) => e.meta?.role === role);
  const first = (role: ElementMeta["role"]) => byRole(role)[0];
  const sections = new Map<number, TemplateSection>();
  const section = (sec: number, kind: string | null) => {
    let found = sections.get(sec);
    if (!found) {
      found = { kind: kind ?? "custom", title: "", items: [] };
      sections.set(sec, found);
    }
    if (kind && found.kind === "custom") found.kind = kind;
    return found;
  };
  for (const el of byRole("title")) {
    if (el.meta?.sec == null) continue;
    section(el.meta.sec, el.meta.kind).title = richText(el.body).split("\n")[0] ?? "";
  }
  const items = new Map<string, TemplateItem>();
  for (const el of byRole("item")) {
    if (el.meta?.sec == null || el.meta.idx == null) continue;
    const item: TemplateItem = { label: el.name, body: el.body, dates: "" };
    items.set(`${el.meta.sec}:${el.meta.idx}`, item);
    section(el.meta.sec, el.meta.kind).items[el.meta.idx] = item;
  }
  for (const el of byRole("dates")) {
    if (el.meta?.sec == null || el.meta.idx == null) continue;
    const text = richText(el.body).trim();
    const item = items.get(`${el.meta.sec}:${el.meta.idx}`);
    if (item) item.dates = text;
    else section(el.meta.sec, el.meta.kind).items[el.meta.idx] = { label: el.name, body: null, dates: text };
  }
  const ordered = [...sections.entries()].sort((a, b) => a[0] - b[0]).map(([, s]) => ({ ...s, items: s.items.filter(Boolean) }));
  const contactsEl = first("contacts");
  return {
    labelled,
    dropped: texts.filter((e) => !e.meta && e.body && e.body.content.length > 0).length,
    content: {
      name: first("name") ? richText(first("name")!.body).split("\n")[0]! : "",
      headline: first("headline") ? richText(first("headline")!.body).split("\n")[0]! : "",
      contacts: contactsEl ? readContacts(contactsEl) : [],
      sections: ordered,
    },
  };
}

function para(text: string): RichNode {
  return { type: "paragraph", content: [{ type: "text", text }] };
}

function bullets(lines: string[]): RichNode {
  return {
    type: "bulletList",
    content: lines.map((l) => ({ type: "listItem", content: [para(l)] })),
  };
}

function item(label: string, sub: string, dates: string, lines: string[]): TemplateItem {
  const head = inlineDoc([{ text: label, marks: ["bold"] }, { text: sub ? `, ${sub}` : "", marks: ["italic"] }]);
  return { label, dates, body: { type: "doc", content: [...head.content, ...(lines.length ? [bullets(lines)] : [])] } };
}

/** Made-up words for previews when the person has nothing written yet. */
export const SAMPLE_CONTENT: TemplateContent = {
  name: "Asha Rao",
  headline: "Data analyst",
  contacts: toContacts(["asha.rao@example.com", "+91 98765 43210", "Bengaluru, India", "linkedin.com/in/asharao"]),
  sections: [
    { kind: "summary", title: "Summary", items: [{ label: "Summary", dates: "", body: { type: "doc", content: [para("Analyst who turns messy operational data into clear weekly decisions.")] } }] },
    {
      kind: "experience",
      title: "Experience",
      items: [
        item("Data Analyst", "Kestrel Logistics", "2024 to now", ["Cut weekly reporting from two days to two hours with SQL and Python.", "Built a dashboard that six teams use to track late deliveries."]),
        item("Analytics Intern", "Northwind Retail", "2023", ["Cleaned six sales sources and found a 4% double count."]),
      ],
    },
    {
      kind: "projects",
      title: "Projects",
      items: [item("Route planner", "personal project", "2025", ["Compared three routing methods on real delivery data."])],
    },
    { kind: "education", title: "Education", items: [item("B.E. Computer Science", "Visvesvaraya Technological University", "2020 to 2024", [])] },
    { kind: "skills", title: "Skills", items: [{ label: "Skills", dates: "", body: { type: "doc", content: [para("SQL, Python, pandas, Tableau, statistics, communication")] } }] },
  ],
};

export function isEmptyContent(content: TemplateContent): boolean {
  return !content.name && !content.headline && content.contacts.length === 0 && content.sections.every((s) => s.items.length === 0 && !s.title);
}
