import { expect, test, type Page } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import { auditAccessibility, assertReflow } from "./accessibility-helpers";

const projects = [{id:"schedule-a",code:"A",name:"Tower"},{id:"schedule-b",code:"B",name:"Residence"}];
const network = {context_id:"approved-source-a",version_number:3,effective_from:"2026-10-01T00:00:00Z",data_date:"2026-11-02",activity_count:2,dependency_count:1,milestone_count:1,calendar_count:1,activities:[
  {code:"T1",name:"Foundation concrete",planned_start:"2026-11-01",planned_finish:"2026-11-10",calendar_id:"Site calendar",total_float_days:null},
  {code:"T2",name:"Ground floor slab",planned_start:"2026-11-11",planned_finish:"2026-11-20",calendar_id:"Site calendar",total_float_days:"0"},
],dependencies:[{predecessor_code:"T1",successor_code:"T2",relation_type:"FINISH_TO_START",lag_days:"0"}],milestones:[{code:"M1",name:"Structure handover",planned_date:"2026-11-25",activity_code:"T2",material:true}]};

async function fixture(page: Page, options: {missing?:boolean; failure?:number; policyFailure?:boolean; delay?:Promise<void>} = {}) {
  let writes = 0;
  await page.addInitScript(() => {localStorage.setItem("vai-project-workspace",JSON.stringify({actorId:"planner@test",organizationId:"schedule-org"}));localStorage.setItem("vai-active-project","schedule-a");});
  await page.route("**/api/v1/**",async route => {
    const path = new URL(route.request().url()).pathname;
    if(route.request().method() === "POST") { writes++; await route.fulfill({status:403,json:{detail:"Administrator permission required"}}); return; }
    if(path.endsWith("/auth/session")) {await route.fulfill({json:{mode:"DEVELOPMENT",actor_id:null,organization_id:null}});return;}
    if(path.endsWith("/projects")) {await route.fulfill({json:projects});return;}
    if(path.endsWith("/schedule/network")) {
      if(path.includes("schedule-a") && options.delay) await options.delay;
      if(options.failure) {await route.fulfill({status:options.failure,json:{detail:"Schedule access denied"}});return;}
      if(options.missing || path.includes("schedule-b")) {await route.fulfill({status:404,json:{detail:"Current authorized schedule not found"}});return;}
      await route.fulfill({json:network});return;
    }
    if(path.endsWith("/schedule/policies")) {await route.fulfill(options.policyFailure ? {status:503,json:{detail:"Policy store unavailable"}} : {json:[]});return;}
    await route.fulfill({json:[]});
  });
  return () => writes;
}

test("approved schedule automatically loads dates, searchable tasks and milestones with accessible reflow",async({page},testInfo)=>{
  const writes = await fixture(page);
  await page.goto("/schedule");
  await expect(page.getByRole("region",{name:"Approved plan summary"})).toContainText("Approved version 3");
  await expect(page.getByRole("region",{name:"Approved plan summary"})).toContainText("25 Nov 2026");
  await expect(page.getByRole("heading",{name:"Milestones",exact:true})).toBeVisible();
  await expect(page.getByRole("link",{name:"Next: Update progress",exact:false}).first()).toHaveAttribute("href","/progress");
  await expect(page.getByRole("button",{name:"Load schedule"})).toHaveCount(0);
  await expect(page.getByLabel("Version name",{exact:true})).toBeHidden();
  await page.getByRole("searchbox",{name:"Find a task"}).fill("T2");
  await expect(page.getByRole("rowheader",{name:"Ground floor slab T2"})).toBeVisible();
  await expect(page.getByRole("rowheader",{name:"Foundation concrete T1"})).toHaveCount(0);
  await expect(page.getByRole("cell",{name:"T1 · finish to start · lag 0 days"})).toBeVisible();
  await page.getByRole("searchbox").fill("");
  await auditAccessibility(page,testInfo,"approved-schedule-desktop");
  await mkdir(".test-tmp/approved-schedule",{recursive:true});
  await page.evaluate(() => { (document.activeElement as HTMLElement)?.blur(); window.scrollTo(0,0); });
  await page.screenshot({path:".test-tmp/approved-schedule/desktop.png",fullPage:true});
  await page.setViewportSize({width:320,height:900});
  await assertReflow(page);
  await auditAccessibility(page,testInfo,"approved-schedule-mobile");
  await page.evaluate(() => { (document.activeElement as HTMLElement)?.blur(); window.scrollTo(0,0); });
  await page.screenshot({path:".test-tmp/approved-schedule/mobile.png",fullPage:true});
  expect(writes()).toBe(0);
});

