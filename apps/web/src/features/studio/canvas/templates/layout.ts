import { newId } from "../../doc-ops";
import type { Measure } from "../convert";
import { inlineDoc, plainRich } from "../rich";
import { LIMITS, pageSize } from "../types";
import type { CanvasDoc, CanvasElement, CanvasPage, CanvasStyle, ElementMeta, Role, ShapeElement, TextElement } from "../types";
import type { Contact, TemplateContent, TemplateItem, TemplateSection } from "./content";
import { paletteById } from "./palettes";
import type { Palette } from "./palettes";
import type { TemplateSpec } from "./specs";

/** Colors and sizes that can replace a template's own, such as when a guided resume is moved over. */
export interface LayoutOptions {
  paper?: string;
  fontPair?: string;
  accent?: string;
  /** All four colors, such as the ones the person already has. Wins over the template palette. */
  colors?: Pick<Palette, "accent" | "ink" | "muted" | "tint">;
  margin?: number;
  base?: number;
  blockGap?: number;
  sectionGap?: number;
}

const DATES_WIDTH_MM = 38;
const DATES_LEFT_MM = 26;
const NARROW_COLUMN_MM = 90;
const SIDE_PADDING_MM = 7;
const SIDE_GAP_MM = 9;
const r1 = (n: number) => Math.round(n * 10) / 10;

interface Column {
  x: number;
  w: number;
  page: number;
  y: number;
  filled: Set<number>;
  dark: boolean;
}

const label = (text: string) => text.slice(0, 60);
const note = (role: Role, sec: number | null = null, idx: number | null = null, kind: string | null = null): ElementMeta => ({ role, sec, idx, kind });

function textBox(partial: Partial<TextElement> & Pick<TextElement, "name" | "x" | "y" | "w">): TextElement {
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
    name: label(partial.name),
  };
}

function box(name: string, x: number, y: number, w: number, h: number, fill: string): ShapeElement {
  return { id: newId(), kind: "shape", name, x, y, w, h, locked: false, group: null, fill, stroke: "none", stroke_pt: 0, radius: 0, meta: note("decor") };
}

/** The contact lines as rich text: each contact with a web, mail or phone address becomes a link. */
export function contactsDoc(contacts: Contact[], mode: "line" | "stack"): TextElement["body"] {
  if (contacts.length === 0) return null;
  const node = (c: Contact) => ({ type: "text", text: c.text, ...(c.href ? { marks: [{ type: "link" as const, attrs: { href: c.href } }] } : {}) });
  if (mode === "stack") return { type: "doc", content: contacts.map((c) => ({ type: "paragraph", content: [node(c)] })) };
  const content: ReturnType<typeof node>[] = [];
  contacts.forEach((c, i) => {
    if (i > 0) content.push({ type: "text", text: "   |   " });
    content.push(node(c));
  });
  return { type: "doc", content: [{ type: "paragraph", content }] };
}

/**
 * Lay a resume's words out on canvas pages with a template: header, section titles, items and dates
 * placed top to bottom (or in two columns), each box as tall as its text so nothing overlaps.
 * `measure` asks the browser how tall a text box is, so the layout itself stays a plain function.
 */
