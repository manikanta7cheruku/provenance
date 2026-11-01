import type { CSSProperties } from "react";
import type { CanvasElement, CanvasStyle } from "./types";

/**
 * The CSS of one element. The server writes the same declarations for the PDF
 * (pv_domain.resume_canvas.element_css). tests/fixtures/canvas_css_golden.json is checked by both,
 * so what is drawn here and what is printed cannot drift without a test failing.
 */

/** CSS family name -> file prefix of the shipped fonts. The server has the same table. */
const FAMILIES: Record<string, string> = {
  "PV Plex": "ibm-plex-sans",
  "PV Serif": "newsreader",
  "PV Inter": "inter",
  "PV Lato": "lato",
  "PV Source": "source-sans-3",
  "PV Montserrat": "montserrat",
  "PV Lora": "lora",
  "PV Merriweather": "merriweather",
  "PV Playfair": "playfair-display",
};
const SERIF = "Georgia, serif";
const SANS = "Arial, sans-serif";
const SERIF_FAMILIES = new Set(["PV Serif", "PV Lora", "PV Merriweather", "PV Playfair"]);
const stack = (family: string) => `"${family}", ${SERIF_FAMILIES.has(family) ? SERIF : SANS}`;

/** key -> [heading family, body family]. */
export const FONT_PAIR_FAMILIES: Record<string, readonly [string, string]> = {
  "plex-newsreader": ["PV Serif", "PV Plex"],
  plex: ["PV Plex", "PV Plex"],
  newsreader: ["PV Serif", "PV Serif"],
  inter: ["PV Inter", "PV Inter"],
  "inter-lora": ["PV Lora", "PV Inter"],
  lato: ["PV Lato", "PV Lato"],
  "montserrat-lato": ["PV Montserrat", "PV Lato"],
  source: ["PV Source", "PV Source"],
  "source-merriweather": ["PV Merriweather", "PV Source"],
  "playfair-source": ["PV Playfair", "PV Source"],
  lora: ["PV Lora", "PV Lora"],
  merriweather: ["PV Merriweather", "PV Merriweather"],
};

const FONT_FAMILIES: Record<string, readonly [string, string]> = Object.fromEntries(
  Object.entries(FONT_PAIR_FAMILIES).map(([key, [h, b]]) => [key, [stack(h), stack(b)] as const]),
);

export const FONT_FILES: readonly (readonly [string, number, string, string])[] = Object.entries(FAMILIES).flatMap(
  ([family, prefix]) =>
    ([400, 600] as const).flatMap((weight) =>
      (["normal", "italic"] as const).map((style) => [family, weight, style, `${prefix}-latin-${weight}-${style}.woff`] as const),
    ),
);

/** The @font-face rules for the shipped fonts, served by the API's public font route. */
export function fontFaceCss(base = "/api/v1/studio/fonts/"): string {
  return FONT_FILES.map(
    ([family, weight, style, file]) =>
      `@font-face{font-family:"${family}";font-weight:${weight};font-style:${style};src:url("${base}${file}") format("woff");}`,
  ).join("\n");
}

export function resolveColor(value: string, style: CanvasStyle): string {
  if (value === "ink") return style.ink;
  if (value === "muted") return style.muted;
  if (value === "accent") return style.accent;
  if (value === "tint") return style.tint;
  if (value === "white") return "#ffffff";
  if (value === "none") return "transparent";
  return value;
}

/** Millimetres the way the server writes them: two decimals, no trailing zeros. */
export function mm(value: number): string {
  const text = value.toFixed(2).replace(/0+$/, "").replace(/\.$/, "");
  return `${text === "" ? "0" : text}mm`;
}

export function elementCss(el: CanvasElement, style: CanvasStyle, z: number): Record<string, string> {
  const css: Record<string, string> = {
    position: "absolute",
    left: mm(el.x),
    top: mm(el.y),
    width: mm(el.w),
    "z-index": String(z),
  };
  if (el.kind === "text") {
    const [heading, body] = FONT_FAMILIES[style.font_pair] ?? FONT_FAMILIES["plex-newsreader"]!;
    css["min-height"] = mm(el.h);
    css["font-family"] = el.font === "heading" ? heading : body;
    css["font-size"] = `${el.size}pt`;
    css["line-height"] = String(el.line_height);
    css.color = resolveColor(el.color, style);
    css["text-align"] = el.align;
    if (el.caps) {
      css["text-transform"] = "uppercase";
      css["letter-spacing"] = "0.06em";
    }
  } else {
    css.height = mm(el.h);
    css.background = resolveColor(el.fill, style);
    if (el.stroke !== "none" && el.stroke_pt > 0) {
      css.border = `${el.stroke_pt}pt solid ${resolveColor(el.stroke, style)}`;
    }
    if (el.radius > 0) css["border-radius"] = mm(el.radius);
  }
  return css;
}

/** The same declarations as a React style object. */
export function reactStyle(css: Record<string, string>): CSSProperties {
  const out: Record<string, string> = {};
  for (const [key, value] of Object.entries(css)) {
    out[key.replace(/-([a-z])/g, (_, c: string) => c.toUpperCase())] = value;
  }
  return out as CSSProperties;
}

function luminance(hex: string): number {
  const channel = (v: number) => {
    const c = v / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * channel(parseInt(hex.slice(1, 3), 16)) + 0.7152 * channel(parseInt(hex.slice(3, 5), 16)) + 0.0722 * channel(parseInt(hex.slice(5, 7), 16));
}

/** The WCAG contrast ratio of two #rrggbb colors, from 1 to 21. */
export function contrastRatio(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x) as [number, number];
  return (hi + 0.05) / (lo + 0.05);
}

/** Hex colors need a readable check against white. Used for a warning, not a refusal. */
export function contrastOnWhite(hex: string): number {
  const channel = (v: number) => {
    const c = v / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  };
  const r = channel(parseInt(hex.slice(1, 3), 16));
  const g = channel(parseInt(hex.slice(3, 5), 16));
  const b = channel(parseInt(hex.slice(5, 7), 16));
  return 1.05 / (0.2126 * r + 0.7152 * g + 0.0722 * b + 0.05);
}
