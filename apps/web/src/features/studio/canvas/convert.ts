import type { ResumeBlock, ResumeContent, RichDoc, RichNode } from "../../../lib/studio-api";
import { newId } from "../doc-ops";
import { inlineDoc, plainRich } from "./rich";
import { LIMITS, pageSize } from "./types";
import type { CanvasDoc, CanvasElement, CanvasPage, CanvasStyle, ShapeElement, TextElement } from "./types";

/** How tall a text element is once its text is laid out at its width, in millimetres. */
export type Measure = (el: TextElement, style: CanvasStyle) => number;

const MARGIN_MM = { narrow: 12, normal: 16, wide: 22 } as const;
const BASE_PT = { small: 9.5, medium: 10.5, large: 11.5 } as const;
const BLOCK_GAP = { tight: 1.8, normal: 3, relaxed: 4.6 } as const;
const SECTION_GAP = { tight: 3.8, normal: 5.5, relaxed: 7.5 } as const;
const DATES_WIDTH_MM = 38;

function textEl(partial: Partial<TextElement> & Pick<TextElement, "name" | "x" | "y" | "w">): TextElement {
  return {
    id: newId(),
    kind: "text",
    h: 5,
    locked: false,
    group: null,
    body: null,
    font: "body",
    size: 10.5,
    color: "ink",
    align: "left",
    line_height: 1.3,
    caps: false,
    ...partial,
  };
}

function ruleEl(name: string, x: number, y: number, w: number, thickness: number): ShapeElement {
  return {
    id: newId(),
    kind: "shape",
    name,
    x,
    y,
    w,
    h: thickness,
    locked: false,
    group: null,
    fill: "accent",
    stroke: "none",
    stroke_pt: 0,
    radius: 0,
  };
}

function blockBody(block: ResumeBlock): RichDoc | null {
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

/**
 * Lay a flowing resume out on canvas pages, top to bottom, as a starting point the person can then
 * move around. Each box is as tall as its text, so nothing overlaps. `measure` asks the browser how
 * tall the text is, so it is passed in and the layout itself stays a plain function.
 */
export function structuredToCanvas(content: ResumeContent, measure: Measure): CanvasDoc {
  const s = content.style;
  const margin = MARGIN_MM[s.margins as keyof typeof MARGIN_MM] ?? 16;
  const base = BASE_PT[s.size as keyof typeof BASE_PT] ?? 10.5;
  const blockGap = BLOCK_GAP[s.spacing as keyof typeof BLOCK_GAP] ?? 3;
  const sectionGap = SECTION_GAP[s.spacing as keyof typeof SECTION_GAP] ?? 5.5;
  const style: CanvasStyle = {
    template: s.template,
    font_pair: s.font_pair,
    accent: s.accent,
    paper: s.paper,
    margin_mm: margin,
  };
  const [pw, ph] = pageSize(style);
  const width = pw - 2 * margin;
  const bottom = ph - margin;

  const pages: CanvasElement[][] = [[]];
  let y = margin;
  const place = (els: CanvasElement[], height: number) => {
    // A unit that does not fit starts the next page, unless it is the first thing on this one.
    const onPage = pages[pages.length - 1]!;
    if (y + height > bottom && onPage.length > 0 && pages.length < LIMITS.maxPages) {
      pages.push([]);
      y = margin;
    }
    const shift = y;
    pages[pages.length - 1]!.push(...els.map((el) => ({ ...el, y: Math.round((shift + (el.y - els[0]!.y)) * 10) / 10 })));
    y += height;
  };

  const measured = (el: TextElement): TextElement => ({ ...el, h: Math.max(Math.round(measure(el, style) * 10) / 10, 1) });

  const nameSize = Math.round(base * (s.template === "compact" ? 2 : 2.4) * 10) / 10;
  const name = measured(
    textEl({ name: "Name", x: margin, y: 0, w: width, font: "heading", size: nameSize, color: "accent", line_height: 1.1, body: content.header.name ? inlineDoc([{ text: content.header.name }]) : null }),
  );
  place([name], name.h + 1);
  const headline = measured(
    textEl({ name: "Headline", x: margin, y: 0, w: width, size: Math.round(base * 1.1 * 10) / 10, body: plainRich(content.header.headline) }),
  );
  place([headline], headline.h + 1.2);
  const contacts = measured(
    textEl({ name: "Contacts", x: margin, y: 0, w: width, size: Math.round(base * 0.95 * 10) / 10, color: "muted", body: plainRich(content.header.contacts.filter(Boolean).join("   |   ")) }),
  );
  place([contacts], contacts.h);

  for (const section of content.sections) {
    y += sectionGap;
    if (section.title) {
      const title = measured(
        textEl({ name: `${section.title} heading`, x: margin, y: 0, w: width, font: "heading", size: Math.round(base * 1.05 * 10) / 10, color: "accent", caps: true, body: inlineDoc([{ text: section.title }]) }),
      );
      const rule = ruleEl(`${section.title} rule`, margin, title.h + 0.8, width, 0.35);
      place([title, rule], title.h + 0.8 + 0.35 + blockGap);
    }
    for (const block of section.blocks) {
      const body = blockBody(block);
      if (!body && !block.dates) continue;
      const withDates = block.dates !== "";
      const left = measured(
        textEl({ name: block.heading || block.subheading || "Item", x: margin, y: 0, w: withDates ? width - DATES_WIDTH_MM : width, size: base, body }),
      );
      const els: CanvasElement[] = [left];
      if (withDates) {
        els.push(
          measured(textEl({ name: `${block.heading || "Item"} dates`, x: margin + width - DATES_WIDTH_MM + 2, y: 0, w: DATES_WIDTH_MM - 2, align: "right", size: Math.round(base * 0.95 * 10) / 10, color: "muted", body: plainRich(block.dates) })),
        );
      }
      place(els, left.h + blockGap);
    }
  }

  const doc: CanvasDoc = {
    version: 2,
    style,
    pages: pages.map((elements): CanvasPage => ({ id: newId(), elements })),
  };
  return doc;
}
