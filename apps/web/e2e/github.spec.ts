import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import { fakeApi, githubRepos } from "./fake-api";
import type { Fake, FakeGitHub } from "./fake-api";

const WCAG_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];

async function axe(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(WCAG_TAGS).analyze();
  expect(results.violations.map((v) => ({ id: v.id, nodes: v.nodes.slice(0, 2).map((n) => n.target.join(" ")) }))).toEqual([]);
}

const github = (over: Partial<FakeGitHub> = {}): FakeGitHub => ({ available: true, connected: false, reads: 0, sync_state: "idle", sync_error: null, repos: [], revoked: true, calls: [], ...over });
const panel = (page: Page) => page.getByRole("region", { name: "GitHub" });

async function openProfile(page: Page, initial: Partial<Fake>) {
  await page.setViewportSize({ width: 1400, height: 1000 });
  const fake = await fakeApi(page, initial);
  await page.goto("/profile");
  await expect(panel(page)).toBeVisible();
  return fake;
}

test("it says what is asked of GitHub: no permissions, public information only", async ({ page }) => {
  await openProfile(page, { github: github() });
  await expect(panel(page)).toContainText("no permissions at all");
  await expect(panel(page)).toContainText("public information only");
  await expect(panel(page)).toContainText("never sees your password");
  await expect(panel(page).getByRole("button", { name: "Connect GitHub" })).toBeVisible();
});

test("when the server has no GitHub app the screen says so and offers nothing to click", async ({ page }) => {
  await openProfile(page, { github: github({ available: false }) });
  await expect(panel(page)).toContainText("GitHub is not set up on this server");
  await expect(panel(page).getByRole("button", { name: "Connect GitHub" })).toHaveCount(0);
});

test("connecting sends the person to GitHub and back, then lists repositories to choose", async ({ page }) => {
  const fake = await openProfile(page, { github: github() });
  // Stand in for github.com: it sends the person straight back with a code and the state.
  await page.route("https://github.com/login/oauth/authorize**", (route) => {
    const state = new URL(route.request().url()).searchParams.get("state") ?? "";
    return route.fulfill({ status: 302, headers: { location: `${new URL(page.url()).origin}/connect/github/callback?code=good&state=${state}` } });
  });
  await panel(page).getByRole("button", { name: "Connect GitHub" }).click();
  await expect(page).toHaveURL(/\/profile$/);
  expect(fake.github.calls).toEqual(["start", "callback:good"]);
  await expect(panel(page)).toContainText("Connected as asha");
  await expect(panel(page).getByRole("group", { name: "Repositories to use as evidence" })).toBeVisible({ timeout: 10_000 });
  await expect(panel(page).getByLabel("asha/project-1")).toBeVisible();
  await expect(panel(page)).toContainText("Suggested");
});

test("the code and state do not stay in the address bar", async ({ page }) => {
  await openProfile(page, { github: github() });
  await page.goto("/connect/github/callback?code=good&state=" + "s".repeat(40));
  await expect(page).toHaveURL(/\/profile$/);
  const history = await page.evaluate(() => window.history.length);
  expect(history).toBeGreaterThan(0);
  expect(page.url()).not.toContain("code=");
});

test("choosing repositories makes entries marked as coming from GitHub", async ({ page }) => {
  const fake = await openProfile(page, { github: github({ connected: true, repos: githubRepos() }) });
  await expect(panel(page)).toContainText("Connected as asha");
  await expect(panel(page).getByRole("button", { name: "Use these as evidence" })).toBeDisabled();
  await panel(page).getByLabel("asha/project-1").check();
  await panel(page).getByLabel("asha/project-2").check();
  await panel(page).getByRole("button", { name: "Use these as evidence" }).click();
  expect(fake.github.calls).toContain("repos:1,2");
  await expect(page.getByText("Using 2 repositories as evidence")).toBeVisible();
  await expect(page.getByText(/^From GitHub/).first()).toBeVisible({ timeout: 10_000 });
  await expect(page.getByText("project-1", { exact: true }).first()).toBeVisible();
});

test("more than twelve cannot be chosen", async ({ page }) => {
  const many = Array.from({ length: 14 }, (_, i) => ({ ...githubRepos()[0]!, id: i + 1, full_name: `asha/p${i + 1}`, name: `p${i + 1}`, suggested: false }));
  await openProfile(page, { github: github({ connected: true, repos: many }) });
  for (let i = 1; i <= 13; i += 1) await panel(page).getByLabel(`asha/p${i}`, { exact: true }).check();
  await expect(panel(page).getByText("Choose at most 12 repositories.")).toBeVisible();
  await expect(panel(page).getByRole("button", { name: "Use these as evidence" })).toBeDisabled();
});

test("read again starts a new read and shows it is reading", async ({ page }) => {
  const fake = await openProfile(page, { github: github({ connected: true, repos: githubRepos() }) });
  await panel(page).getByRole("button", { name: "Read my repositories again" }).click();
  expect(fake.github.calls).toContain("sync");
  await expect(panel(page).getByText("Reading your repositories.")).toBeVisible();
});

test("a failed read says what to do", async ({ page }) => {
  await openProfile(page, { github: github({ connected: true, repos: githubRepos(), sync_state: "failed", sync_error: "GitHub says the connection is no longer valid. Connect GitHub again to continue." }) });
  await expect(panel(page)).toContainText("The last read did not work");
  await expect(panel(page)).toContainText("Connect GitHub again to continue");
});

