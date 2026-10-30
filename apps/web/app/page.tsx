"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ProjectHealthPanel, type ProjectHealth } from "./project-health-panel";
import { SnapshotAssistantPanel } from "./snapshot-assistant-panel";
import { currentWorkspace, type Workspace } from "./workspace-session";

const API = process.env.NEXT_PUBLIC_VAI_API_URL ?? "http://localhost:8000";
type Project = { id: string; code: string; name: string; timezone: string };
type QueueItem = { case_id: string; case_number: string; title: string; priority_band: string | null; governance_state: string; lifecycle: string; next_action?: string; next_deadline?: string | null; owner_actor_id?: string };
type Artifact = { id: string; original_filename: string; source_type: string; scan_result: string; received_at: string };
type Context = { context_type: string; semantic_state: string; version_number: number };
type CostRef = { assessment_id: string; controlled_object_id: string; currency: string; assessment_status: string; values: { estimate_at_completion: string | null } };
type Snapshot = {
  id: string; snapshot_number: number; data_date: string; planned_ratio: string; actual_ratio: string;
  progress_status: string; confidence: string; limitations: { code: string }[];
  package_results: { controlled_object_code: string; planned_ratio: string; actual_ratio: string; actual_truth_type: string }[];
  shared_metrics: { planned: { display: string }; actual: { display: string }; variance: { display: string }; cost_assessments: CostRef[]; forecast_projections: { target: string; result_point: string; result_unit: string }[] };
  health?: ProjectHealth;
};
type Resource<T> = { value: T | null; error?: string };
type Overview = {
  projectId: string; loadedAt: number; snapshots: Resource<Snapshot[]>; queue: Resource<QueueItem[]>;
  artifacts: Resource<Artifact[]>; imports: Resource<{ id: string; data_date: string }[]>; contexts: Resource<Context[]>;
};

