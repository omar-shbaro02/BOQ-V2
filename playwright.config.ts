import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/browser",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  expect: { timeout: 15_000 },
  use: { baseURL: "http://127.0.0.1:3011", trace: "retain-on-failure", channel: process.env.PLAYWRIGHT_CHANNEL },
  webServer: [
    {
      command: process.platform === "win32" ? ".venv\\Scripts\\python.exe scripts/e2e_api.py" : ".venv/bin/python scripts/e2e_api.py",
      url: "http://127.0.0.1:8011/health",
      reuseExistingServer: false,
    },
    {
      command: "node apps/web/node_modules/next/dist/bin/next dev apps/web --hostname 127.0.0.1 --port 3011",
      url: "http://127.0.0.1:3011/bootstrap",
      env: { NEXT_PUBLIC_VAI_API_URL: "http://127.0.0.1:8011" },
      timeout: 120_000,
      reuseExistingServer: false,
    },
  ],
});
