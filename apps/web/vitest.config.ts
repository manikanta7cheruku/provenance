import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// Unit and component tests run in jsdom. Anything that needs real layout, focus management on the
// native <dialog> or computed contrast is covered by the browser tests in e2e/ instead.
export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.{ts,tsx}"],
    setupFiles: ["src/test-setup.ts"],
    css: false,
  },
});
