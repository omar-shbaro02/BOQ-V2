import { expect, test } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import { assertReflow, auditAccessibility } from "./accessibility-helpers";

test("operator setup preserves charter authority, five work packages, recipients and reported updates", async ({ page }, testInfo) => {
  test.setTimeout(120_000);
  await page.goto("/setup");
  const create = page.locator("form.project-create-form");
  await create.getByLabel("Company or workspace name").fill("Operator acceptance workspace");
  await create.getByLabel("Project name", { exact: true }).fill("Five-package concrete acceptance");
  await create.getByLabel("Project code").fill("OP-12");
  await create.getByRole("button", { name: "Create project", exact: true }).click();
  await expect(create.getByRole("status")).toContainText("OP-12");
  const projectId = await page.evaluate(() => localStorage.getItem("vai-active-project"));
  expect(projectId).toBeTruthy();
  const workspace = await page.evaluate(() => JSON.parse(localStorage.getItem("vai-project-workspace")!));
  const base = `http://127.0.0.1:8011/api/v1/projects/${projectId}`;
  const headers = { "X-VAI-Actor-ID": workspace.actorId, "X-VAI-Organization-ID": workspace.organizationId };
  const controls = page.getByRole("region", { name: "Project governance setup", exact: true });
  await expect(controls.getByRole("combobox", { name: "Project", exact: true })).toHaveValue(projectId!);
  await controls.getByRole("button", { name: "Load project controls" }).click();
  await expect(controls.getByRole("status")).toContainText("Project controls loaded");
  const wbs = controls.getByRole("region", { name: "Work package setup" });
  for (const [index, name] of ["Foundations", "Columns", "Beams", "Slabs", "Stairs"].entries()) {
    await wbs.getByLabel("Object type").selectOption("WORK_PACKAGE");
    await wbs.getByLabel("Object code").fill(`WP-${index + 1}`);
    await wbs.getByLabel("Object name").fill(name);
    await wbs.getByRole("button", { name: "Create controlled object" }).click();
    await expect(wbs.getByRole("listitem").filter({ hasText: name })).toHaveCount(1);
  }
  const charter = controls.getByRole("region", { name: "Project charter", exact: true });
  await charter.getByLabel("Objectives (one per line)").fill("Deliver concrete scope with traceable evidence");
  await charter.getByLabel("Success criteria (one per line)").fill("Accepted quantities reconcile with BOQ");
  await charter.getByLabel("Delivery strategy").fill("Reviewed phased concrete sequence");
  await charter.getByLabel("Charter authority reference").fill("Synthetic board reference OP-12");
  await charter.getByLabel("Effective from").fill("2026-10-01T09:00");
  await charter.getByRole("button", { name: "Save charter version" }).click();
  await expect(charter).toContainText("DRAFT");
  await charter.getByLabel("Charter review or approval rationale").fill("Reviewed project objectives and boundaries");
  await charter.getByRole("button", { name: "Review charter version 1" }).click();
  await expect(charter.getByRole("button", { name: "Approve charter version 1" })).toBeDisabled();
  // Test-only authority provisioning uses the real public command; it is not a human session.
  const grant = await page.request.post(`${base}/authority-grants`, { headers, data: { actor_id: workspace.actorId, authority_type: "CHARTER_APPROVAL" } });
  expect(grant.status()).toBe(201);
  const grantId = (await grant.json()).id;
  await page.reload();
  await page.getByRole("button", { name: "Load project controls" }).click();
  await expect(controls.getByRole("status")).toContainText("Project controls loaded");
  await charter.getByLabel("My charter approval authority").selectOption(grantId);
  await charter.getByLabel("Charter review or approval rationale").fill("Accountable review of the exact charter version");
  await charter.getByLabel("Charter approval reference").fill("OP-CHARTER-1");
  await charter.getByRole("button", { name: "Approve charter version 1" }).click();
  await expect(charter).toContainText("APPROVED");
  const recipient = controls.getByRole("region", { name: "Stakeholder registry" });
  await recipient.getByLabel("Stakeholder key").fill("CLIENT-PM");
  await recipient.getByLabel("Stakeholder name").fill("Synthetic client reviewer");
  await recipient.getByLabel("Project role").fill("Client PM");
  await recipient.getByLabel("Communication rules (one per line)").fill("Approved reports only; no automatic distribution");
  await recipient.getByLabel("Eligible for approved reports").check();
  await recipient.getByLabel("Effective from").fill("2026-10-01T09:00");
  await recipient.getByRole("button", { name: "Save stakeholder version" }).click();
  await expect(recipient).toContainText("CLIENT-PM · version 1 · ACTIVE");
  const objects = await (await page.request.get(`${base}/controlled-objects`, { headers })).json();
  const source = await page.request.post(`${base}/evidence/items`, { headers, data: { controlled_object_id: objects[0].id, field_name: "physical_progress", value: "80", unit: "m3", measurement_basis: "PHYSICAL_VERIFIED", semantic_state: "REPORTED", truth_type: "REPORTED_CLAIM", as_of: new Date(Date.now() - 300_000).toISOString(), confidence: "0.8" } });
  expect(source.status()).toBe(201);
  const evidenceId = (await source.json()).id;
  await controls.getByRole("button", { name: "Load project controls" }).click();
  await expect(controls.getByRole("status")).toContainText("Project controls loaded");
  const dates = await page.evaluate(() => {
    const cutoff = new Date(Date.now() - 60_000);
    const date = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Beirut", year: "numeric", month: "2-digit", day: "2-digit" }).format(cutoff);
    cutoff.setMinutes(cutoff.getMinutes() - cutoff.getTimezoneOffset());
    return { cutoff: cutoff.toISOString().slice(0, 16), date };
  });
  const daily = controls.getByRole("region", { name: "Daily update", exact: true });
  await daily.getByLabel("Daily update key").fill("DAILY-OP-1");
  await daily.getByLabel("Project reporting date").fill(dates.date);
  await daily.getByLabel("Reporting cutoff").fill(dates.cutoff);
  await daily.getByLabel("Effective from").fill(dates.cutoff);
  await daily.getByLabel("Reported weather").fill("Reported dry");
  await daily.getByLabel("Updated work package").selectOption(objects[0].id);
  await daily.getByLabel("Reported quantity").fill("80");
  await daily.getByLabel("Quantity unit").fill("m3");
  await daily.getByLabel("Supporting evidence (select one or more)").selectOption(evidenceId);
  await daily.getByRole("button", { name: "Record reported daily update" }).click();
  await expect(controls.getByRole("region", { name: "Project context history" })).toContainText("DAILY UPDATE · DAILY-OP-1 · version 1 · REPORTED");
  const provision = async (kind: string) => {
    const response = await page.request.post(`${base}/authority-grants`, { headers, data: { actor_id: workspace.actorId, authority_type: kind } });
    expect(response.status(), await response.text()).toBe(201);
    return (await response.json()).id as string;
  };
  const weightsGrant = await provision("PROGRESS_WEIGHTING_APPROVAL");
  const budgetGrant = await provision("BUDGET_APPROVAL");
  await controls.getByRole("button", { name: "Load project controls" }).click();
  await expect(controls.getByRole("status")).toContainText("Project controls loaded");
  const sourceControls = controls.getByRole("region", { name: "Budget and weighting controls" });
  await sourceControls.getByLabel("Weight source data date").fill(new Date().toISOString().slice(0, 10));
  await sourceControls.getByLabel("Weight source reference").fill("Reviewed BOQ allocation weights OP-12");
  for (let index = 1; index <= 5; index++) await sourceControls.getByLabel(`Weight for WP-${index} (0–1)`, { exact: true }).fill("0.2");
  await sourceControls.getByLabel("Effective from").fill("2026-10-01T09:00");
  await sourceControls.getByRole("button", { name: "Save proposed control source" }).click();
  await expect(controls.getByRole("status")).toContainText("not authorized");
  await sourceControls.getByLabel("My control approval authority").selectOption(weightsGrant);
  await sourceControls.getByLabel("Control approval reference").fill("OP-WEIGHTS-1");
  await sourceControls.getByLabel("Control authorization rationale").fill("Human reviewed five explicit BOQ package weights");
  await sourceControls.getByRole("button", { name: "Authorize selected control source" }).click();
  await expect(controls.getByRole("status")).toContainText("separate human authority route");
  await sourceControls.getByLabel("Control source type").selectOption("BUDGET");
  await sourceControls.getByLabel("Budget proposal amount (USD)").fill("2000");
  await sourceControls.getByLabel("Budget work package").selectOption("WP-1");
  await sourceControls.getByRole("button", { name: "Save proposed control source" }).click();
  await expect(controls.getByRole("status")).toContainText("not authorized");
  await sourceControls.getByLabel("My control approval authority").selectOption(budgetGrant);
  await sourceControls.getByLabel("Control approval reference").fill("OP-BUDGET-1");
  await sourceControls.getByLabel("Control authorization rationale").fill("Reviewed this work package budget and its exact currency and scope");
  await sourceControls.getByRole("button", { name: "Authorize selected control source" }).click();
  await expect(controls.getByRole("status")).toContainText("separate human authority route");
  for (const width of [1280, 320]) {
    await page.setViewportSize({ width, height: 900 });
    await assertReflow(page);
    await auditAccessibility(page, testInfo, `operator-setup-${width}`);
    await mkdir(".test-tmp/operator-setup", { recursive: true });
    await page.screenshot({ path: `.test-tmp/operator-setup/setup-${width}.png`, fullPage: true });
  }
  await page.reload();
  await page.getByRole("button", { name: "Load project controls" }).click();
  await expect(charter).toContainText("APPROVED");
  await expect(wbs.getByRole("listitem")).toHaveCount(5);
  await expect(daily).toContainText("Updates remain reported");

  // Public-API synthetic preconditions for the snapshot composer; this is not a 17-step UI proof.
  const post = async (path: string, data: Record<string, unknown>) => {
    const response = await page.request.post(`${base}${path}`, { headers: { ...headers, "Idempotency-Key": crypto.randomUUID() }, data });
    expect(response.status(), await response.text()).toBe(201);
    return await response.json();
  };
  const today = new Date().toISOString().slice(0, 10);
  const scheduleSource = await post("/authorized-context/versions", { context_type: "SCHEDULE", semantic_state: "PROPOSED", effective_from: "2026-10-01T00:00:00Z", payload: { data_date: today, network_complete: true, activities: objects.map((item: { code: string; name: string }) => ({ code: `A-${item.code}`, name: item.name, controlled_object_code: item.code, planned_start: "2026-10-01", planned_finish: today, progress_basis: "PHYSICAL_VERIFIED", responsible_owner: workspace.actorId, progress_plan: [{ as_of: today, numerator: "200", denominator: "200", unit: "m3", measurement_basis: "PHYSICAL_VERIFIED" }] })) } });
  const scheduleGrant = await provision("CURRENT_SCHEDULE_APPROVAL");
  const schedule = await post("/authorized-context/activate", { source_version_id: scheduleSource.id, authority_grant_id: scheduleGrant, expected_current_context_id: null, approval_reference: "OP-SCHEDULE-1", reason: "Synthetic reviewed source for composer coverage" });
  const observation = new Date().toISOString();
  const inputPairs: Record<string, { planned: string; actual: string }> = {};
  for (const object of objects) {
    const pair: Record<string, string> = {};
    for (const kind of ["PLANNED_AUTHORIZED", "VERIFIED"]) {
      let item = await post("/evidence/items", { controlled_object_id: object.id, field_name: kind === "PLANNED_AUTHORIZED" ? "planned_progress" : "physical_progress", value: kind === "PLANNED_AUTHORIZED" ? "200" : "80", unit: "m3", measurement_basis: "PHYSICAL_VERIFIED", semantic_state: kind === "PLANNED_AUTHORIZED" ? "CURRENT_AUTHORIZED" : "REPORTED", truth_type: kind === "PLANNED_AUTHORIZED" ? "JUDGMENT" : "REPORTED_CLAIM", as_of: observation, confidence: "0.9" });
      if (kind === "VERIFIED") {
        const verified = await post(`/evidence/items/${item.id}/verify`, { method: "Synthetic quantity inspection", outcome: "VERIFIED", rationale: "Separate test-only evidence verification", verified_confidence: "0.95" });
        const items = await (await page.request.get(`${base}/evidence/items`, { headers })).json();
        item = items.find((value: { id: string }) => value.id === verified.result_item_id);
      }
      const measurement = await post("/progress/measurements", { evidence_item_id: item.id, authorized_context_id: kind === "PLANNED_AUTHORIZED" ? schedule.id : null, measurement_kind: kind, numerator: kind === "PLANNED_AUTHORIZED" ? "200" : "80", denominator: "200", unit: "m3" });
      pair[kind === "PLANNED_AUTHORIZED" ? "planned" : "actual"] = measurement.id;
    }
    inputPairs[object.code] = pair as { planned: string; actual: string };
  }
  await page.goto("/progress");
  const composer = page.getByRole("region", { name: "Issue project-control snapshot", exact: true });
  await composer.getByText("Issue project-control snapshot", { exact: true }).click();
  await composer.getByRole("button", { name: "Load snapshot sources" }).click();
  await expect(composer.getByRole("status")).toContainText("Snapshot sources loaded");
  await composer.getByLabel("Authorized progress weights").selectOption({ index: 1 });
  await composer.getByLabel("Authorized snapshot schedule").selectOption(schedule.id);
  for (const object of objects) {
    await composer.getByRole("combobox", { name: `Planned measurement for ${object.code}`, exact: true }).selectOption(inputPairs[object.code].planned);
    await composer.getByRole("combobox", { name: `Actual measurement for ${object.code}`, exact: true }).selectOption(inputPairs[object.code].actual);
  }
  const cutoff = await page.evaluate(() => { const value = new Date(); value.setMinutes(value.getMinutes() - value.getTimezoneOffset()); return value.toISOString().slice(0, 19); });
  await composer.getByLabel("Snapshot reporting cutoff (browser timezone)").fill(cutoff);
  await composer.getByLabel("Health policy version").fill("OP-HEALTH-1");
  await composer.getByLabel("Health policy rationale").fill("Explicit synthetic operator acceptance thresholds");
  await composer.getByLabel("Health policy effective from (browser timezone)").fill("2026-10-01T09:00");
  for (const [label, value] of [["Progress yellow deficit ratio", "0.02"], ["Progress red deficit ratio", "0.05"], ["Schedule yellow exposure (days)", "2"], ["Schedule red exposure (days)", "5"], ["Cost yellow overrun ratio", "0.03"], ["Cost red overrun ratio", "0.1"], ["Evidence red below confidence", "0.5"], ["Evidence green at least confidence", "0.8"], ["Material red package weight", "0.2"], ["Maximum source age (days)", "14"]]) await composer.getByLabel(label, { exact: true }).fill(value);
  await page.setViewportSize({ width: 1280, height: 900 });
  await auditAccessibility(page, testInfo, "snapshot-composer-desktop");
  await page.setViewportSize({ width: 320, height: 900 });
  await assertReflow(page);
  await auditAccessibility(page, testInfo, "snapshot-composer-mobile");
  await composer.getByRole("button", { name: "Issue immutable control snapshot" }).click();
  await expect(composer).toContainText("Snapshot 1 issued");
  await composer.getByRole("link", { name: "Open updated command center" }).click();
  await expect(page.getByRole("heading", { name: "Five-package concrete acceptance", exact: true })).toBeVisible();
  await expect(page.getByText("40.0%", { exact: true }).first()).toBeVisible();
});