test("disconnecting asks first, says what happens, and removes the entries", async ({ page }) => {
  const fake = await openProfile(page, { github: github({ connected: true, repos: githubRepos().map((r, i) => ({ ...r, selected: i === 0 })) }) });
  await panel(page).getByRole("button", { name: "Read my repositories again" }).click();
  await expect(page.getByText(/^From GitHub/).first()).toBeVisible({ timeout: 10_000 });
  await panel(page).getByRole("button", { name: "Disconnect GitHub" }).click();
  const dialog = page.getByRole("dialog", { name: "Disconnect GitHub?" });
  await expect(dialog).toContainText("stored access token is deleted");
  await dialog.getByRole("button", { name: "Cancel" }).click();
  expect(fake.github.calls.some((c) => c.startsWith("disconnect"))).toBe(false);
  await panel(page).getByRole("button", { name: "Disconnect GitHub" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Disconnect" }).click();
  await expect(page.getByText(/GitHub is disconnected and its token is deleted/)).toBeVisible();
  await expect(page.getByText(/GitHub confirmed the access was revoked/)).toBeVisible();
  expect(fake.github.calls).toContain("disconnect:false");
  await expect(panel(page).getByRole("button", { name: "Connect GitHub" })).toBeVisible();
  await expect(page.getByText(/^From GitHub/)).toHaveCount(0);
});

test("keeping the entries makes them the person's own", async ({ page }) => {
  const fake = await openProfile(page, { github: github({ connected: true, repos: githubRepos().map((r, i) => ({ ...r, selected: i === 0 })) }) });
  await panel(page).getByRole("button", { name: "Read my repositories again" }).click();
  await expect(page.getByText(/^From GitHub/).first()).toBeVisible({ timeout: 10_000 });
  await panel(page).getByRole("button", { name: "Disconnect GitHub" }).click();
  await page.getByRole("dialog").getByLabel("Keep those entries as mine").check();
  await page.getByRole("dialog").getByRole("button", { name: "Disconnect" }).click();
  expect(fake.github.calls).toContain("disconnect:true");
  await expect(page.getByText("project-1", { exact: true }).first()).toBeVisible();
  await expect(page.getByText(/^From GitHub/)).toHaveCount(0);
});

test("a revoke GitHub did not confirm tells the person where to remove it", async ({ page }) => {
  await openProfile(page, { github: github({ connected: true, repos: githubRepos(), revoked: false }) });
  await panel(page).getByRole("button", { name: "Disconnect GitHub" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Disconnect" }).click();
  await expect(page.getByText(/did not confirm the revoke/)).toBeVisible();
  await expect(page.getByText(/github.com\/settings\/applications/)).toBeVisible();
});

test("places that cannot be connected say why and what to do instead", async ({ page }) => {
  await openProfile(page, { github: github() });
  await panel(page).getByText("Evidence from places that cannot be connected").click();
  await expect(panel(page)).toContainText("LinkedIn does not allow other products to read your profile");
  await expect(panel(page)).toContainText("Anywhere else");
});

test("a sign-in GitHub did not accept says what to do and the way back", async ({ page }) => {
  await openProfile(page, { github: github() });
  await page.goto("/connect/github/callback?code=bad&state=" + "s".repeat(40));
  await expect(page.getByText("GitHub was not connected")).toBeVisible();
  await expect(page.getByText(/Start again from the Connect GitHub button/)).toBeVisible();
  await page.getByRole("link", { name: "Back to your profile" }).click();
  await expect(page).toHaveURL(/\/profile$/);
});

test("declining on GitHub is not an error", async ({ page }) => {
  await openProfile(page, { github: github() });
  await page.goto("/connect/github/callback?error=access_denied");
  await expect(page.getByText(/You chose not to connect GitHub/)).toBeVisible();
});

test("the callback page without a code explains itself", async ({ page }) => {
  await openProfile(page, { github: github() });
  await page.goto("/connect/github/callback");
  await expect(page.getByText(/only for the return from GitHub/)).toBeVisible();
});

for (const scheme of ["light", "dark"] as const) {
  test(`axe: GitHub not connected, connected with repositories, and the disconnect question (${scheme})`, async ({ page }) => {
    await page.emulateMedia({ colorScheme: scheme });
    await openProfile(page, { github: github() });
    await axe(page);
    await page.goto("/profile");
    await page.unrouteAll();
    const fake = await fakeApi(page, { github: github({ connected: true, repos: githubRepos(), sync_state: "failed", sync_error: "GitHub could not be reached just now. Nothing was changed. Try again in a few minutes." }) });
    void fake;
    await page.goto("/profile");
    await expect(panel(page)).toContainText("Connected as asha");
    await axe(page);
    await panel(page).getByRole("button", { name: "Disconnect GitHub" }).click();
    await expect(page.getByRole("dialog", { name: "Disconnect GitHub?" })).toBeVisible();
    await axe(page);
  });
}

test("on a phone nothing scrolls sideways", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await fakeApi(page, { github: github({ connected: true, repos: githubRepos() }) });
  await page.goto("/profile");
  await expect(panel(page)).toContainText("Connected as asha");
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(0);
});
