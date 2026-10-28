import { expect, test } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import { auditAccessibility, assertReflow } from "./accessibility-helpers";

const journey = ["/setup", "/bootstrap", "/schedule", "/evidence", "/progress", "/cost", "/signals", "/cases", "/forecast", "/impact", "/orchestration", "/decision-center"];

for (const width of [1280, 320]) {
  test(`guided navigation follows the full working order at ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/");
    await page.getByRole("region", { name: "Workflow orientation" }).getByRole("link", { name: "Start: Projects" }).click();
    for (const [index, route] of journey.entries()) {
      await expect(page).toHaveURL(new RegExp(`${route}$`));
      const guide = page.getByRole("region", { name: "Workflow orientation" });
      const handoff = page.getByRole("region", { name: "Next workflow step" });
      await expect(guide).toContainText(`${String(index + 1).padStart(2, "0")} / 12`);
      await expect(handoff).toContainText("moving to another page does not complete or approve this step");
      const next = handoff.locator(".workflow-next");
      await expect(next).toHaveAttribute("href", journey[index + 1] ?? "/cases");
      await expect(guide.locator(".workflow-next")).toHaveAttribute("href", journey[index + 1] ?? "/cases");
      await assertReflow(page);
      if (route === "/setup") {
        await auditAccessibility(page, testInfo, `guided-setup-${width}`);
        await mkdir(".test-tmp/workflow", { recursive: true });
        await page.screenshot({ path: `.test-tmp/workflow/setup-${width}.png`, fullPage: true });
      }
      await next.click();
    }
    await expect(page).toHaveURL(/\/cases$/);
  });
}

test("planning branches retain orientation and expose the authorization route", async ({ page }) => {
  for (const route of ["/bootstrap", "/bootstrap/advanced", "/bootstrap/schedule-assistant"]) {
    await page.goto(route);
    const guide = page.getByRole("region", { name: "Workflow orientation" });
    await expect(guide).toContainText("02 / 12");
    await expect(guide.locator(".workflow-next")).toHaveAttribute("href", "/schedule");
    if (route !== "/bootstrap/advanced") {
      await expect(page.getByRole("region", { name: "Next workflow step" }).getByRole("link", { name: "Review & authorize schedule" })).toHaveAttribute("href", "/bootstrap/advanced");
    }
    await expect(page.locator('.sidebar-nav a[aria-current="page"]')).toHaveAttribute("href", "/bootstrap");
  }
});