test("missing approval has an actionable empty state and policy failure never hides the approved plan",async({page})=>{
  await fixture(page,{policyFailure:true});await page.goto("/schedule");
  await expect(page.getByRole("region",{name:"Approved plan summary"})).toBeVisible();
  await page.getByText("Advanced settings: schedule analysis policy",{exact:true}).click();
  await expect(page.getByText("Policy settings unavailable:",{exact:false})).toBeVisible();
  await page.getByRole("combobox",{name:"Project",exact:true}).selectOption("schedule-b");
  await expect(page.getByRole("heading",{name:"No approved schedule yet"})).toBeVisible();
  await expect(page.getByRole("link",{name:"Review and approve a schedule",exact:false})).toHaveAttribute("href","/bootstrap/advanced");
  await expect(page.getByRole("region",{name:"Approved plan summary"})).toHaveCount(0);
});

test("permission failures are not mislabeled as missing schedules; denied policy writes preserve input",async({page})=>{
  const writes=await fixture(page,{failure:403}); await page.goto("/schedule");
  await expect(page.getByRole("heading",{name:"Schedule unavailable"})).toBeVisible();
  await expect(page.getByRole("heading",{name:"No approved schedule yet"})).toHaveCount(0);
  await page.getByText("Advanced settings: schedule analysis policy",{exact:true}).click();
  await page.getByLabel("Version name",{exact:true}).fill("v4");
  await page.getByLabel("On-time tolerance (days)",{exact:true}).fill("0.5");
  await page.getByLabel("Maximum schedule age (days)",{exact:true}).fill("14");
  await page.getByLabel("Reason for these rules").fill("Reviewed project requirements");
  await page.getByRole("button",{name:"Save new policy version"}).click();
  await expect(page.getByText("Administrator permission required",{exact:true})).toBeVisible();
  await expect(page.getByLabel("Version name",{exact:true})).toHaveValue("v4");
  expect(writes()).toBe(1);
});

test("late schedule responses never populate a different selected project",async({page})=>{
  let release!:()=>void;
  const delay=new Promise<void>(resolve=>{release=resolve;});
  await fixture(page,{delay});await page.goto("/schedule");
  await expect(page.getByText("Loading the approved schedule…",{exact:true})).toBeVisible();
  await page.getByRole("combobox",{name:"Project",exact:true}).selectOption("schedule-b");
  await expect(page.getByRole("heading",{name:"No approved schedule yet"})).toBeVisible();
  release();
  await expect(page.getByRole("region",{name:"Approved plan summary"})).toHaveCount(0);
  await expect(page.getByText("approved-source-a",{exact:false})).toHaveCount(0);
});

test("saving a policy shows persistent feedback without issuing schedule approval",async({page})=>{
  await fixture(page);
  let writes = 0;
  await page.route("**/schedule/policies",async route=>{
    if(route.request().method() !== "POST") {await route.fallback();return;}
    writes++;
    const body=route.request().postDataJSON();
    expect(body).toMatchObject({on_time_tolerance_days:"0.5",maximum_schedule_age_days:14,require_dependency_for_consequence:true,allow_calculated_float:true});
    await route.fulfill({status:201,json:body});
  });
  await page.goto("/schedule");
  await expect(page.getByRole("region",{name:"Approved plan summary"})).toBeVisible();
  await page.getByText("Advanced settings: schedule analysis policy",{exact:true}).click();
  await page.getByLabel("Version name",{exact:true}).fill("v4");
  await page.getByLabel("On-time tolerance (days)",{exact:true}).fill("0.5");
  await page.getByLabel("Maximum schedule age (days)",{exact:true}).fill("14");
  await page.getByLabel("Reason for these rules").fill("Synthetic reviewed project policy");
  await page.getByRole("button",{name:"Save new policy version"}).click();
  await expect(page.getByText("Policy version saved. The approved schedule has not changed.",{exact:true})).toBeVisible();
  await expect(page.getByRole("region",{name:"Approved plan summary"})).toContainText("Approved version 3");
  expect(writes).toBe(1);
});
