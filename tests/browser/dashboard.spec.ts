import { expect, test, type Page } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import { auditAccessibility, assertReflow } from "./accessibility-helpers";

const projects = [
  { id: "dashboard-alpha", code: "ZTWR-002", name: "Zeino Tower", timezone: "Asia/Beirut" },
  { id: "dashboard-beta", code: "WEST-01", name: "West Residence", timezone: "Asia/Beirut" },
];

async function fixture(page: Page, { queueFailure = false, delayedAlpha = false } = {}) {
  await page.addInitScript(() => { localStorage.setItem("vai-project-workspace", JSON.stringify({ actorId: "dashboard@test", organizationId: "dashboard-org" })); localStorage.removeItem("vai-active-project"); });
  await page.route("**/api/v1/**", async route => {
    const url = new URL(route.request().url());
    let body: unknown = [];
    if (url.pathname.endsWith("/auth/session")) body = { mode: "DEVELOPMENT", actor_id: null, organization_id: null };
    else if (url.pathname.endsWith("/projects")) body = projects;
    else if (url.pathname.endsWith("/decision-center/queue")) {
      if (queueFailure) { await route.fulfill({ status: 503, json: { detail: "Unavailable" } }); return; }
      const alpha = url.pathname.includes("dashboard-alpha");
      body = [{ case_id: alpha ? "alpha-case" : "beta-case", case_number: alpha ? "DC-014" : "DC-021", title: alpha ? "Foundation pour needs verification" : "Review west access", priority_band: alpha ? "HIGH" : null, governance_state: "HUMAN_REVIEW_REQUIRED", lifecycle: "OPEN", next_action: "VERIFY_EVIDENCE", next_deadline: "2026-01-01T08:00:00Z", owner_actor_id: "Planner" }];
    } else if (url.pathname.endsWith("/evidence/artifacts") && url.pathname.includes("dashboard-alpha")) body = [
      { id: "boq", original_filename: "zeino-boq.pdf", source_type: "BOQ_UPLOAD", scan_result: "CLEAN", received_at: "2026-10-01T10:00:00Z" },
      { id: "schedule", original_filename: "zeino-schedule.xlsx", source_type: "AI_SCHEDULE_EXPORT", scan_result: "CLEAN", received_at: "2026-10-02T10:00:00Z" },
    ];
    if (delayedAlpha && url.pathname.includes("dashboard-alpha") && url.pathname.includes("snapshots")) await new Promise(resolve => setTimeout(resolve, 250));
    await route.fulfill({ json: body });
  });
}

test("command center opens an available project and directs work without invented performance", async ({ page }, testInfo) => {
  await fixture(page);
  await page.goto("/");
  await expect(page.getByRole("combobox", { name: "Active project" })).toHaveValue("dashboard-alpha");
  await expect(page.getByRole("region", { name: "Recommended next step" })).toContainText("1 case needs your attention");
  await expect(page.getByRole("link", { name: "Review priority cases" })).toHaveAttribute("href", "/decision-center");
  await expect(page.getByRole("region", { name: "Project summary" })).toContainText("Not issued");
  await expect(page.getByRole("heading", { name: "Management attention: UNKNOWN" })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Foundation pour needs verification", exact: true })).toBeVisible();
  await expect(page.getByText("Overdue ·", { exact: false })).toBeVisible();
  await expect(page.getByText("Proposal saved · authorization outstanding")).toBeVisible();
  expect(await page.evaluate(() => localStorage.getItem("vai-active-project"))).toBe("dashboard-alpha");
  await mkdir(".test-tmp/command-center", { recursive: true });
  await page.screenshot({ path: ".test-tmp/command-center/desktop.png", fullPage: true });
  await auditAccessibility(page, testInfo, "command-center-ready");
  await page.setViewportSize({ width: 320, height: 900 });
  await auditAccessibility(page, testInfo, "command-center-mobile");
  await assertReflow(page);
  await page.screenshot({ path: ".test-tmp/command-center/mobile.png", fullPage: true });
});

test("command center isolates project changes and ignores late responses", async ({ page }) => {
  await fixture(page, { delayedAlpha: true });
  await page.goto("/");
  const selector = page.getByRole("combobox", { name: "Active project" });
  await expect(selector).toHaveValue("dashboard-alpha");
  await selector.selectOption("dashboard-beta");
  await expect(page.getByRole("link", { name: "Review west access", exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "Foundation pour needs verification", exact: true })).toHaveCount(0);
  await expect(page.getByRole("region", { name: "Recommended next step" })).toContainText("Start with your project plan");
  expect(await page.evaluate(() => localStorage.getItem("vai-active-project"))).toBe("dashboard-beta");
});

test("a failed queue is shown as unavailable while other project records remain useful", async ({ page }) => {
  await fixture(page, { queueFailure: true });
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Decision cases unavailable" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Open decision cases", exact: false })).toContainText("Unavailable");
  await expect(page.getByRole("region", { name: "Recommended next step" })).toContainText("Your schedule is ready for review");
  await expect(page.getByRole("heading", { name: "No open decision cases" })).toHaveCount(0);
  await expect(page.getByText("missing results are not counted as zero", { exact: false })).toBeVisible();
});
