import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/browser-oidc", workers: 1, retries: 0,
  expect: { timeout: 15_000 },
  use: { baseURL: "https://127.0.0.1:3012", ignoreHTTPSErrors: true, channel: process.env.PLAYWRIGHT_CHANNEL, trace: "retain-on-failure" },
  webServer: {
    command: process.platform === "win32" ? ".venv\\Scripts\\python.exe scripts/e2e_oidc.py" : ".venv/bin/python scripts/e2e_oidc.py",
    url: "https://127.0.0.1:3012", ignoreHTTPSErrors: true, timeout: 180_000, reuseExistingServer: false,
  },
});
