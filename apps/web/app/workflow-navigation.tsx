import Link from "next/link";

// A suggested working order, never a claim that a step is complete or authorized.
export const workflowGroups = [
  { label: "01 · Establish the plan", links: [
    { href: "/setup", label: "Projects", icon: "folder", guidance: "Create or select your project and review its control context." },
    { href: "/bootstrap", label: "BOQ to schedule", icon: "layers", guidance: "Prepare a schedule proposal from the BOQ. Review and authorize it separately in the advanced workbench." },
    { href: "/schedule", label: "Schedule", icon: "calendar", guidance: "Check the effective authorized schedule, calendars and dependency logic before comparing updates." },
  ] },
  { label: "02 · Collect control updates", links: [
    { href: "/evidence", label: "Evidence", icon: "file", guidance: "Retain source artifacts and reported claims. Record human verification separately." },
    { href: "/progress", label: "Progress", icon: "trend", guidance: "Map evidence-backed measurements to the authorized plan and preserve their truth labels." },
    { href: "/cost", label: "Cost control", icon: "wallet", guidance: "Review budget and cost evidence with matching currency, scope, period and measurement basis." },
  ] },
  { label: "03 · Investigate & assess", links: [
    { href: "/signals", label: "Signals", icon: "signal", guidance: "Screen detected conditions and review correlations before opening or linking a Decision Case." },
    { href: "/cases", label: "Decision cases", icon: "briefcase", guidance: "Assemble evidence, freeze a snapshot and assess progress, schedule and cost sufficiency before forecasting." },
    { href: "/forecast", label: "Forecasts", icon: "chart", guidance: "Inspect case-bound forecasts, assumptions and validity. Create forecasts within the case; keep scenarios separate." },
    { href: "/impact", label: "Impact & priority", icon: "target", guidance: "Use the case snapshot and eligible analysis to assess consequences, confidence, decision clocks and priority." },
    { href: "/orchestration", label: "Orchestration", icon: "nodes", guidance: "Coordinate snapshot-bound specialist results and inspect the recommendation, alternatives and blockers." },
  ] },
  { label: "04 · Review & follow through", links: [
    { href: "/decision-center", label: "Decision queue", icon: "pulse", guidance: "Prioritize human review, inspect authority routes and export reports. Record decisions and follow responses in the case." },
  ] },
];

const steps = workflowGroups.flatMap((group) => group.links.map((link) => ({ ...link, stage: group.label })));

export function WorkflowNavigation({ pathname, position }: { pathname: string; position: "top" | "bottom" }) {
  const index = steps.findIndex((step) => pathname === step.href || pathname.startsWith(`${step.href}/`));
  const current = steps[index];
  const previous = steps[index - 1];
  const next = steps[index + 1];
  const advanced = pathname === "/bootstrap/advanced";
  const assistant = pathname === "/bootstrap/schedule-assistant";
  const title = advanced ? "Schedule review & authorization" : assistant ? "Schedule-change proposal" : current?.label ?? "Command center";
  const guidance = advanced ? "Upload your BOQ, check its work items, plan working dates, then request approval." : assistant ? "Review and recalculate the proposed changes in Microsoft Project. This proposal does not change the authorized schedule." : current?.guidance ?? "Start with a project, then follow the guided workflow. Returning operators can jump directly to the decision queue.";
  const destination = next ?? (current ? steps.find((step) => step.href === "/cases")! : steps[0]);
  const action = !current ? "Start: Projects" : !next ? "Return to cases for decisions" : `Next: ${destination.label}`;

  if (position === "top") return <section className="workflow-guide" aria-label="Workflow orientation">
    <div className="workflow-location"><span className="workflow-step">{current ? `${String(index + 1).padStart(2, "0")} / ${steps.length}` : "START HERE"}</span><div><span className="workflow-stage">{current?.stage ?? "Your project workflow"}</span><strong>{title}</strong></div></div>
    <p>{guidance}</p>
    <Link className="workflow-next" href={destination.href}>{action}<span aria-hidden="true">→</span></Link>
  </section>;

  return <section className="workflow-handoff" aria-label="Next workflow step">
    <div className="workflow-handoff-copy"><span className="eyebrow">{next || !current ? "Continue your workflow" : "Continue in the case"}</span><h2>{destination.label}</h2><p>{destination.guidance}</p><small>Navigation only. Save your work before leaving; moving to another page does not complete or approve this step.</small></div>
    <div className="workflow-handoff-actions"><Link className="workflow-next" href={destination.href}>{action}<span aria-hidden="true">→</span></Link>{previous ? <Link className="workflow-previous" href={previous.href}>← Back: {previous.label}</Link> : current ? <Link className="workflow-previous" href="/">← Command center</Link> : <Link className="workflow-previous" href="/decision-center">Go to decision queue</Link>}</div>
    {pathname.startsWith("/bootstrap") ? <div className="workflow-branches"><span>Planning tools</span>{!advanced ? <Link href="/bootstrap/advanced">Review & authorize schedule</Link> : <Link href="/bootstrap">BOQ conversion</Link>}{!assistant ? <Link href="/bootstrap/schedule-assistant">Propose schedule changes</Link> : null}</div> : null}
  </section>;
}
