import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./report-tests",
  outputDir: "../reports/report-ui-artifacts",
  workers: 1,
  retries: 0,
  reporter: [["list"], ["json", { outputFile: "../reports/report-ui.json" }]],
  use: {
    baseURL: "http://127.0.0.1:4175",
    trace: "retain-on-failure",
    screenshot: "off",
    ...(process.env.PW_CHROMIUM
      ? {
          launchOptions: {
            executablePath: process.env.PW_CHROMIUM,
            args: ["--disable-gpu", "--no-zygote"],
          },
        }
      : {}),
  },
  webServer: {
    command: "python3 ../tools/report_server.py",
    url: "http://127.0.0.1:4175/index.html",
    reuseExistingServer: false,
  },
  projects: [
    {
      name: "report-desktop",
      use: { viewport: { width: 1440, height: 1000 } },
    },
    {
      name: "report-mobile",
      use: {
        viewport: { width: 390, height: 844 },
        isMobile: true,
        hasTouch: true,
      },
    },
  ],
});
