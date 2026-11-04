import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import { canvasDoc, fakeApi, newStudio, TINY_PNG } from "./fake-api";
import type { FakeImage, FakeStudio } from "./fake-api";

const WCAG_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];

async function axe(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(WCAG_TAGS).analyze();
  expect(results.violations.map((v) => ({ id: v.id, nodes: v.nodes.slice(0, 2).map((n) => n.target.join(" ")) }))).toEqual([]);
}

type El = { id: string; kind: string; name: string; [key: string]: unknown };
const withCanvas = (): FakeStudio => ({ ...newStudio(), doc: canvasDoc() });
const els = (fake: { studio: FakeStudio }): El[] => (fake.studio.doc?.content.pages[0].elements ?? []) as El[];

async function open(page: Page, images: FakeImage[] = []) {
  await page.setViewportSize({ width: 1500, height: 1000 });
  const fake = await fakeApi(page, { studio: withCanvas(), images });
  await page.goto("/studio");
  await expect(page.locator("[data-el='name']")).toBeVisible();
  return fake;
}

const saved = (page: Page) => expect(page.getByText(/All changes saved/)).toBeVisible({ timeout: 8000 });
const png = (name: string) => ({ name, mimeType: "image/png", buffer: TINY_PNG });
const MINE: FakeImage = { id: "img-1", name: "asha.png", width: 800, height: 1000 };

async function addMine(page: Page) {
  await page.getByRole("button", { name: "Add picture" }).click();
  await page.getByRole("dialog", { name: "Pictures" }).getByRole("button", { name: /Add to page\s*:\s*asha\.png/ }).click();
}

test("the picture dialog says what is accepted, what is removed, and that photos are not for everyone", async ({ page }) => {
  await open(page);
  await page.getByRole("button", { name: "Add picture" }).click();
  const dialog = page.getByRole("dialog", { name: "Pictures" });
  await expect(dialog).toContainText("Many employers advise against photos");
  await expect(dialog).toContainText("JPEG, PNG or WebP");
  await expect(dialog).toContainText("camera, place and time stored in a photo are removed");
  await expect(dialog).toContainText("No pictures yet");
});

test("a picture is uploaded, listed with its size, and added to the page described as needing a description", async ({ page }) => {
  const fake = await open(page);
  await page.getByRole("button", { name: "Add picture" }).click();
  const dialog = page.getByRole("dialog", { name: "Pictures" });
  await dialog.getByLabel("Upload a picture").setInputFiles(png("asha.png"));
  await expect(dialog.locator(".cv-pictures__name", { hasText: "asha.png" })).toBeVisible();
  await expect(dialog.getByText(/800 by 1000 pixels/)).toBeVisible();
  await expect(dialog.getByText(/1 of 20 pictures/)).toBeVisible();
  await dialog.getByRole("button", { name: /Add to page\s*:\s*asha\.png/ }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.getByText("Picture added.")).toBeVisible();
  await saved(page);
  const picture = els(fake).find((e) => e.kind === "image")!;
  expect(picture).toMatchObject({ image_id: fake.images[0]!.id, fit: "cover", shape: "rect", decorative: false, alt: "" });
  await expect(page.locator(`[data-el='${picture.id}'] img`)).toHaveAttribute("src", /\/api\/v1\/studio\/images\/img-.+\/file/);
  await expect(page.getByText("This picture has no description yet.")).toBeVisible();
});

test("the description, the shape, the crop and the fit change the picture and are saved", async ({ page }) => {
  const fake = await open(page, [MINE]);
  await addMine(page);
  await saved(page);
  const id = els(fake).find((e) => e.kind === "image")!.id;
  await page.getByLabel("Description of the picture").fill("Asha at her desk");
  await expect(page.getByText("This picture has no description yet.")).toHaveCount(0);
  await page.getByLabel("Shape", { exact: true }).selectOption("circle");
  await page.getByLabel("Fit", { exact: true }).selectOption("contain");
  await page.getByLabel("Crop across").fill("25");
  await page.getByLabel("Crop across").press("Enter");
  await saved(page);
  const box = page.locator(`[data-el='${id}']`);
  await expect(box).toHaveCSS("border-radius", /50%|\d+px/);
  await expect(box.locator("img")).toHaveCSS("object-fit", "contain");
  const el = els(fake).find((e) => e.id === id)!;
  expect(el).toMatchObject({ alt: "Asha at her desk", shape: "circle", fit: "contain", focus_x: 25 });
});

test("a decorative picture needs no description, and the layout check says what pictures risk", async ({ page }) => {
  const fake = await open(page, [MINE]);
  await addMine(page);
  await page.getByLabel(/Decorative: it adds nothing/).check();
  await expect(page.getByText("This picture has no description yet.")).toHaveCount(0);
  await page.getByRole("button", { name: /Layout check/ }).click();
  await expect(page.getByText(/some hiring systems ignore pictures/).first()).toBeVisible();
  await saved(page);
  expect(els(fake).find((e) => e.kind === "image")).toMatchObject({ decorative: true });
});

test("a picture we do not accept is refused in words and nothing is added", async ({ page }) => {
  const fake = await open(page);
  await page.getByRole("button", { name: "Add picture" }).click();
  const dialog = page.getByRole("dialog", { name: "Pictures" });
  await dialog.getByLabel("Upload a picture").setInputFiles({ name: "logo.pdf", mimeType: "application/pdf", buffer: Buffer.from("x") });
  await expect(dialog.getByText(/This file type is not supported/)).toBeVisible();
  await dialog.getByLabel("Upload a picture").setInputFiles({ name: "logo.svg", mimeType: "image/svg+xml", buffer: Buffer.from("<svg/>") });
  await expect(dialog.getByText(/This file type is not supported/)).toBeVisible(); // the browser check
  expect(fake.images).toHaveLength(0);
});

