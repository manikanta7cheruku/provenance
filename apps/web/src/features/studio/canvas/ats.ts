import { contrastOnWhite, resolveColor } from "./css";
import { overlapArea } from "./geometry";
import type { Box } from "./geometry";
import { pageSize } from "./types";
import type { CanvasDoc, CanvasElement, TextElement } from "./types";

/**
 * A plain-words check of how well applicant tracking systems will read this layout. It is advice
 * shown to the person, with the reason, and it never blocks saving or exporting. It looks at what
 * makes parsers lose order or skip text: columns, text over text, text on a filled shape.
 */

export type AtsIssueKind = "columns" | "overlap" | "on_shape" | "small_text" | "edge" | "contrast";

export interface AtsIssue {
  kind: AtsIssueKind;
  /** True when this can make a system misread or skip the text. Otherwise it is a note. */
  blocks: boolean;
  message: string;
  ids: string[];
}

export interface AtsReport {
  safe: boolean;
  issues: AtsIssue[];
}

const COLUMN_MIN_WIDTH_MM = 50;
const COLUMN_MIN_HEIGHT_MM = 12;
const OVERLAP_SHARE = 0.25;
const SMALL_TEXT_PT = 8;
const EDGE_MM = 5;
const MIN_CONTRAST = 4.5;
const SHAPE_MIN_HEIGHT_MM = 2;

const hasText = (el: CanvasElement): el is TextElement =>
  el.kind === "text" && !!el.body && el.body.content.length > 0;

const boxOf = (el: CanvasElement): Box => ({ x: el.x, y: el.y, w: el.w, h: el.h });

function verticalShare(a: Box, b: Box): number {
  const overlap = Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y);
  return overlap > 0 ? overlap / Math.min(a.h, b.h) : 0;
}

export function analyzeAts(doc: CanvasDoc): AtsReport {
  const issues: AtsIssue[] = [];
  const [pw, ph] = pageSize(doc.style);
  const seen = new Set<string>();
  const add = (issue: AtsIssue) => {
    const key = `${issue.kind}:${[...issue.ids].sort().join(",")}`;
    if (!seen.has(key)) {
      seen.add(key);
      issues.push(issue);
    }
  };

  doc.pages.forEach((page, pi) => {
    const label = doc.pages.length > 1 ? ` on page ${pi + 1}` : "";
    const texts = page.elements.filter(hasText);
    const shapes = page.elements.filter(
      (el) => el.kind === "shape" && el.fill !== "none" && el.h >= SHAPE_MIN_HEIGHT_MM && el.w >= SHAPE_MIN_HEIGHT_MM,
    );

    for (let i = 0; i < texts.length; i += 1) {
      for (let j = i + 1; j < texts.length; j += 1) {
        const a = texts[i]!;
        const b = texts[j]!;
        const area = overlapArea(boxOf(a), boxOf(b));
        if (area > 0 && area / Math.min(a.w * a.h, b.w * b.h) >= OVERLAP_SHARE) {
          add({
            kind: "overlap",
            blocks: true,
            ids: [a.id, b.id],
            message: `"${a.name}" and "${b.name}" overlap${label}. A reader may mix their text together.`,
          });
          continue;
        }
        const sideBySide = a.x + a.w <= b.x || b.x + b.w <= a.x;
        const big = (e: TextElement) => e.w >= COLUMN_MIN_WIDTH_MM && e.h >= COLUMN_MIN_HEIGHT_MM;
        if (sideBySide && big(a) && big(b) && verticalShare(boxOf(a), boxOf(b)) >= 0.4) {
          add({
            kind: "columns",
            blocks: true,
            ids: [a.id, b.id],
            message: `"${a.name}" and "${b.name}" sit side by side as columns${label}. Many systems read across a row and mix the columns.`,
          });
        }
      }
    }

    for (const text of texts) {
      const onShape = shapes.find((s) => overlapArea(boxOf(text), boxOf(s)) / (text.w * text.h) >= 0.6);
      if (onShape) {
        add({
          kind: "on_shape",
          blocks: true,
          ids: [text.id, onShape.id],
          message: `"${text.name}" sits on a filled shape${label}. Some systems skip text that is drawn over shapes.`,
        });
      }
      if (text.size < SMALL_TEXT_PT) {
        add({
          kind: "small_text",
          blocks: false,
          ids: [text.id],
          message: `"${text.name}" is under ${SMALL_TEXT_PT} pt${label}. It is hard to read in print and on small screens.`,
        });
      }
      const color = resolveColor(text.color, doc.style);
      if (!onShape && /^#[0-9a-f]{6}$/i.test(color) && contrastOnWhite(color) < MIN_CONTRAST) {
        add({
          kind: "contrast",
          blocks: false,
          ids: [text.id],
          message: `"${text.name}" is hard to read on white paper${label}. Choose a darker color.`,
        });
      }
    }

    for (const el of page.elements) {
      if (!hasText(el)) continue;
      if (el.x < EDGE_MM || el.y < EDGE_MM || el.x + el.w > pw - EDGE_MM || el.y + el.h > ph - EDGE_MM) {
        add({
          kind: "edge",
          blocks: false,
          ids: [el.id],
          message: `"${el.name}" is within ${EDGE_MM} mm of the page edge${label}. Many printers cut it off.`,
        });
      }
    }
  });
  return { safe: !issues.some((i) => i.blocks), issues };
}