export default function Home() {
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState("");
  const [initializing, setInitializing] = useState(true);
  const [error, setError] = useState("");
  const [reload, setReload] = useState(0);
  const [overview, setOverview] = useState<Overview | null>(null);
  const [refresh, setRefresh] = useState(0);
  const project = projects.find(item => item.id === projectId);
  const data = overview?.projectId === projectId ? overview : null;

  useEffect(() => {
    const controller = new AbortController();
    async function initialize() {
      try {
        const active = await currentWorkspace();
        if (controller.signal.aborted) return;
        setWorkspace(active);
        if (!active) return;
        const response = await fetch(`${API}/api/v1/organizations/${active.organizationId}/projects`, { signal: controller.signal, cache: "no-store", headers: auth(active) });
        if (!response.ok) throw new Error("Your projects could not be loaded. Check your connection and try again.");
        const items = await response.json() as Project[];
        if (controller.signal.aborted) return;
        const stored = localStorage.getItem("vai-active-project");
        const selected = items.find(item => item.id === stored)?.id ?? items[0]?.id ?? "";
        setProjects(items); setProjectId(selected); setError("");
        if (selected) localStorage.setItem("vai-active-project", selected);
      } catch (cause) {
        if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : "Unable to load your workspace.");
      } finally { if (!controller.signal.aborted) setInitializing(false); }
    }
    void initialize();
    return () => controller.abort();
  }, [reload]);

  useEffect(() => {
    if (!workspace || !projectId) return;
    const controller = new AbortController();
    const active = workspace, selected = projectId;
    async function read<T,>(path: string): Promise<Resource<T>> {
      try {
        const response = await fetch(`${API}/api/v1/projects/${selected}${path}`, { signal: controller.signal, cache: "no-store", headers: auth(active) });
        if (!response.ok) throw new Error("Unavailable");
        return { value: await response.json() as T };
      } catch { return { value: null, error: "Could not load this section." }; }
    }
    async function load() {
      const [snapshots, queue, artifacts, imports, contexts] = await Promise.all([
        read<Snapshot[]>("/project-control/snapshots?limit=1"), read<QueueItem[]>("/decision-center/queue"),
        read<Artifact[]>("/evidence/artifacts"), read<{ id: string; data_date: string }[]>("/progress/workbook-imports"),
        read<Context[]>("/authorized-context/versions"),
      ]);
      if (!controller.signal.aborted) setOverview({ projectId: selected, loadedAt: Date.now(), snapshots, queue, artifacts, imports, contexts });
    }
    void load();
    return () => controller.abort();
  }, [workspace, projectId, refresh]);

  function chooseProject(value: string) { setOverview(null); setProjectId(value); localStorage.setItem("vai-active-project", value); }
  function retry() { setOverview(null); setRefresh(value => value + 1); }
  const snapshot = data?.snapshots.value?.[0];
  const cases = data?.queue.value?.filter(item => item.lifecycle !== "CLOSED") ?? [];
  const urgent = cases.filter(item => item.priority_band === "HIGH" || item.priority_band === "CRITICAL");
  const cleanFiles = data?.artifacts.value?.filter(item => item.scan_result === "CLEAN") ?? [];
  const schedules = cleanFiles.filter(item => item.source_type === "AI_SCHEDULE_EXPORT");
  const boq = cleanFiles.filter(item => item.source_type === "BOQ_UPLOAD");
  const current = data?.contexts.value?.filter(item => item.semantic_state === "CURRENT_AUTHORIZED") ?? [];
  const authorizedSchedule = current.find(item => item.context_type === "SCHEDULE");
  const hasWeights = current.some(item => item.context_type === "PROGRESS_WEIGHTING");
  const imports = data?.imports.value ?? [];
  const timezone = project?.timezone ?? "UTC";
  const incomplete = data && [data.snapshots, data.queue, data.artifacts, data.imports, data.contexts].some(item => item.error);
  const next = !data ? null : urgent.length ? { label: "Review priority cases", href: "/decision-center", title: `${urgent.length} ${urgent.length === 1 ? "case needs" : "cases need"} your attention`, detail: "Review the evidence, next action and authority route before making a decision." }
    : !data.artifacts.value || !data.contexts.value ? { label: "Review project setup", href: "/setup", title: "Some project information could not be loaded", detail: "Refresh the workspace to retry, or open project setup to review the available records." }
    : !schedules.length && !authorizedSchedule ? { label: "Build your schedule", href: "/bootstrap", title: "Start with your project plan", detail: "Upload the BOQ to prepare the activity schedule and make your progress template available." }
    : !authorizedSchedule ? { label: "Review & authorize schedule", href: "/bootstrap/advanced", title: "Your schedule is ready for review", detail: "A saved schedule is a proposal. Review the dates, dependencies and assumptions before authorizing the baseline." }
    : !data.imports.value ? { label: "Open progress", href: "/progress", title: "Check your reporting updates", detail: "Progress history could not be loaded. Refresh or open Progress to review your records." }
    : !imports.length && !snapshot ? { label: "Update project progress", href: "/progress", title: "Record your first progress update", detail: "Download the ready-to-use Excel template, enter site progress and compare it with your schedule." }
    : !snapshot ? { label: "Prepare project status", href: "/progress", title: "Turn your updates into a verified project view", detail: "Review supporting evidence, verify the measurements and issue a project-control snapshot." }
    : { label: "Update project progress", href: "/progress", title: "Keep the next reporting cycle moving", detail: "Record the latest site observations and review changes before issuing your next status snapshot." };

  return <main className="cc-shell">
    <header className="cc-header"><div><span className="eyebrow">Command center</span><h1>{project?.name ?? "Command center"}</h1><p>Your plan, latest updates and decisions that need attention.</p></div><div className="cc-project-controls">{projects.length ? <label>Active project<select value={projectId} onChange={event => chooseProject(event.target.value)}>{projects.map(item => <option key={item.id} value={item.id}>{item.code} · {item.name}</option>)}</select></label> : null}{project ? <button className="cc-refresh" onClick={retry}>Refresh</button> : null}</div></header>
    {error ? <div className="cc-error" role="alert"><strong>Workspace unavailable</strong><p>{error}</p><button onClick={() => setReload(value => value + 1)}>Try again</button><Link href="/setup">Open project setup →</Link></div> : null}
    {initializing ? <div className="cc-loading" role="status">Loading your projects…</div> : !project && !error ? <section className="cc-welcome"><div className="cc-welcome-mark" aria-hidden="true">01</div><span className="eyebrow">A clear starting point</span><h2>Bring your project into focus.</h2><p>Create or select a project, build its schedule, and track the work against your plan. Your next action will appear here as you go.</p><Link className="primary-action" href="/setup">Start: Projects <span aria-hidden="true">→</span></Link><div className="cc-welcome-steps"><div><b>01 / Plan</b><span>BOQ, activities and reviewed dates</span></div><div><b>02 / Track</b><span>Site updates and supporting evidence</span></div><div><b>03 / Decide</b><span>Investigate issues and follow through</span></div></div></section> : null}
    {project && !data ? <div className="cc-loading" role="status">Loading {project.name}…</div> : null}
    {project && data && <>
      <section className="cc-next" aria-label="Recommended next step"><div><span className="cc-live-label">Next action · {project.code}</span><h2>{next?.title}</h2><p>{next?.detail}</p></div><Link className="primary-action" href={next?.href ?? "/setup"}>{next?.label}<span aria-hidden="true">→</span></Link></section>
      {incomplete ? <p className="cc-warning" role="status">Some sections are unavailable. Available records are shown below; missing results are not counted as zero. <button onClick={retry}>Retry loading</button></p> : null}
      <section className="cc-stats" aria-label="Project summary"><Stat label="Saved schedules" value={data.artifacts.value ? String(schedules.length) : "Unavailable"} note="Stored proposals · review required" href="/bootstrap" /><Stat label="Progress updates" value={data.imports.value ? String(imports.length) : "Unavailable"} note={imports[0] ? `Latest reporting date ${date(imports[0].data_date, timezone)}` : "Saved reported workbook imports"} href="/progress" /><Stat label="Open decision cases" value={data.queue.value ? String(cases.length) : "Unavailable"} note={data.queue.value ? `${urgent.length} high or critical priority` : "Decision cases unavailable"} href="/decision-center" attention={urgent.length > 0} /><Stat label="Verified completion" value={snapshot?.shared_metrics.actual.display ?? (data.snapshots.error ? "Unavailable" : "Not issued")} note={snapshot ? `Snapshot #${snapshot.snapshot_number} · ${date(snapshot.data_date, timezone)}` : "Requires an issued control snapshot"} href="/progress" /></section>
      <div className="cc-columns"><div className="cc-work-stack"><section className="cc-panel" aria-labelledby="cc-review-title"><div className="cc-panel-head"><div><span className="eyebrow">Live review queue</span><h2 id="cc-review-title">Needs your review</h2></div><Link href="/decision-center">View queue →</Link></div>{data.queue.error ? <Empty title="Decision cases unavailable" detail="Refresh to retry. We cannot confirm whether there are cases awaiting review." href="/decision-center" action="Open decision queue" /> : !cases.length ? <Empty title="No open decision cases" detail="Review project signals when new evidence or a potential issue needs investigation." href="/signals" action="Review signals" /> : <ul className="cc-cases">{cases.slice(0, 5).map(item => <li key={item.case_id}><div className="cc-case-top"><span className={`cc-priority ${item.priority_band === "HIGH" || item.priority_band === "CRITICAL" ? "urgent" : ""}`}>{item.priority_band ?? "UNRANKED"}</span><span>{item.case_number}</span>{item.next_deadline ? <time className={new Date(item.next_deadline).getTime() < data.loadedAt ? "cc-overdue" : ""} dateTime={item.next_deadline}>{new Date(item.next_deadline).getTime() < data.loadedAt ? "Overdue · " : "Due · "}{date(item.next_deadline, timezone)}</time> : null}</div><Link href="/cases" className="cc-case-title">{item.title}<span aria-hidden="true">↗</span></Link><p>{item.next_action ? words(item.next_action) : "Open the case to review its evidence and next action."}</p><small>{words(item.governance_state)}{item.owner_actor_id ? ` · ${item.owner_actor_id}` : ""}</small></li>)}</ul>}</section><QuickActions /></div>
        <section className="cc-panel" aria-labelledby="cc-readiness-title"><div className="cc-panel-head"><div><span className="eyebrow">Reporting foundations</span><h2 id="cc-readiness-title">Plan to project status</h2></div></div><p className="cc-panel-intro">Stored records and review stages. These indicators do not grant approval.</p><ol className="cc-readiness"><Stage number="01" title="BOQ source" detail={data.artifacts.error ? "Source records unavailable" : `${boq.length} clean source ${boq.length === 1 ? "file" : "files"}`} state={data.artifacts.error ? "Unavailable" : boq.length ? "Saved" : "Add source"} href="/bootstrap" /><Stage number="02" title="Schedule baseline" detail={authorizedSchedule ? `Authorized version ${authorizedSchedule.version_number}` : schedules.length ? "Proposal saved · authorization outstanding" : "Prepare and review the activity network"} state={data.contexts.error ? "Unavailable" : authorizedSchedule ? "Authorized" : "Review needed"} href={authorizedSchedule ? "/schedule" : "/bootstrap/advanced"} /><Stage number="03" title="Progress weighting" detail="Define how work packages contribute to completion" state={data.contexts.error ? "Unavailable" : hasWeights ? "Authorized" : "Set weights"} href="/setup" /><Stage number="04" title="Site progress" detail="Workbook updates remain reported until verified" state={data.imports.error ? "Unavailable" : imports.length ? "Reported" : "Add update"} href="/progress" /><Stage number="05" title="Verified project view" detail={snapshot ? `Issued ${date(snapshot.data_date, timezone)}` : "Verify measurements and issue a control snapshot"} state={data.snapshots.error ? "Unavailable" : snapshot ? "Issued" : "Not issued"} href="/progress" /></ol></section></div>

      {snapshot ? <><div className="cc-snapshot-heading"><div><span className="eyebrow">Verified reporting basis</span><h2>Latest issued project status</h2></div><span>Snapshot #{snapshot.snapshot_number} · {date(snapshot.data_date, timezone)} · {timezone}</span></div><div className="cc-columns cc-performance"><section className="cc-panel"><div className="cc-panel-head"><div><h2>Plan versus verified actual</h2><p>One issued snapshot. New uploads are not included automatically.</p></div><span className="cc-status">{words(snapshot.progress_status)}</span></div><div className="cc-progress-numbers"><div><span>Planned</span><strong>{snapshot.shared_metrics.planned.display}</strong></div><div><span>Verified actual</span><strong>{snapshot.shared_metrics.actual.display}</strong></div><div><span>Variance</span><strong>{snapshot.shared_metrics.variance.display}</strong></div></div><Bar label="Planned completion" value={Number(snapshot.planned_ratio) * 100} /><Bar label="Verified completion" value={Number(snapshot.actual_ratio) * 100} actual /><p className="cc-footnote">No overall completion is inferred from an unweighted average of task percentages.</p></section><section className="cc-panel"><div className="cc-panel-head"><h2>Work-package contributions</h2><Link href="/progress">View progress →</Link></div><div className="cc-packages">{snapshot.package_results.slice(0, 6).map(item => <div key={item.controlled_object_code}><strong>{item.controlled_object_code}</strong><span>Plan {percent(item.planned_ratio)} · actual {percent(item.actual_ratio)}</span><small>{words(item.actual_truth_type)}</small></div>)}</div></section></div><div className="cc-health"><ProjectHealthPanel health={snapshot.health} timezone={timezone} /></div><SnapshotAssistantPanel key={snapshot.id} snapshotId={snapshot.id} timezone={timezone} /><details className="cc-panel cc-source-details"><summary>Snapshot forecasts, scoped costs & limitations</summary><p>Projections and cost estimates retain their own scope and assumptions. They are not added into an unsupported project total.</p><div className="cc-source-grid"><div><h3>Completion forecasts</h3>{snapshot.shared_metrics.forecast_projections.filter(item => item.target === "PROJECT_COMPLETION").map((item, index) => <p key={index}>{item.result_point} {item.result_unit === "DATE" ? "" : item.result_unit}</p>)}{!snapshot.shared_metrics.forecast_projections.some(item => item.target === "PROJECT_COMPLETION") ? <p>No completion forecast selected for this snapshot.</p> : null}<Link href="/forecast">Review forecast history →</Link></div><div><h3>Scoped estimate at completion</h3>{snapshot.shared_metrics.cost_assessments.map(item => <p key={item.assessment_id}>{item.controlled_object_id} · {item.currency} {item.values.estimate_at_completion ?? "Unavailable"} · {words(item.assessment_status)}</p>)}{!snapshot.shared_metrics.cost_assessments.length ? <p>No cost assessment selected for this snapshot.</p> : null}<Link href="/cost">Review cost records →</Link></div></div><p>Limitations: {snapshot.limitations.length ? snapshot.limitations.map(item => words(item.code)).join(" · ") : "None recorded in this snapshot"}.</p></details></> : <section className="cc-snapshot-empty"><div><span className="eyebrow">Verified reporting basis</span><h2>{data.snapshots.error ? "Project status could not be loaded" : "Your verified project view comes next"}</h2><p>{data.snapshots.error ? "Retry loading before drawing conclusions about project performance." : "Your saved schedules and reported updates are available above. Verified completion and project health appear after evidence is reviewed and a control snapshot is issued."}</p></div><Link href="/progress">{data.snapshots.error ? "Review project snapshots" : "Prepare project status"} →</Link></section>}
      <footer className="cc-footer">Workspace counts reflect the latest loaded records. Performance figures use the dated snapshot. Recommendations and indicators do not authorize execution.</footer>
    </>}
  </main>;
}

