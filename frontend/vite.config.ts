import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    allowedHosts: ["meta-bot-production-5ec3.up.railway.app"], // your frontend's Railway domain
    proxy: {
      "/api": { target: "https://meta-bot-production-d1da.up.railway.app", changeOrigin: true },
      "/ws": { target: "https://meta-bot-production-d1da.up.railway.app", ws: true },
    },
  },
  preview: {
    allowedHosts: ["meta-bot-production-5ec3.up.railway.app"], // needed if you run `vite preview` too
  },
});