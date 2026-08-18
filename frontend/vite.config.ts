import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Complete boilerplate — dev server proxies /api and /ws to the backend
// so the frontend can call relative paths in both dev and prod.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true },
      "/ws": { target: "ws://localhost:8000", ws: true },
    },
  },
});