test("changing project clears loaded governance context before allowing another command", async ({ page }) => {
  const org = await page.request.post("http://127.0.0.1:8011/api/v1/organizations", { headers: { "X-VAI-Actor-ID": "switch@example.test", "X-VAI-Roles": "ORGANIZATION_ADMIN" }, data: { name: "Project switch acceptance", slug: `switch-${crypto.randomUUID()}` } });
  expect(org.status()).toBe(201);
  const organizationId = (await org.json()).id;
  const headers = { "X-VAI-Actor-ID": "switch@example.test", "X-VAI-Organization-ID": organizationId };
  const projects = [];
  for (const code of ["FIRST", "SECOND"]) {
    const response = await page.request.post(`http://127.0.0.1:8011/api/v1/organizations/${organizationId}/projects`, { headers, data: { code, name: `Scope ${code}`, timezone: "Asia/Beirut", currency: "USD", delivery_model: "DESIGN_BID_BUILD", reporting_cadence: "WEEKLY" } });
    expect(response.status()).toBe(201);
    projects.push(await response.json());
  }
  const object = await page.request.post(`http://127.0.0.1:8011/api/v1/projects/${projects[0].id}/controlled-objects`, { headers, data: { code: "FIRST-ONLY", name: "First project scope", object_type: "WORK_PACKAGE" } });
  expect(object.status()).toBe(201);
  await page.addInitScript(({ organizationId, projectId }) => { localStorage.setItem("vai-project-workspace", JSON.stringify({ actorId: "switch@example.test", organizationId })); localStorage.setItem("vai-active-project", projectId); }, { organizationId, projectId: projects[0].id });
  await page.goto("/setup");
  const controls = page.getByRole("region", { name: "Project governance setup", exact: true });
  await controls.getByRole("button", { name: "Load project controls" }).click();
  await expect(controls).toContainText("FIRST-ONLY");
  await controls.getByRole("combobox", { name: "Project", exact: true }).selectOption(projects[1].id);
  await expect(controls).not.toContainText("FIRST-ONLY");
  await expect(controls.getByRole("button", { name: "Save charter version" })).toBeDisabled();
  await controls.getByRole("button", { name: "Load project controls" }).click();
  await expect(controls.getByRole("status")).toContainText("Project controls loaded");
  await expect(controls).toContainText("Scope SECOND");
  await expect(controls).not.toContainText("FIRST-ONLY");
});