test("the server's refusal of a picture is shown beside the upload", async ({ page }) => {
  const fake = await open(page);
  await page.getByRole("button", { name: "Add picture" }).click();
  const dialog = page.getByRole("dialog", { name: "Pictures" });
  await dialog.getByLabel("Upload a picture").setInputFiles(png("huge-photo.png"));
  await expect(dialog.getByText(/much larger than a resume needs/)).toBeVisible();
  expect(fake.images).toHaveLength(0);
});

test("a picture can be deleted unless a resume still uses it", async ({ page }) => {
  await open(page, [MINE, { id: "img-2", name: "logo.png", width: 400, height: 400, used: true }]);
  await page.getByRole("button", { name: "Add picture" }).click();
  const dialog = page.getByRole("dialog", { name: "Pictures" });
  await expect(dialog.getByRole("button", { name: /Delete\s*:\s*logo\.png/ })).toBeDisabled();
  await dialog.getByRole("button", { name: /Delete\s*:\s*asha\.png/ }).click();
  await expect(dialog.locator(".cv-pictures__name", { hasText: "asha.png" })).toHaveCount(0);
  await expect(dialog.locator(".cv-pictures__name", { hasText: "logo.png" })).toBeVisible();
});

test("the icon picker adds an icon that takes its color from the style, and it can be changed", async ({ page }) => {
  const fake = await open(page);
  await page.getByRole("button", { name: "Add icon" }).click();
  const dialog = page.getByRole("dialog", { name: "Icons" });
  await expect(dialog).toContainText("An icon is decoration");
  await dialog.getByRole("button", { name: /Email icon, add to page/ }).click();
  await expect(page.getByText("Icon added.")).toBeVisible();
  await saved(page);
  const icon = els(fake).find((e) => e.kind === "icon")!;
  expect(icon).toMatchObject({ icon: "mail", weight: 2, color: "accent", w: 5, h: 5 });
  await expect(page.locator(`[data-el='${icon.id}'] svg`)).toBeVisible();
  await page.getByLabel("Icon", { exact: true }).selectOption("phone");
  await page.getByLabel("Line weight").selectOption("3");
  await page.getByLabel("Size").fill("8");
  await page.getByLabel("Size").press("Enter");
  await saved(page);
  expect(els(fake).find((e) => e.id === icon.id)).toMatchObject({ icon: "phone", weight: 3, w: 8, h: 8 });
});

test("pictures and icons appear in the layers list", async ({ page }) => {
  await open(page, [MINE]);
  await addMine(page);
  await page.getByRole("button", { name: "Add icon" }).click();
  await page.getByRole("dialog", { name: "Icons" }).getByRole("button", { name: /Place icon/ }).click();
  await page.getByRole("button", { name: "Layers", exact: true }).click();
  await expect(page.locator(".cv-layers__kind", { hasText: "Picture" })).toBeVisible();
  await expect(page.locator(".cv-layers__kind", { hasText: "Icon" })).toBeVisible();
});

test("a resume that holds as many pictures as it can will not take another", async ({ page }) => {
  const studio = withCanvas();
  const base = studio.doc!.content.pages[0].elements as El[];
  for (let n = 0; n < 5; n += 1) {
    base.push({ id: `pic${n}`, kind: "image", name: `Picture ${n + 1}`, x: 10 + n * 12, y: 100, w: 10, h: 10, locked: false, group: null, image_id: "img-1", alt: "x", decorative: false, fit: "cover", shape: "rect", focus_x: 50, focus_y: 50, border: "none", border_pt: 0 });
  }
  await page.setViewportSize({ width: 1500, height: 1000 });
  await fakeApi(page, { studio, images: [MINE] });
  await page.goto("/studio");
  await expect(page.locator("[data-el='name']")).toBeVisible();
  await page.getByRole("button", { name: "Add picture" }).click();
  const dialog = page.getByRole("dialog", { name: "Pictures" });
  await expect(dialog.getByText(/already has the most pictures it can hold/)).toBeVisible();
  await expect(dialog.getByRole("button", { name: /Add to page\s*:\s*asha\.png/ })).toBeDisabled();
});

for (const theme of ["light", "dark"] as const) {
  test(`axe: the picture and icon dialogs and their properties (${theme})`, async ({ page }) => {
    await page.addInitScript((value) => window.localStorage.setItem("pv-theme", value), theme);
    await open(page, [MINE, { id: "img-2", name: "logo.png", width: 400, height: 400, used: true }]);
    await page.getByRole("button", { name: "Add picture" }).click();
    await axe(page);
    await page.getByRole("dialog", { name: "Pictures" }).getByRole("button", { name: /Add to page\s*:\s*asha\.png/ }).click();
    await axe(page); // a picture selected, with the missing description error
    await page.getByLabel("Description of the picture").fill("Asha at her desk");
    await axe(page);
    await page.getByRole("button", { name: "Add icon" }).click();
    await axe(page);
    await page.getByRole("dialog", { name: "Icons" }).getByRole("button", { name: /Email icon, add to page/ }).click();
    await axe(page); // an icon selected
  });
}
