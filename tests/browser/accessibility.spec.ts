import { expect, test } from "@playwright/test";
import { auditAccessibility as audit } from "./accessibility-helpers";

const projectId = "00000000-0000-0000-0000-000000000066";
const organizationId = "00000000-0000-0000-0000-000000000065";
const routes = ["/", "/setup", "/bootstrap", "/bootstrap/advanced", "/bootstrap/schedule-assistant", "/decision-center", "/evidence", "/signals", "/cases", "/progress", "/schedule", "/cost", "/forecast", "/impact", "/orchestration"];

test.beforeEach(async ({ page }) => {
  await page.addInitScript(({ projectId, organizationId }) => {
    localStorage.setItem("vai-project-workspace", JSON.stringify({ actorId: "browser@example.test", organizationId }));
    localStorage.setItem("vai-active-project", projectId);
  }, { projectId, organizationId });
});

for (const width of [1280, 320]) for (const route of routes) {
  test(`WCAG automated checks ${width}px: ${route}`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 900 });
    await page.goto(route);
    await expect(page.getByText("Local evaluation", { exact: true })).toBeVisible();
    await expect(page.locator("main h1")).toBeVisible();
    await audit(page, testInfo, `${width}-${route.replaceAll("/", "_")}`);
    if (width === 320) expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
  });
}

test("keyboard skip link reaches visible main content", async ({ page }) => {
  await page.goto("/decision-center");
  await expect(page.getByText("Local evaluation", { exact: true })).toBeVisible();
  await page.keyboard.press("Tab");
  const skip = page.getByRole("link", { name: "Skip to main content" });
  await expect(skip).toBeFocused();
  await expect(skip).toBeInViewport();
  await page.keyboard.press("Enter");
  await expect(page.locator("#main-content")).toBeFocused();
  expect(await page.locator("#main-content").evaluate((element) => getComputedStyle(element).outlineStyle)).not.toBe("none");
});

test("mobile navigation confines focus, closes with Escape, and restores its opener", async ({ page }, testInfo) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.setViewportSize({ width: 320, height: 900 });
  await page.goto("/decision-center");
  await expect(page.getByText("Local evaluation", { exact: true })).toBeVisible();
  await expect(page.locator(".app-sidebar")).not.toBeVisible();
  const menu = page.getByRole("button", { name: "Open navigation" });
  await menu.focus();
  await page.keyboard.press("Enter");
  const dialog = page.getByRole("dialog", { name: "Primary navigation" });
  await expect(dialog).toBeVisible();
  expect(await dialog.evaluate((element) => getComputedStyle(element).transitionDuration)).toBe("0s");
  await expect(dialog.getByRole("button", { name: "Close navigation" })).toBeFocused();
  await page.keyboard.press("Shift+Tab");
  await expect(dialog.locator(".brand")).toBeFocused();
  await page.keyboard.press("Shift+Tab");
  await expect(dialog.getByRole("link", { name: "Decision queue", exact: true })).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(dialog.locator(".brand")).toBeFocused();
  await audit(page, testInfo, "mobile-navigation-open");
  await page.keyboard.press("Escape");
  await expect(menu).toBeFocused();
  await expect(menu).toHaveAttribute("aria-expanded", "false");
  await expect(page.locator(".app-sidebar")).not.toBeVisible();
  await page.keyboard.press("Tab");
  expect(await page.locator(".app-sidebar").evaluate((element) => element.contains(document.activeElement))).toBe(false);
});

test("loaded queue, filters, and expanded report history remain accessible", async ({ page }, testInfo) => {
  await page.goto("/decision-center");
  await expect(page.getByRole("combobox", { name: "Project", exact: true })).toHaveValue(projectId);
  await page.getByRole("button", { name: "Load governed queue" }).click();
  await expect(page.getByRole("row").filter({ hasText: "DC-E2E-001" })).toBeVisible();
  await page.locator("details").first().locator("summary").click();
  await audit(page, testInfo, "loaded-decision-queue");
  await page.setViewportSize({ width: 320, height: 900 });
  await audit(page, testInfo, "loaded-decision-queue-mobile");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
  const tableRegion = page.getByRole("region", { name: "Decision queue table" });
  await tableRegion.focus();
  await page.keyboard.press("ArrowRight");
  await expect.poll(() => tableRegion.evaluate((element) => element.scrollLeft)).toBeGreaterThan(0);
});

test("loaded case detail and human governance forms remain accessible", async ({ page }, testInfo) => {
  await page.goto("/cases");
  await expect(page.getByRole("combobox", { name: "Project", exact: true })).toHaveValue(projectId);
  await page.getByRole("button", { name: "Load cases", exact: true }).click();
  await page.getByRole("button", { name: /DC-E2E-001/ }).click();
  await expect(page.getByRole("heading", { name: "Human governance and response lifecycle" })).toBeVisible();
  await audit(page, testInfo, "loaded-case-governance");
  await page.setViewportSize({ width: 320, height: 900 });
  await audit(page, testInfo, "loaded-case-governance-mobile");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
});

test("loading project choices cannot submit a missing project", async ({ page }) => {
  let release!: () => void;
  const ready = new Promise<void>((resolve) => { release = resolve; });
  await page.route("**/organizations/*/projects", async (route) => { await ready; await route.continue(); });
  const missingProjects: string[] = [];
  page.on("request", (request) => { if (/\/projects\/(null|undefined)\//.test(request.url())) missingProjects.push(request.url()); });
  await page.goto("/decision-center");
  await expect(page.getByText("Local evaluation", { exact: true })).toBeVisible();
  const project = page.getByRole("combobox", { name: "Project", exact: true });
  try {
    await expect(project).toHaveValue("");
    await page.getByRole("button", { name: "Load governed queue" }).click();
    expect(await project.evaluate((element: HTMLSelectElement) => element.validity.valueMissing)).toBe(true);
    await expect(page.getByText("Report and presentation history", { exact: true })).toHaveCount(0);
    expect(missingProjects).toEqual([]);
  } finally { release(); }
  await expect(project).toHaveValue(projectId);
  await page.getByRole("button", { name: "Load governed queue" }).click();
  await expect(page.getByRole("row").filter({ hasText: "DC-E2E-001" })).toBeVisible();
  expect(missingProjects).toEqual([]);
});
