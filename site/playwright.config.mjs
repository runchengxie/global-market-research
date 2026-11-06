import { defineConfig } from "@playwright/test";
import { tmpdir } from "node:os";
import { join } from "node:path";

const port=Number(process.env.PAGES_TEST_PORT || 4397);
export default defineConfig({
  testDir: "./tests",
  testMatch: "**/*.spec.mjs",
  outputDir: process.env.PAGES_TEST_OUTPUT || join(tmpdir(), "quant-competition-pages-tests"),
  reporter: "list",
  use: { baseURL: `http://127.0.0.1:${port}`, browserName: "chromium" },
  webServer: {
    command: `npm run preview -- --ignore-lock --host 127.0.0.1 --port ${port}`,
    url: `http://127.0.0.1:${port}/global-market-research/`,
    reuseExistingServer: false,
  },
});
