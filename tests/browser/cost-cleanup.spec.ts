import { expect, test, type Page } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import { auditAccessibility, assertReflow } from "./accessibility-helpers";

async function fixture(page:Page, withRecord=false) {
  let saved:unknown;
  let records=withRecord ? [{id:"record-a",record_kind:"ACTUAL",amount:"1250",currency:"USD",reporting_period_start:"2026-11-01",reporting_period_end:"2026-11-02",commercial_effect:"NONE",truth_type:"REPORTED",controlled_object_id:"package-a"}] : [];
  await page.addInitScript(()=>{localStorage.setItem("vai-project-workspace",JSON.stringify({actorId:"cost@test",organizationId:"cost-org"}));localStorage.setItem("vai-active-project","cost-a");});
  await page.route("**/api/v1/**",async route=>{
    const path=new URL(route.request().url()).pathname;
    if(path.endsWith("/auth/session")) {await route.fulfill({json:{mode:"DEVELOPMENT"}});return;}
    if(path.endsWith("/projects")) {await route.fulfill({json:[{id:"cost-a",code:"A",name:"Tower"},{id:"cost-b",code:"B",name:"Residence"}]});return;}
    if(path.endsWith("/cost/budget")) {await route.fulfill({status:404,json:{detail:"Current authorized budget not found"}});return;}
    if(path.endsWith("/cost/records")) {
      if(route.request().method()==="POST") {saved=route.request().postDataJSON();records=[{...saved as typeof records[number],id:"new-record",truth_type:"REPORTED",controlled_object_id:"package-a"}];await route.fulfill({status:201,json:records[0]});return;}
      await route.fulfill({json:records});return;
    }
    await route.fulfill({json:[]});
  });
  return ()=>saved;
}

test("cost page removes empty blocks and saves an evidence-bound record with optional details collapsed",async({page},testInfo)=>{
  const saved=await fixture(page);await page.goto("/cost");
  await expect(page.getByRole("combobox",{name:"Project",exact:true})).toHaveValue("cost-a");
  await expect(page.getByRole("heading",{name:"Authorized budget"})).toHaveCount(0);
  await expect(page.getByRole("heading",{name:"Visible policy"})).toHaveCount(0);
  await expect(page.getByRole("heading",{name:"Cost ledger"})).toHaveCount(0);
  await page.getByRole("button",{name:"Load cost controls",exact:true}).click();
  await expect(page.getByRole("button",{name:"Save cost record",exact:true})).toBeEnabled();
  await expect(page.getByRole("heading",{name:"Saved cost records"})).toHaveCount(0);
  await expect(page.getByLabel("Commercial effect",{exact:true})).toBeHidden();
  await auditAccessibility(page,testInfo,"cost-cleanup-desktop");
  await mkdir(".test-tmp/cost-cleanup",{recursive:true});
  await page.evaluate(()=>{(document.activeElement as HTMLElement)?.blur();window.scrollTo(0,0);});
  await page.screenshot({path:".test-tmp/cost-cleanup/desktop.png",fullPage:true});
  await page.setViewportSize({width:320,height:900});await assertReflow(page);await auditAccessibility(page,testInfo,"cost-cleanup-mobile");
  await page.screenshot({path:".test-tmp/cost-cleanup/mobile.png",fullPage:true});
  await page.getByLabel("Supporting evidence reference").fill("evidence-a");
  await page.getByLabel("Amount",{exact:true}).fill("1250");
  await page.getByLabel("Period start",{exact:true}).fill("2026-11-01");
  await page.getByLabel("Period end",{exact:true}).fill("2026-11-02");
  await page.getByRole("button",{name:"Save cost record",exact:true}).click();
  await expect(page.getByRole("heading",{name:"Saved cost records"})).toBeVisible();
  await expect(page.locator(".workbench-message")).toContainText("Cost record saved.");
  expect(saved()).toMatchObject({evidence_item_id:"evidence-a",record_kind:"ACTUAL",amount:"1250",currency:"USD",measurement_basis:"COST_VALUE",commercial_effect:"NONE",effect_explanation:null});
});

test("a missing budget does not hide saved cost records, and switching projects clears them",async({page})=>{
  await fixture(page,true);await page.goto("/cost");
  await expect(page.getByRole("combobox",{name:"Project",exact:true})).toHaveValue("cost-a");
  await page.getByRole("button",{name:"Load cost controls",exact:true}).click();
  await expect(page.getByRole("heading",{name:"Saved cost records"})).toBeVisible();
  await expect(page.getByText("REPORTED · scope package-a · record-a",{exact:true})).toBeVisible();
  await expect(page.locator(".workbench-message")).toContainText("Current authorized budget not found");
  await page.getByRole("combobox",{name:"Project",exact:true}).selectOption("cost-b");
  await expect(page.getByRole("heading",{name:"Saved cost records"})).toHaveCount(0);
  await expect(page.getByRole("button",{name:"Save cost record",exact:true})).toBeDisabled();
});
