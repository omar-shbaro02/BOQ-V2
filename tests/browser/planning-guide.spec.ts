import { expect, test } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import { auditAccessibility, assertReflow } from "./accessibility-helpers";

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("vai-project-workspace", JSON.stringify({ actorId: "browser@example.test", organizationId: "00000000-0000-0000-0000-000000000065" }));
    localStorage.setItem("vai-active-project", "00000000-0000-0000-0000-000000000066");
  });
});

test("guided upload explains the inputs, fills the document name and hides optional complexity", async ({ page }, testInfo) => {
  await page.goto("/bootstrap/advanced");
  await expect(page.getByRole("combobox", { name: "Project", exact: true })).toHaveValue("00000000-0000-0000-0000-000000000066");
  await page.getByRole("button", { name: "Load project", exact: true }).click();
  await expect(page.locator(".workbench-message")).toContainText("Project connected");
  await expect(page.getByRole("heading", { name: "Upload your BOQ", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Set working days and task links", exact: true })).toHaveCount(0);
  await page.getByLabel("BOQ file (Excel or PDF)").setInputFiles(".test-tmp/browser-boq.xlsx");
  await expect(page.getByRole("textbox", { name: "Document name or revision", exact: true })).toHaveValue("browser-boq.xlsx");
  await expect(page.getByRole("combobox", { name: "Prior BOQ version (revision only)" })).toHaveCount(0);
  await expect(page.getByRole("textbox", { name: "Governed inputs JSON" })).toHaveCount(0);
  await auditAccessibility(page, testInfo, "guided-boq-upload");
  await mkdir(".test-tmp/planning-guide", { recursive: true });
  await page.evaluate(() => { (document.activeElement as HTMLElement)?.blur(); window.scrollTo(0, 0); });
  await page.screenshot({ path: ".test-tmp/planning-guide/upload-desktop.png", fullPage: true });
  await page.setViewportSize({ width: 320, height: 900 });
  await assertReflow(page);
  await auditAccessibility(page, testInfo, "guided-boq-mobile");
  await page.evaluate(() => { (document.activeElement as HTMLElement)?.blur(); window.scrollTo(0, 0); });
  await page.screenshot({ path: ".test-tmp/planning-guide/upload-mobile.png", fullPage: true });
});

test("viewing planning stages does not invent a calendar, submit inputs or grant authority", async ({ page }) => {
  const posts: string[] = [];
  page.on("request", request => { if (request.method() === "POST") posts.push(request.url()); });
  await page.goto("/bootstrap/advanced");
  await expect(page.getByRole("combobox", { name: "Project", exact: true })).toHaveValue("00000000-0000-0000-0000-000000000066");
  await page.getByRole("button", { name: "Load project", exact: true }).click();
  await expect(page.locator(".workbench-message")).toContainText("Project connected");
  const stages = page.getByRole("navigation", { name: "Schedule preparation stages" });
  await stages.getByRole("button").nth(2).click();
  const calendar = page.locator('[data-bootstrap-step="07"]');
  await expect(calendar.getByRole("spinbutton", { name: "Working hours per day" })).toHaveValue("");
  for (const day of ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]) await expect(calendar.getByLabel(day, { exact: true })).not.toBeChecked();
  await expect(calendar.getByRole("button", { name: "Create logic", exact: true })).toBeDisabled();
  await stages.getByRole("button").nth(3).click();
  await expect(page.getByRole("button", { name: "Authorize schedule", exact: true })).toBeDisabled();
  await expect(page.getByRole("textbox", { name: "Authority grant reference" })).toHaveCount(0);
  expect(posts).toEqual([]);
});
