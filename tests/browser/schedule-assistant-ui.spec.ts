import { expect, test } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import { auditAccessibility, assertReflow } from "./accessibility-helpers";

test("schedule assistant has readable controls and retains a proposal for repeat download", async ({ page }, testInfo) => {
  let calls = 0;
  let finish!: () => void;
  const ready = new Promise<void>(resolve => { finish = resolve; });
  await page.route("**/api/v1/ms-project/revise-with-ai", async route => {
    calls++;
    expect(route.request().postDataBuffer()?.includes(Buffer.from("Delay the concrete pour by five working days"))).toBe(true);
    await ready;
    await route.fulfill({ contentType: "application/zip", body: Buffer.from("PK-SYNTHETIC-UI-DOWNLOAD-FIXTURE") });
  });
  await page.goto("/bootstrap/schedule-assistant");
  await expect(page.getByRole("heading", { name: "Propose a schedule change" })).toBeVisible();
  const nav = page.getByRole("navigation", { name: "BOQ to schedule navigation" });
  await expect(nav.locator('[aria-current="page"]')).toContainText("Schedule assistant");
  await page.getByLabel("Upload the current schedule", { exact: false }).setInputFiles({ name: "reviewed-schedule.xlsx", mimeType: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", buffer: Buffer.from("SYNTHETIC-UI-INPUT") });
  const request = page.getByRole("textbox", { name: "Describe the requested change", exact: false });
  await request.fill("Delay the concrete pour by five working days. Preserve task IDs and scope, and identify successor impacts.");
  expect(await request.evaluate(element => element.clientHeight)).toBeGreaterThanOrEqual(180);
  await expect(page.getByText("Schedule selected · ready for your request")).toBeVisible();
  await auditAccessibility(page, testInfo, "schedule-assistant-desktop");
  await mkdir(".test-tmp/schedule-assistant", { recursive: true });
  await page.evaluate(() => { (document.activeElement as HTMLElement)?.blur(); window.scrollTo(0, 0); });
  await page.screenshot({ path: ".test-tmp/schedule-assistant/desktop.png", fullPage: true });
  await page.setViewportSize({ width: 320, height: 900 });
  await assertReflow(page);
  await auditAccessibility(page, testInfo, "schedule-assistant-mobile");
  await page.screenshot({ path: ".test-tmp/schedule-assistant/mobile.png", fullPage: true });
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Create schedule proposal" }).click();
  await expect(request).toBeDisabled();
  await expect(page.getByRole("button", { name: "Preparing your proposal" })).toBeDisabled();
  finish();
  expect((await download).suggestedFilename()).toBe("proposed_schedule_change.zip");
  await expect(page.locator(".sc-feedback-success").getByRole("status")).toContainText("Your proposal package is ready");
  const repeated = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download proposal again" }).click();
  expect((await repeated).suggestedFilename()).toBe("proposed_schedule_change.zip");
  expect(calls).toBe(1);
  await request.fill("New planning request with different constraints.");
  await expect(page.getByRole("button", { name: "Download proposal again" })).toHaveCount(0);
});

test("schedule assistant explains validation failures and preserves the user's inputs", async ({ page }) => {
  await page.route("**/api/v1/ms-project/revise-with-ai", route => route.fulfill({ status: 422, json: { detail: [{ msg: "Schedule must contain the six required columns" }] } }));
  await page.goto("/bootstrap/schedule-assistant");
  await page.getByLabel("Upload the current schedule", { exact: false }).setInputFiles({ name: "reviewed-schedule.xlsx", mimeType: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", buffer: Buffer.from("SYNTHETIC-UI-INPUT") });
  const request = page.getByRole("textbox", { name: "Describe the requested change", exact: false });
  await request.fill("Review the proposed sequence without changing scope.");
  await page.getByRole("button", { name: "Create schedule proposal" }).click();
  await expect(page.locator(".sc-feedback-error")).toContainText("Schedule must contain the six required columns");
  await expect(request).toHaveValue("Review the proposed sequence without changing scope.");
  await expect(page.getByRole("button", { name: "Create schedule proposal" })).toBeEnabled();
});
