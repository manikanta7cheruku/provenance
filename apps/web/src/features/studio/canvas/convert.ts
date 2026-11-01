import type { ResumeContent } from "../../../lib/studio-api";
import type { CanvasDoc, TextElement, CanvasStyle } from "./types";
import { fromStructured } from "./templates/content";
import { layoutTemplate } from "./templates/layout";
import { templateById } from "./templates/specs";

/** How tall a text element is once its text is laid out at its width, in millimetres. */
export type Measure = (el: TextElement, style: CanvasStyle) => number;

const MARGIN_MM = { narrow: 12, normal: 16, wide: 22 } as const;
const BASE_PT = { small: 9.5, medium: 10.5, large: 11.5 } as const;
const BLOCK_GAP = { tight: 1.8, normal: 3, relaxed: 4.6 } as const;
const SECTION_GAP = { tight: 3.8, normal: 5.5, relaxed: 7.5 } as const;
const GUIDED_TEMPLATE: Record<string, string> = { classic: "ledger", modern: "modern-plain", compact: "compact-page" };

/**
 * Lay a guided resume out on canvas pages, top to bottom, as a starting point the person can then
 * move around. It keeps the guided resume's own fonts, size, spacing, margins and accent color, and
 * uses the template that matches its look. `measure` asks the browser how tall the text is.
 */
export function structuredToCanvas(content: ResumeContent, measure: Measure): CanvasDoc {
  const s = content.style;
  const spec = templateById(GUIDED_TEMPLATE[s.template] ?? "ledger")!;
  return layoutTemplate(fromStructured(content), spec, measure, {
    paper: s.paper,
    fontPair: s.font_pair,
    accent: s.accent,
    margin: MARGIN_MM[s.margins as keyof typeof MARGIN_MM] ?? 16,
    base: BASE_PT[s.size as keyof typeof BASE_PT] ?? 10.5,
    blockGap: BLOCK_GAP[s.spacing as keyof typeof BLOCK_GAP] ?? 3,
    sectionGap: SECTION_GAP[s.spacing as keyof typeof SECTION_GAP] ?? 5.5,
  });
}
