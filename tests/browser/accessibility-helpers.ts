import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, type TestInfo } from "@playwright/test";
import { mkdir, writeFile } from "node:fs/promises";

export async function auditAccessibility(page: Page, testInfo: TestInfo, name: string) {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]).analyze();
  await mkdir(".test-tmp/accessibility", { recursive: true });
  await writeFile(`.test-tmp/accessibility/${name}.json`, JSON.stringify(results, null, 2));
  await testInfo.attach("accessibility.json", { body: JSON.stringify(results, null, 2), contentType: "application/json" });
  if (["mobile-navigation-open", "loaded-decision-queue", "loaded-case-governance-mobile", "snapshot-health", "snapshot-health-mobile"].includes(name)) {
    await page.screenshot({ path: `.test-tmp/accessibility/${name}.png` });
  }
  expect(results.violations.map(({ id, impact, nodes }) => ({ id, impact, nodes: nodes.map(({ target, failureSummary }) => ({ target, failureSummary })) }))).toEqual([]);
}

export async function assertReflow(page: Page) {
  const layout = await page.evaluate(() => ({
    width: window.innerWidth,
    scrollWidth: document.documentElement.scrollWidth,
    outliers: Array.from(document.querySelectorAll("main *")).flatMap((element) => {
      const rectangle = element.getBoundingClientRect();
      if (rectangle.right <= window.innerWidth + 1 || !rectangle.width || getComputedStyle(element).visibility === "hidden") return [];
      return [{ tag: element.tagName, className: element.className, right: rectangle.right, width: rectangle.width }];
    }).slice(0, 12),
  }));
  expect(layout.scrollWidth, JSON.stringify(layout)).toBeLessThanOrEqual(layout.width + 1);
}
