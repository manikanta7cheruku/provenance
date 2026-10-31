import type { ResumeBlock, ResumeContent, ResumeSection, ResumeStyle, RichDoc } from "../../lib/studio-api";

/** Pure edits of a resume document. Each returns a new document and never changes its input. */

let counter = 0;
export function newId(): string {
  counter += 1;
  return `n${Date.now().toString(36)}${counter.toString(36)}${Math.random().toString(36).slice(2, 6)}`;
}

export const SECTION_TITLES: Record<string, string> = {
  summary: "Summary",
  experience: "Experience",
  education: "Education",
  projects: "Projects",
  skills: "Skills",
  certifications: "Certifications",
  achievements: "Achievements",
  custom: "Section",
};

export const blankBlock = (): ResumeBlock => ({
  id: newId(),
  heading: "",
  subheading: "",
  dates: "",
  location: "",
  body: null,
});

export function addSection(doc: ResumeContent, kind: string): ResumeContent {
  const section: ResumeSection = {
    id: newId(),
    kind,
    title: SECTION_TITLES[kind] ?? "Section",
    blocks: [blankBlock()],
  };
  return { ...doc, sections: [...doc.sections, section] };
}

function move<T>(items: T[], index: number, by: -1 | 1): T[] {
  const target = index + by;
  if (index < 0 || index >= items.length || target < 0 || target >= items.length) return items;
  const copy = [...items];
  const [item] = copy.splice(index, 1);
  copy.splice(target, 0, item as T);
  return copy;
}

export function moveSection(doc: ResumeContent, index: number, by: -1 | 1): ResumeContent {
  return { ...doc, sections: move(doc.sections, index, by) };
}

export function removeSection(doc: ResumeContent, index: number): ResumeContent {
  return { ...doc, sections: doc.sections.filter((_, i) => i !== index) };
}

export function updateSection(doc: ResumeContent, index: number, patch: Partial<ResumeSection>): ResumeContent {
  return { ...doc, sections: doc.sections.map((s, i) => (i === index ? { ...s, ...patch } : s)) };
}

function withBlocks(doc: ResumeContent, si: number, edit: (blocks: ResumeBlock[]) => ResumeBlock[]): ResumeContent {
  return updateSection(doc, si, { blocks: edit(doc.sections[si]?.blocks ?? []) });
}

export function addBlock(doc: ResumeContent, si: number): ResumeContent {
  return withBlocks(doc, si, (blocks) => [...blocks, blankBlock()]);
}

export function moveBlock(doc: ResumeContent, si: number, bi: number, by: -1 | 1): ResumeContent {
  return withBlocks(doc, si, (blocks) => move(blocks, bi, by));
}

export function removeBlock(doc: ResumeContent, si: number, bi: number): ResumeContent {
  return withBlocks(doc, si, (blocks) => blocks.filter((_, i) => i !== bi));
}

export function updateBlock(
  doc: ResumeContent,
  si: number,
  bi: number,
  patch: Partial<Omit<ResumeBlock, "id">>,
): ResumeContent {
  return withBlocks(doc, si, (blocks) => blocks.map((b, i) => (i === bi ? { ...b, ...patch } : b)));
}

export function setHeader(doc: ResumeContent, patch: Partial<ResumeContent["header"]>): ResumeContent {
  return { ...doc, header: { ...doc.header, ...patch } };
}

export function setStyle(doc: ResumeContent, patch: Partial<ResumeStyle>): ResumeContent {
  return { ...doc, style: { ...doc.style, ...patch } };
}

export function isEmptyRich(body: RichDoc | null): boolean {
  return !body || body.content.length === 0;
}

/** True when two documents are the same, so autosave does not fire for a no-op. */
export function sameDocument(a: ResumeContent, b: ResumeContent): boolean {
  return JSON.stringify(a) === JSON.stringify(b);
}
