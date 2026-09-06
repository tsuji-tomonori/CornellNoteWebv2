import { defineConfig } from "vitest/config";
export default defineConfig({
  server: {
    host: "0.0.0.0",
    port: 5173,
    proxy: {
      "/api": {
        target: process.env.API_TARGET || "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
  test: {
    include: ["src/**/*.test.ts"],
    coverage: {
      provider: "v8",
      reporter: ["text", "html", "json"],
      reportsDirectory: "../reports/frontend-coverage",
      include: ["src/**/*.{ts,tsx}"],
      exclude: ["src/**/*.test.ts"],
    },
  },
});
