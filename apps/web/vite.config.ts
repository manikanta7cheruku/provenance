import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Inside Docker the API is reachable as http://api:8000 (set by compose.yaml).
const apiTarget = process.env.VITE_API_PROXY_TARGET ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    // Windows bind mounts do not deliver file-change events into containers.
    watch: { usePolling: true, interval: 300 },
    proxy: { "/api": { target: apiTarget, changeOrigin: true } },
  },
});