export function layoutTemplate(content: TemplateContent, spec: TemplateSpec, measure: Measure, options: LayoutOptions = {}): CanvasDoc {
  const palette = options.colors ?? paletteById(spec.palette);
  const margin = options.margin ?? spec.margin;
  const base = options.base ?? spec.base;
  const blockGap = options.blockGap ?? spec.blockGap;
  const sectionGap = options.sectionGap ?? spec.sectionGap;
  const style: CanvasStyle = {
    template: spec.id,
    font_pair: options.fontPair ?? spec.fontPair,
    accent: options.accent ?? palette.accent,
    ink: palette.ink,
    muted: palette.muted,
    tint: palette.tint,
    paper: options.paper ?? "a4",
    margin_mm: margin,
  };
  const [pw, ph] = pageSize(style);
  const bottom = ph - margin;
  const sb = spec.sidebar;
  const h = spec.header;

  const column = (x: number, w: number, dark: boolean): Column => ({ x, w, page: 0, y: margin, filled: new Set(), dark });
  let main: Column;
  let side: Column | null = null;
  if (sb && sb.side === "left") {
    side = column(SIDE_PADDING_MM, sb.width - 2 * SIDE_PADDING_MM, sb.fill === "accent");
    main = column(sb.width + SIDE_GAP_MM, pw - sb.width - SIDE_GAP_MM - margin, false);
  } else if (sb) {
    main = column(margin, pw - sb.width - SIDE_GAP_MM - margin, false);
    side = column(pw - sb.width + SIDE_PADDING_MM, sb.width - 2 * SIDE_PADDING_MM, sb.fill === "accent");
  } else {
    main = column(margin, pw - 2 * margin, false);
  }

  const pages: CanvasElement[][] = [[]];
  const measured = <T extends TextElement>(el: T): T => ({ ...el, h: Math.max(r1(measure(el, style)), 1) });

  /** Put one unit (boxes whose y is relative to the unit's top) in a column, on a new page if it does not fit. */
  const place = (col: Column, els: CanvasElement[], height: number, reserve = 0) => {
    if (col.y + height + reserve > bottom && col.filled.has(col.page) && col.page + 1 < LIMITS.maxPages) {
      col.page += 1;
      col.y = margin;
    }
    while (pages.length <= col.page) pages.push([]);
    const target = pages[col.page]!;
    for (const el of els) target.push({ ...el, y: r1(Math.min(col.y + el.y, ph - Math.min(el.h, 10))) });
    col.filled.add(col.page);
    col.y += height;
  };

  const inkOn = (col: Column) => (col.dark ? "white" : "ink");
  const mutedOn = (col: Column) => (col.dark ? "white" : "muted");

  // ---- header
  const contactsBox = (col: Column, w: number, x: number, y: number, mode: "line" | "stack", align: TextElement["align"], color: string): TextElement =>
    measured(textBox({ name: "Contacts", x, y, w, size: r1(base * 0.95), color, align, line_height: spec.lineHeight, body: contactsDoc(content.contacts, mode), meta: note("contacts") }));

  const nameBox = (x: number, y: number, w: number, align: TextElement["align"], color: string): TextElement =>
    measured(
      textBox({
        name: "Name",
        x,
        y,
        w,
        font: "heading",
        size: r1(base * h.nameScale),
        color,
        line_height: 1.1,
        align,
        caps: h.nameCaps,
        body: content.name ? inlineDoc([{ text: content.name }]) : null,
        meta: note("name"),
      }),
    );

  const headlineBox = (x: number, y: number, w: number, align: TextElement["align"], color: string): TextElement =>
    measured(textBox({ name: "Headline", x, y, w, size: r1(base * 1.1), color, align, line_height: spec.lineHeight, body: plainRich(content.headline), meta: note("headline") }));

  const sideContacts = !!sb?.contacts && !!side;
  const alignOf: TextElement["align"] = h.layout === "center" ? "center" : h.layout === "right" ? "right" : "left";

  if (h.layout === "band") {
    const inner = pw - 2 * margin;
    const padTop = r1(margin * 0.7);
    const name = nameBox(margin, padTop, inner, "left", "white");
    const headline = headlineBox(margin, r1(padTop + name.h + 1), inner, "left", "white");
    const contacts = contactsBox(main, inner, margin, r1(headline.y + headline.h + 1.2), h.contacts, "left", "white");
    const bandH = r1(contacts.y + contacts.h + margin * 0.5);
    pages[0]!.push(box("Header band", 0, 0, pw, bandH, "accent"), name, headline, contacts);
    main.y = r1(bandH + 6);
    main.filled.add(0);
    if (side) {
      side.y = main.y;
      side.filled.add(0);
    }
  } else if (h.layout === "panel") {
    const pad = 4;
    const top = main.y;
    const name = nameBox(main.x, 0, main.w, "left", h.nameColor);
    const headline = headlineBox(main.x, name.h + 1, main.w, "left", h.headlineColor);
    const contacts = contactsBox(main, main.w, main.x, name.h + headline.h + 2.2, h.contacts, "left", "muted");
    const inside = r1(name.h + headline.h + 2.2 + contacts.h);
    place(main, [box("Header panel", main.x - pad, -pad, main.w + 2 * pad, inside + 2 * pad, "tint"), name, headline, contacts], inside + 2 * pad + 2);
    main.y = Math.max(main.y, top + inside + pad + 6);
  } else if (h.layout === "split") {
    const leftW = r1(main.w * 0.6);
    const name = nameBox(main.x, 0, leftW, "left", h.nameColor);
    const headline = headlineBox(main.x, name.h + 1, leftW, "left", h.headlineColor);
    const contacts = contactsBox(main, r1(main.w * 0.38), r1(main.x + main.w * 0.62), 0, "stack", "right", "muted");
    place(main, [name, headline, contacts], Math.max(name.h + 1 + headline.h, contacts.h) + 1);
  } else {
    const name = nameBox(main.x, 0, main.w, alignOf, h.nameColor);
    place(main, [name], name.h + 1);
    const headline = headlineBox(main.x, 0, main.w, alignOf, h.headlineColor);
    place(main, [headline], headline.h + 1.2);
    if (!sideContacts) {
      const contacts = contactsBox(main, main.w, main.x, 0, h.contacts, alignOf, "muted");
      place(main, [contacts], contacts.h);
    }
  }
  if (h.rule > 0 && h.layout !== "band" && h.layout !== "panel") {
    main.y += 2;
    place(main, [box("Header rule", main.x, 0, main.w, h.rule, "accent")], h.rule + 1);
  }

  if (sideContacts && side) {
    const title = measured(
      textBox({ name: "Contact heading", x: side.x, y: 0, w: side.w, font: "heading", size: r1(base * spec.titles.scale), color: side.dark ? "white" : "accent", caps: true, body: inlineDoc([{ text: "Contact" }]), meta: note("decor") }),
    );
    const contacts = contactsBox(side, side.w, side.x, title.h + 1.2, "stack", "left", side.dark ? "white" : "ink");
    place(side, [title, contacts], title.h + 1.2 + contacts.h + blockGap);
  }

  // ---- sections
  const titleUnit = (col: Column, section: TemplateSection, si: number): { els: CanvasElement[]; height: number } => {
    const t = spec.titles;
    const color = col.dark ? "white" : t.color;
    const rule = col.dark ? "white" : t.color === "ink" ? "ink" : t.color === "muted" ? "muted" : "accent";
    const bold = t.style === "plain" || t.style === "bar" || t.style === "box";
    const make = (x: number, y: number, w: number) =>
      measured(
        textBox({
          name: `${section.title} heading`,
          x,
          y,
          w,
          font: "heading",
          size: r1(base * t.scale),
          color,
          caps: t.caps,
          align: t.center ? "center" : "left",
          line_height: 1.2,
          body: inlineDoc([{ text: section.title, marks: bold ? ["bold"] : [] }]),
          meta: note("title", si, null, section.kind),
        }),
      );
    switch (t.style) {
      case "plain": {
        const title = make(col.x, 0, col.w);
        return { els: [title], height: title.h + blockGap * 0.7 };
      }
      case "short": {
        const title = make(col.x, 0, col.w);
        const x = t.center ? col.x + (col.w - 14) / 2 : col.x;
        return { els: [title, box(`${section.title} rule`, r1(x), r1(title.h + 0.8), 14, 0.9, rule)], height: title.h + 0.8 + 0.9 + blockGap };
      }
      case "bar": {
        const title = make(col.x + 3.6, 0, col.w - 3.6);
        return { els: [title, box(`${section.title} bar`, col.x, 0, 1.2, title.h, rule)], height: title.h + blockGap };
      }
      case "box": {
        const title = make(col.x + 2.5, 1.5, col.w - 5);
        return { els: [box(`${section.title} panel`, col.x, 0, col.w, r1(title.h + 3), col.dark ? "white" : "tint"), title], height: title.h + 3 + blockGap };
      }
      case "overline": {
        const title = make(col.x, 1.6, col.w);
        return { els: [box(`${section.title} rule`, col.x, 0, col.w, 0.35, rule), title], height: 1.6 + title.h + blockGap * 0.8 };
      }
      default: {
        const title = make(col.x, 0, col.w);
        return { els: [title, box(`${section.title} rule`, col.x, r1(title.h + 0.8), col.w, 0.35, rule)], height: title.h + 0.8 + 0.35 + blockGap };
      }
    }
  };

  const itemUnit = (col: Column, section: TemplateSection, si: number, item: TemplateItem, ii: number): { els: CanvasElement[]; height: number } => {
    const hasDates = item.dates !== "";
    const mode = col.w < NARROW_COLUMN_MM ? "below" : spec.dates;
    const datesSize = r1(base * 0.95);
    const itemMeta = note("item", si, ii, section.kind);
    const datesMeta = note("dates", si, ii, section.kind);
    const datesBox = (x: number, y: number, w: number, align: TextElement["align"]) =>
      measured(textBox({ name: `${item.label} dates`, x, y, w, size: datesSize, color: mutedOn(col), align, line_height: spec.lineHeight, body: plainRich(item.dates), meta: datesMeta }));
    const bodyBox = (x: number, w: number) =>
      measured(textBox({ name: item.label, x, y: 0, w, size: base, color: inkOn(col), line_height: spec.lineHeight, body: item.body, meta: itemMeta }));
    if (hasDates && mode === "right") {
      const left = bodyBox(col.x, col.w - DATES_WIDTH_MM);
      return { els: [left, datesBox(col.x + col.w - DATES_WIDTH_MM + 2, 0, DATES_WIDTH_MM - 2, "right")], height: left.h + blockGap };
    }
    if (hasDates && mode === "left") {
      const left = bodyBox(col.x + DATES_LEFT_MM + 4, col.w - DATES_LEFT_MM - 4);
      return { els: [left, datesBox(col.x, 0, DATES_LEFT_MM, "left")], height: left.h + blockGap };
    }
    const left = bodyBox(col.x, col.w);
    if (hasDates) {
      const dates = datesBox(col.x, left.h + 0.3, col.w, "left");
      return { els: [left, dates], height: left.h + 0.3 + dates.h + blockGap };
    }
    return { els: [left], height: left.h + blockGap };
  };

  content.sections.forEach((section, si) => {
    if (!section.title && section.items.length === 0) return;
    const col = side && sb?.kinds.includes(section.kind) ? side : main;
    if (col.filled.size > 0) col.y += sectionGap;
    const first = section.items[0] ? itemUnit(col, section, si, section.items[0], 0) : null;
    if (section.title) {
      const title = titleUnit(col, section, si);
      place(col, title.els, title.height, Math.min(first?.height ?? 0, 24));
    }
    section.items.forEach((item, ii) => {
      const unit = ii === 0 && first ? first : itemUnit(col, section, si, item, ii);
      place(col, unit.els, unit.height);
    });
  });

  // ---- backgrounds, drawn first so they sit under the text
  if (sb && side) {
    const x = sb.side === "left" ? 0 : pw - sb.width;
    pages.forEach((page) => page.unshift(box("Sidebar", x, 0, sb.width, ph, sb.fill)));
  }
  if (spec.edge) pages.forEach((page) => page.unshift(box("Edge bar", 0, 0, 4, ph, "accent")));

  return { version: 2, style, pages: pages.map((elements): CanvasPage => ({ id: newId(), elements })) };
}
