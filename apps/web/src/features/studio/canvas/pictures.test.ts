import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { analyzeAts } from "./ats";
import { elementCss, imageCss } from "./css";
import { addElement, makeIcon, makeImage, makeText, pictureCount } from "./edit";
import { DEFAULT_WEIGHT, ICON_DATA, ICON_LABELS, ICON_NAMES, iconSvg, WEIGHTS } from "./icons";
import type { CanvasDoc, CanvasElement, CanvasStyle, IconElement, ImageElement } from "./types";

const fixtures = (name: string) => JSON.parse(readFileSync(resolve(process.cwd(), "../../tests/fixtures", name), "utf-8"));

const style: CanvasStyle = {
  template: "free",
  font_pair: "plex-newsreader",
  accent: "#1f3d7a",
  ink: "#1b1b1b",
  muted: "#4a4a4a",
  tint: "#eef1f6",
  paper: "a4",
  margin_mm: 16,
};

function doc(...elements: CanvasElement[]): CanvasDoc {
  return { version: 2, style, pages: [{ id: "p1", elements }] };
}

const picture = { id: "3f1c2a54-6b7d-4e0a-9c11-5a2b7d8e9f01", width: 800, height: 1000, name: "me.jpg" };

describe("pictures and icons share their drawing with the server", () => {
  const golden = fixtures("canvas_css_golden.json") as {
    name: string;
    style: CanvasStyle;
    element: CanvasElement;
    z: number;
    css: Record<string, string>;
    inner?: Record<string, string>;
    svg?: string;
  }[];

  it("has picture and icon cases to check", () => {
    expect(golden.filter((g) => g.element.kind === "image").length).toBeGreaterThanOrEqual(3);
    expect(golden.filter((g) => g.element.kind === "icon").length).toBeGreaterThanOrEqual(2);
  });

  it.each(golden.filter((g) => g.element.kind === "image").map((g) => [g.name, g] as const))("draws the picture inside %s as the server does", (_n, g) => {
    expect(elementCss(g.element, g.style, g.z)).toEqual(g.css);
    expect(imageCss(g.element as ImageElement)).toEqual(g.inner);
  });

  it.each(golden.filter((g) => g.element.kind === "icon").map((g) => [g.name, g] as const))("draws the icon in %s as the server does", (_n, g) => {
    const el = g.element as IconElement;
    expect(elementCss(el, g.style, g.z)).toEqual(g.css);
    expect(iconSvg(el.icon, el.weight)).toBe(g.svg);
  });

  it("has every icon, at every weight, exactly as the server draws it", () => {
    const icons = fixtures("canvas_icons_golden.json") as Record<string, { shapes: unknown; svg: Record<string, string> }>;
    expect(Object.keys(icons).sort()).toEqual([...ICON_NAMES].sort());
    for (const [name, entry] of Object.entries(icons)) {
      expect(ICON_DATA[name]).toEqual(entry.shapes);
      for (const weight of Object.keys(WEIGHTS)) expect(iconSvg(name, Number(weight))).toBe(entry.svg[weight]);
    }
  });

  it("labels every icon and names no brand", () => {
    expect(Object.keys(ICON_LABELS).sort()).toEqual([...ICON_NAMES].sort());
    expect(ICON_NAMES.some((n) => /linkedin|github|twitter|facebook|google|indeed/.test(n))).toBe(false);
  });

  it("draws only plain shapes with nothing that could run", () => {
    for (const name of ICON_NAMES) {
      const svg = iconSvg(name, DEFAULT_WEIGHT);
      expect(svg).not.toMatch(/<script|on\w+=|href=|<style|<image|<foreignObject/i);
      expect(svg.startsWith("<svg ") && svg.endsWith("</svg>")).toBe(true);
    }
    expect(iconSvg("not-an-icon")).toContain("<svg");
  });
});

describe("making pictures and icons", () => {
  it("makes a picture box that keeps the pictures shape and stays on the page", () => {
    const d = doc();
    const el = makeImage(d, picture);
    expect(el.kind).toBe("image");
    expect(el.image_id).toBe(picture.id);
    expect(el.w).toBe(40);
    expect(el.h).toBeCloseTo(50, 1); // 800 by 1000
    expect(el.x + el.w).toBeLessThanOrEqual(210 - 16 + 0.001);
    expect(el.y).toBe(16);
    expect(el).toMatchObject({ fit: "cover", shape: "rect", focus_x: 50, focus_y: 50, decorative: false, alt: "" });
  });

  it("keeps a very tall picture inside the page", () => {
    const el = makeImage(doc(), { ...picture, width: 100, height: 4000 });
    expect(el.h).toBeLessThanOrEqual(297 - 32);
  });

  it("names pictures and icons one after another", () => {
    let d = doc();
    d = addElement(d, 0, makeImage(d, picture));
    expect(makeImage(d, picture).name).toBe("Picture 2");
    d = addElement(d, 0, makeIcon(d, "mail"));
    expect(makeIcon(d, "phone").name).toBe("Icon 2");
  });

  it("makes a small accent icon", () => {
    const el = makeIcon(doc(), "pin");
    expect(el).toMatchObject({ kind: "icon", icon: "pin", w: 5, h: 5, color: "accent", weight: 2, alt: "" });
  });

  it("counts only pictures against the limit, not icons or text", () => {
    let d = doc();
    d = addElement(d, 0, makeImage(d, picture));
    d = addElement(d, 0, makeIcon(d, "mail"));
    d = addElement(d, 0, makeText(d, 0));
    expect(pictureCount(d)).toBe(1);
  });
});

describe("the layout check and pictures", () => {
  it("says a picture may not be read by hiring systems, as a note and not a block", () => {
    const d = doc(makeImage(doc(), picture, { alt: "Asha at her desk" }));
    const report = analyzeAts(d);
    const note = report.issues.find((i) => i.kind === "picture");
    expect(note?.message).toMatch(/Many employers advise against photos/);
    expect(note?.blocks).toBe(false);
    expect(report.safe).toBe(true);
  });

  it("asks for a description when a picture has none, unless it is decorative", () => {
    const bare = analyzeAts(doc(makeImage(doc(), picture)));
    expect(bare.issues.some((i) => /no description/.test(i.message))).toBe(true);
    const decorative = analyzeAts(doc(makeImage(doc(), picture, { decorative: true })));
    expect(decorative.issues.some((i) => /no description/.test(i.message))).toBe(false);
    const described = analyzeAts(doc(makeImage(doc(), picture, { alt: "A logo" })));
    expect(described.issues.some((i) => /no description/.test(i.message))).toBe(false);
  });

  it("says nothing about icons, which are decoration", () => {
    const report = analyzeAts(doc(makeIcon(doc(), "mail")));
    expect(report.issues.some((i) => i.kind === "picture")).toBe(false);
  });
});
