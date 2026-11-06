import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import { fakeApi } from "./fake-api";

const WCAG_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];

async function axe(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(WCAG_TAGS).analyze();
  expect(
    results.violations.map((v) => ({
      id: v.id,
      nodes: v.nodes.slice(0, 2).map((n) => n.target.join(" ")),
    })),
  ).toEqual([]);
}

const section = (page: Page) => page.getByRole("region", { name: "Your data" });

async function open(page: Page, refuse: "password" | "server" | null = null) {
  await page.setViewportSize({ width: 1400, height: 1000 });
  const fake = await fakeApi(page, {
    account: { deleted: false, refuse, calls: [] },
  });
  await page.goto("/settings");
  await expect(section(page)).toBeVisible();
  return fake;
}

const dialog = (page: Page) =>
  page.getByRole("dialog", { name: "Delete your account?" });

test("your data offers a copy to download and a way to delete, and says what each does", async ({
  page,
}) => {
  await open(page);
  const link = section(page).getByRole("link", { name: "Download my data" });
  await expect(link).toHaveAttribute("href", "/api/v1/account/export");
  await expect(link).toHaveAttribute("download", "Provenance data.json");
  await expect(section(page)).toContainText(
    "leaves out your password, sign-in sessions and the files you uploaded",
  );
  await expect(section(page)).toContainText("It cannot be undone");
  await expect(
    section(page).getByRole("link", { name: "privacy policy" }),
  ).toHaveAttribute("href", "/privacy");
});

test("deleting asks for the password and the words, and cancel changes nothing", async ({
  page,
}) => {
  const fake = await open(page);
  await section(page)
    .getByRole("button", { name: "Delete my account" })
    .click();
  await expect(dialog(page)).toBeVisible();
  await expect(
    dialog(page).getByRole("button", { name: "Cancel" }),
  ).toBeFocused(); // a stray Enter must not confirm
  await dialog(page).getByRole("button", { name: "Delete my account" }).click();
  await expect(dialog(page)).toContainText("Enter your password.");
  await expect(dialog(page)).toContainText(
    'Type "delete my account" to confirm.',
  );
  expect(fake.account.calls).toEqual([]); // nothing was sent
  await dialog(page).getByRole("button", { name: "Cancel" }).click();
  await expect(dialog(page)).toBeHidden();
  await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible();
  expect(fake.account.deleted).toBe(false);
});

test("a wrong password is shown on the field and nothing is deleted", async ({
  page,
}) => {
  const fake = await open(page, "password");
  await section(page)
    .getByRole("button", { name: "Delete my account" })
    .click();
  await dialog(page).getByLabel("Your password").fill("wrong password");
  await dialog(page).getByLabel(/^Type/).fill("delete my account");
  await dialog(page).getByRole("button", { name: "Delete my account" }).click();
  await expect(dialog(page)).toContainText("Your password is not correct.");
  expect(fake.account.deleted).toBe(false);
  await expect(dialog(page)).toBeVisible();
});

test("a server problem is said plainly and the dialog stays open to try again", async ({
  page,
}) => {
  await open(page, "server");
  await section(page)
    .getByRole("button", { name: "Delete my account" })
    .click();
  await dialog(page).getByLabel("Your password").fill("a password");
  await dialog(page).getByLabel(/^Type/).fill("delete my account");
  await dialog(page).getByRole("button", { name: "Delete my account" }).click();
  await expect(dialog(page).getByRole("alert")).toContainText(
    "Something went wrong on our side.",
  );
  await expect(dialog(page)).toBeVisible();
});

test("confirming signs you out and takes you to the sign-in page", async ({
  page,
}) => {
  const fake = await open(page);
  await section(page)
    .getByRole("button", { name: "Delete my account" })
    .click();
  await dialog(page).getByLabel("Your password").fill("a password");
  await dialog(page).getByLabel(/^Type/).fill("  Delete   MY account ");
  await dialog(page).getByRole("button", { name: "Delete my account" }).click();
  await expect(page).toHaveURL(/\/signin/);
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
  expect(fake.account.deleted).toBe(true);
  expect(fake.account.calls).toEqual(["delete:  Delete   MY account "]);
});

test("the privacy policy and the terms are public pages that say what is still open", async ({
  page,
}) => {
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/v1/auth/session")
      return route.fulfill({
        json: {
          authenticated: false,
          user: null,
          csrf_token: null,
          config: { signup_mode: "invite", email_verification_required: false },
        },
      });
    return route.fulfill({ status: 404, json: { detail: "not mocked" } });
  });
  await page.goto("/privacy");
  await expect(
    page.getByRole("heading", { level: 1, name: "Privacy policy" }),
  ).toBeVisible();
  await expect(page.getByText("Open before launch")).toBeVisible();
  await expect(
    page.getByText("A lawyer has not yet read this policy."),
  ).toBeVisible();
  for (const heading of [
    "What we keep",
    "Who else handles your data",
    "How long we keep it",
    "Your choices",
  ]) {
    await expect(
      page.getByRole("heading", { level: 2, name: heading }),
    ).toBeVisible();
  }
  await expect(
    page.getByText("up to 30 days after it is deleted"),
  ).toBeVisible();
  await page
    .getByRole("navigation", { name: "Legal" })
    .getByRole("link", { name: "Terms of use" })
    .click();
  await expect(
    page.getByRole("heading", { level: 1, name: "Terms of use" }),
  ).toBeVisible();
  await expect(page.getByText("Results are help, not advice")).toBeVisible();
});

test("the sign-in page links to both documents", async ({ page }) => {
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/v1/auth/session")
      return route.fulfill({
        json: {
          authenticated: false,
          user: null,
          csrf_token: null,
          config: { signup_mode: "invite", email_verification_required: false },
        },
      });
    return route.fulfill({ status: 404, json: { detail: "not mocked" } });
  });
  await page.goto("/signin");
  await expect(
    page.getByRole("link", { name: "Privacy policy" }),
  ).toHaveAttribute("href", "/privacy");
  await expect(
    page.getByRole("link", { name: "Terms of use" }),
  ).toHaveAttribute("href", "/terms");
});

for (const theme of ["light", "dark"] as const) {
  test(`axe: your data, the dialog and the legal pages (${theme})`, async ({
    page,
  }) => {
    await page.addInitScript(
      (value) => window.localStorage.setItem("pv-theme", value),
      theme,
    );
    await open(page);
    await axe(page);
    await section(page)
      .getByRole("button", { name: "Delete my account" })
      .click();
    await expect(dialog(page)).toBeVisible();
    await dialog(page)
      .getByRole("button", { name: "Delete my account" })
      .click();
    await expect(dialog(page)).toContainText("Enter your password.");
    await axe(page);
    await page.keyboard.press("Escape");
    for (const path of ["/privacy", "/terms"]) {
      await page.goto(path);
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      await axe(page);
    }
  });
}

test("on a phone nothing scrolls sideways", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await fakeApi(page, {});
  const wide = () =>
    page.evaluate(
      () =>
        document.documentElement.scrollWidth -
        document.documentElement.clientWidth,
    );
  await page.goto("/settings");
  await expect(section(page)).toBeVisible();
  expect(await wide()).toBeLessThanOrEqual(0);
  await page.goto("/privacy");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  expect(await wide()).toBeLessThanOrEqual(0);
});
