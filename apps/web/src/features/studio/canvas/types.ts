import type { RichDoc } from "../../../lib/studio-api";

/** Version 2 of the resume document: pages of boxes positioned in millimetres. */
export type Align = "left" | "center" | "right" | "justify";
export type FontRole = "heading" | "body";

export interface CanvasStyle {
  template: string;
  font_pair: string;
  accent: string;
  paper: string;
  margin_mm: number;
}

interface ElementBase {
  id: string;
  name: string;
  x: number;
  y: number;
  w: number;
  h: number;
  locked: boolean;
  group: string | null;
}

export interface TextElement extends ElementBase {
  kind: "text";
  body: RichDoc | null;
  font: FontRole;
  size: number;
  color: string;
  align: Align;
  line_height: number;
  caps: boolean;
}

export interface ShapeElement extends ElementBase {
  kind: "shape";
  fill: string;
  stroke: string;
  stroke_pt: number;
  radius: number;
}

export type CanvasElement = TextElement | ShapeElement;

export interface CanvasPage {
  id: string;
  elements: CanvasElement[];
}

export interface CanvasDoc {
  version: 2;
  style: CanvasStyle;
  pages: CanvasPage[];
}

export const PAGE_MM: Record<string, readonly [number, number]> = {
  a4: [210, 297],
  letter: [215.9, 279.4],
};

export const LIMITS = {
  maxPages: 3,
  maxElements: 150,
  minSizeMm: 0.2,
  sizePt: [5, 72] as const,
  lineHeight: [0.9, 2.5] as const,
  maxName: 60,
};

export const INK = "#1b1b1b";
export const MUTED = "#4a4a4a";

export const COLOR_CHOICES = [
  { value: "ink", label: "Ink" },
  { value: "muted", label: "Grey" },
  { value: "accent", label: "Accent" },
  { value: "white", label: "White" },
] as const;

export function pageSize(style: CanvasStyle): readonly [number, number] {
  return PAGE_MM[style.paper] ?? [210, 297];
}

export function isCanvas(content: unknown): content is CanvasDoc {
  return typeof content === "object" && content !== null && (content as { version?: unknown }).version === 2;
}

export function allElements(doc: CanvasDoc): CanvasElement[] {
  return doc.pages.flatMap((p) => p.elements);
}

export function findElement(doc: CanvasDoc, id: string): { element: CanvasElement; page: number } | null {
  for (let page = 0; page < doc.pages.length; page += 1) {
    const element = doc.pages[page]?.elements.find((e) => e.id === id);
    if (element) return { element, page };
  }
  return null;
}