function auth(workspace: Workspace) { return { "X-VAI-Actor-ID": workspace.actorId, "X-VAI-Organization-ID": workspace.organizationId }; }
function words(value: string) { return value.replaceAll("_", " ").toLowerCase(); }
function date(value: string, timezone: string) { return new Date(value).toLocaleDateString(undefined, { timeZone: timezone, day: "numeric", month: "short", year: "numeric" }); }
function percent(value: string) { return `${(Number(value) * 100).toFixed(1)}%`; }
function Stat({ label, value, note, href, attention = false }: { label: string; value: string; note: string; href: string; attention?: boolean }) { return <Link href={href} className={`cc-stat ${attention ? "attention" : ""}`}><span>{label}<span aria-hidden="true">↗</span></span><strong>{value}</strong><small>{note}</small></Link>; }
function Stage({ number, title, detail, state, href }: { number: string; title: string; detail: string; state: string; href: string }) { return <li><span className="cc-stage-number" aria-hidden="true">{number}</span><div><Link href={href}>{title}</Link><p>{detail}</p></div><span className={`cc-stage-state ${["Saved", "Authorized", "Reported", "Issued"].includes(state) ? "recorded" : ""}`}>{state}</span></li>; }
function Empty({ title, detail, href, action }: { title: string; detail: string; href: string; action: string }) { return <div className="cc-empty"><span aria-hidden="true">◎</span><h3>{title}</h3><p>{detail}</p><Link href={href}>{action} →</Link></div>; }
function Bar({ label, value, actual = false }: { label: string; value: number; actual?: boolean }) { return <div className="cc-bar"><div><span>{label}</span><strong>{value.toFixed(1)}%</strong></div><div className="cc-bar-track"><span className={actual ? "actual" : ""} style={{ width: `${Math.max(0, Math.min(100, value))}%` }} /></div></div>; }

function QuickActions() { return <section className="cc-quick-links" aria-label="Common project actions"><Link href="/progress"><span className="cc-action-symbol" aria-hidden="true">↗</span><strong>Update progress</strong><span>Download the Excel template and compare site updates.</span></Link><Link href="/evidence"><span className="cc-action-symbol" aria-hidden="true">＋</span><strong>Add site evidence</strong><span>Keep reports, photos and observations traceable.</span></Link><Link href="/bootstrap/schedule-assistant"><span className="cc-action-symbol" aria-hidden="true">⇄</span><strong>Propose a schedule change</strong><span>Prepare a proposal for planner review.</span></Link></section>; }
