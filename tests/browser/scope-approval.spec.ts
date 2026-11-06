import { expect, test } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import { auditAccessibility, assertReflow } from "./accessibility-helpers";

test.beforeEach(async ({page,request}) => {
  const organizationResponse=await request.post("http://127.0.0.1:8011/api/v1/organizations",{headers:{"X-VAI-Actor-ID":"browser@example.test","X-VAI-Roles":"ORGANIZATION_ADMIN"},data:{name:"Scope approval fixture",slug:`scope-${crypto.randomUUID()}`}});
  expect(organizationResponse.status()).toBe(201);
  const organization=await organizationResponse.json();
  const projectResponse=await request.post(`http://127.0.0.1:8011/api/v1/organizations/${organization.id}/projects`,{headers:{"X-VAI-Actor-ID":"browser@example.test","X-VAI-Organization-ID":organization.id},data:{code:"SCOPE",name:"Scope approval fixture",timezone:"Asia/Beirut",currency:"USD",delivery_model:"DESIGN_BID_BUILD",reporting_cadence:"WEEKLY"}});
  expect(projectResponse.status()).toBe(201);
  const project=await projectResponse.json();
  await page.addInitScript(({projectId,organizationId}) => {
    localStorage.setItem("vai-project-workspace",JSON.stringify({actorId:"browser@example.test",organizationId}));
    localStorage.setItem("vai-active-project",projectId);
  },{projectId:project.id,organizationId:organization.id});
});

test("BOQ preparation is automatic but work-package approval requires the human button",async({page},testInfo)=>{
  const revisions:string[]=[];
  page.on("request",request=>{if(request.method()==="POST" && request.url().endsWith("/revisions")) revisions.push(request.url());});
  await page.goto("/bootstrap/advanced");
  await expect(page.getByRole("combobox",{name:"Project",exact:true})).not.toHaveValue("");
  await page.getByRole("button",{name:"Load project",exact:true}).click();
  await expect(page.locator(".workbench-message")).toContainText("Project connected");
  await page.getByLabel("BOQ file (Excel or PDF)").setInputFiles(".test-tmp/browser-boq.xlsx");
  const savedSource=page.waitForResponse(response=>response.request().method()==="POST" && response.url().endsWith("/boq-sources"));
  await page.getByRole("button",{name:"Upload BOQ",exact:true}).click();
  const source=await (await savedSource).json();
  const approval=page.getByRole("button",{name:"Approve work packages",exact:true});
  await expect(approval).toBeEnabled();
  await expect(page.getByRole("button",{name:"Generate structure",exact:true})).toHaveCount(0);
  await expect(page.getByRole("button",{name:"Normalize",exact:true})).toHaveCount(0);
  await expect(page.locator('[data-bootstrap-step="05"]').getByLabel("Review reason")).toHaveCount(0);
  await expect(page.getByRole("region",{name:"BOQ source review",exact:true})).toBeHidden();
  expect(revisions).toEqual([]);
  await auditAccessibility(page,testInfo,"scope-approval-desktop");
  await mkdir(".test-tmp/scope-approval",{recursive:true});
  await page.evaluate(()=>{(document.activeElement as HTMLElement)?.blur();window.scrollTo(0,0);});
  await page.screenshot({path:".test-tmp/scope-approval/desktop.png",fullPage:true});
  await page.setViewportSize({width:320,height:900});
  await assertReflow(page);await auditAccessibility(page,testInfo,"scope-approval-mobile");
  await page.evaluate(()=>{(document.activeElement as HTMLElement)?.blur();window.scrollTo(0,0);});
  await page.screenshot({path:".test-tmp/scope-approval/mobile.png",fullPage:true});
  const response=page.waitForResponse(response=>response.request().method()==="POST" && response.url().endsWith("/revisions"));
  await approval.click();
  const approved=await response;
  expect(approved.status()).toBe(201);
  expect(approved.request().postDataJSON()).toEqual({action:"ACCEPT_PROPOSAL",reason:"Approved work packages using the scope approval button."});
  expect(revisions).toHaveLength(1);
  await expect(page.getByRole("heading",{name:"Plan the schedule",exact:true})).toBeVisible();
  await page.getByRole("navigation",{name:"Schedule preparation stages"}).getByRole("button").nth(0).click();
  await page.getByRole("combobox",{name:"Or continue with a saved BOQ"}).selectOption(source.id);
  await page.getByRole("button",{name:"Review saved BOQ",exact:true}).click();
  await expect(approval).toBeEnabled();
  expect(revisions).toHaveLength(1);
});

test("an unreadable BOQ blocks approval and offers a useful recovery action",async({page})=>{
  await page.route("**/normalizations",route=>route.fulfill({status:422,json:{detail:"BOQ source extraction is not ready"}}));
  await page.goto("/bootstrap/advanced");
  await expect(page.getByRole("combobox",{name:"Project",exact:true})).not.toHaveValue("");
  await page.getByRole("button",{name:"Load project",exact:true}).click();
  await expect(page.locator(".workbench-message")).toContainText("Project connected");
  await page.getByLabel("BOQ file (Excel or PDF)").setInputFiles(".test-tmp/browser-boq.xlsx");
  await page.getByRole("button",{name:"Upload BOQ",exact:true}).click();
  await expect(page.locator('[data-bootstrap-step="05"]').getByText("We could not read this BOQ yet.",{exact:false})).toBeVisible();
  await expect(page.getByRole("button",{name:"Approve work packages",exact:true})).toBeDisabled();
  await expect(page.getByRole("button",{name:"Try preparing again"})).toBeEnabled();
  await page.getByRole("button",{name:"Choose another BOQ"}).click();
  await expect(page.getByRole("heading",{name:"Upload your BOQ",exact:true})).toBeVisible();
});
