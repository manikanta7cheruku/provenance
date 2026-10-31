import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

// The real product screens, with the API replaced by fixed responses, so the design tokens are
// checked on every screen that exists and not only on the gallery.
const WCAG_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];
const CONFIG = { signup_mode: "invite", email_verification_required: false };
const USER = { id: "11111111-1111-4111-8111-111111111111", email: "admin@example.com", role: "ADMIN", email_verified: true };
const STATUS = {
  service: "provenance-api",
  version: "0.1.0",
  environment: "test",
  ready: true,
  checks: { database: "ok", migrations: "ok" },
};
const NOW = "2026-10-30T09:00:00Z";
const RUNS = {
  items: [
    { id: "r1", workflow_type: "demo", workflow_label: "Demo workflow", ui_state: "completed", created_at: NOW, started_at: NOW, finished_at: NOW, duration_ms: 1800 },
    { id: "r2", workflow_type: "demo", workflow_label: "Demo workflow", ui_state: "retrying", created_at: NOW, started_at: NOW, finished_at: null, duration_ms: null },
    { id: "r3", workflow_type: "demo", workflow_label: "Demo workflow", ui_state: "permanently_failed", created_at: NOW, started_at: NOW, finished_at: NOW, duration_ms: 900 },
  ],
  total: 3,
  limit: 25,
  offset: 0,
};
const ADMIN_USERS = {
  items: [
    { ...USER, is_active: true, created_at: NOW, last_seen_at: NOW, active_sessions: 1, profile_entries_count: 0, runs_count: 3 },
    { ...USER, id: "22222222-2222-4222-8222-222222222222", email: "student@example.com", role: "USER", is_active: false, created_at: NOW, last_seen_at: null, active_sessions: 0, profile_entries_count: 4, runs_count: 0 },
  ],
  total: 2,
  limit: 25,
  offset: 0,
};

async function mockApi(page: Page, authenticated: boolean) {
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    const json = (body: unknown) => route.fulfill({ json: body });
    if (path === "/api/v1/status") return json(STATUS);
    if (path === "/api/v1/auth/session") {
      return json({ authenticated, user: authenticated ? USER : null, csrf_token: authenticated ? "token" : null, config: CONFIG });
    }
    if (path === "/api/v1/runs") return json(RUNS);
    if (path === "/api/v1/admin/users") return json(ADMIN_USERS);
    return route.fulfill({ status: 404, json: { detail: "not mocked" } });
  });
}

const SIGNED_OUT = ["/signin", "/signup", "/forgot-password"];
const SIGNED_IN = ["/runs", "/settings", "/admin/users"];

for (const theme of ["light", "dark"] as const) {
  for (const path of SIGNED_OUT) {
    test(`axe: ${path} is accessible when signed out (${theme})`, async ({ page }) => {
      await page.addInitScript((value) => window.localStorage.setItem("pv-theme", value), theme);
      await mockApi(page, false);
      await page.goto(path);
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      const results = await new AxeBuilder({ page }).withTags(WCAG_TAGS).analyze();
      expect(results.violations.map((v) => ({ id: v.id, nodes: v.nodes.slice(0, 2).map((n) => n.target.join(" ")) }))).toEqual([]);
    });
  }
  for (const path of SIGNED_IN) {
    test(`axe: ${path} is accessible when signed in (${theme})`, async ({ page }) => {
      await page.addInitScript((value) => window.localStorage.setItem("pv-theme", value), theme);
      await mockApi(page, true);
      await page.goto(path);
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      await expect(page.getByRole("navigation", { name: "Primary" })).toBeVisible();
      const results = await new AxeBuilder({ page }).withTags(WCAG_TAGS).analyze();
      expect(results.violations.map((v) => ({ id: v.id, nodes: v.nodes.slice(0, 2).map((n) => n.target.join(" ")) }))).toEqual([]);
    });
  }
}

test("the theme control in the shell changes the whole application and is remembered", async ({ page }) => {
  await mockApi(page, true);
  await page.goto("/runs");
  await page.getByRole("radio", { name: "Dark" }).check({ force: true });
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.goto("/settings");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await expect(page.getByRole("radio", { name: "Dark" })).toBeChecked();
});
