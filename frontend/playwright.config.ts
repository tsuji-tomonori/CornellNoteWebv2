import { defineConfig, devices } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 45000,
  reporter: [
    ["list"],
    ["json", { outputFile: "../reports/playwright.json" }],
    ["html", { outputFolder: "../reports/playwright", open: "never" }],
  ],
  use: {
    baseURL: process.env.BASE_URL || "http://127.0.0.1:5173",
    trace: "retain-on-failure",
    screenshot: "off",
    locale: "ja-JP",
    ...(process.env.PW_CHROMIUM
      ? {
          launchOptions: {
            executablePath: process.env.PW_CHROMIUM,
            args: ["--disable-gpu", "--no-zygote"],
          },
        }
      : {}),
  },
  projects: [
    {
      name: "desktop",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1440, height: 1000 },
      },
    },
    {
      name: "mobile",
      use: {
        ...devices["Pixel 7"],
      },
    },
  ],
});
