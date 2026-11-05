import { defineConfig } from "@playwright/test";

// Browser checks run against the production build served by `vite preview`, so they test what ships.
// CI installs Playwright's Chromium. On a developer machine set PW_CHANNEL=msedge (or chrome) to
// reuse the browser already installed instead of downloading another one.
const channel = process.env.PW_CHANNEL;

export default defineConfig({
  testDir: "e2e",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"]],
  use: {
    baseURL: "http://localhost:4173",
    // Pages rise and fade in. A scan that lands mid-animation reads half-faded text as low contrast and
    // a click lands where the element is about to be, so tests run with motion reduced. The base styles
    // already stop all animation under this preference.
    reducedMotion: "reduce",
    ...(channel ? { channel } : {}),
    trace: "retain-on-failure",
  },
  webServer: {
    command: "npm run preview -- --port 4173 --strictPort",
    url: "http://localhost:4173/design",
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
  },
});
