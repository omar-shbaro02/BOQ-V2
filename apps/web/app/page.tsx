"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ProjectHealthPanel, type ProjectHealth } from "./project-health-panel";
import { SnapshotAssistantPanel } from "./snapshot-assistant-panel";
import { currentWorkspace } from "./workspace-session";

const API = process.env.NEXT_PUBLIC_VAI_API_URL ?? "http://localhost:8000";
type Workspace = { actorId: string; organizationId: string };
type Project = { id: string; name: string; timezone: string };
type QueueItem = { case_id: string; case_number: string; title: string; priority_band: string | null; governance_state: string; lifecycle: string };
type PackageResult = { controlled_object_code: string; planned_ratio: string; actual_ratio: string; actual_truth_type: string };
type CostRef = { assessment_id: string; controlled_object_id: string; currency: string; assessment_status: string; values: { estimate_at_completion: string | null } };
type MetricValue = { ratio: string | null; percent: string | null; display: string };
type ForecastRef = { target: string; result_point: string; result_unit: string };
type Snapshot = { id: string; snapshot_number: number; data_date: string; planned_ratio: string; actual_ratio: string; variance_ratio: string; progress_status: string; confidence: string; limitations: { code: string }[]; package_results: PackageResult[]; shared_metrics: { planned: MetricValue; actual: MetricValue; variance: MetricValue; cost_assessments: CostRef[]; forecast_projections: ForecastRef[] }; health?: ProjectHealth };

export default function Home() {
  const [project, setProject] = useState<Project | null>(null);
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [queue, setQueue] = useState<QueueItem[]>([]);
  const [signalCount, setSignalCount] = useState<number | null>(null);
  const [message, setMessage] = useState("Loading governed project state…");

  useEffect(() => {
    async function load() {
      let workspace: Workspace | null;
      try { workspace = await currentWorkspace(); }
      catch (error) { setMessage(error instanceof Error ? error.message : "Identity service is unavailable."); return; }
      const projectId = localStorage.getItem("vai-active-project");
      if (!workspace || !projectId) { setMessage("Choose an active project before opening the command center."); return; }
      const headers = { "X-VAI-Actor-ID": workspace.actorId, "X-VAI-Organization-ID": workspace.organizationId };
      try {
        const responses = await Promise.all([
          fetch(`${API}/api/v1/organizations/${workspace.organizationId}/projects`, { headers }),
          fetch(`${API}/api/v1/projects/${projectId}/project-control/snapshots?limit=1`, { headers }),
          fetch(`${API}/api/v1/projects/${projectId}/decision-center/queue`, { headers }),
          fetch(`${API}/api/v1/projects/${projectId}/signals`, { headers }),
        ]);
        if (!responses.every((response) => response.ok)) throw new Error("Unable to load the governed project projection.");
        const projects = await responses[0].json() as Project[];
        setProject(projects.find((item) => item.id === projectId) ?? null);
        setSnapshot((await responses[1].json() as Snapshot[])[0] ?? null);
        setQueue(await responses[2].json() as QueueItem[]);
        setSignalCount((await responses[3].json() as unknown[]).length);
        setMessage("");
      } catch (error) { setMessage(error instanceof Error ? error.message : "Unable to load project state."); }
    }
    void load();
  }, []);

  const openCases = queue.filter((item) => item.lifecycle !== "CLOSED");
  const materialCases = openCases.filter((item) => item.priority_band === "CRITICAL" || item.priority_band === "HIGH");
  const costs = snapshot?.shared_metrics.cost_assessments ?? [];
  const finishes = snapshot?.shared_metrics.forecast_projections.filter((item) => item.target === "PROJECT_COMPLETION") ?? [];
  const percent = (value?: string) => value === undefined ? "Unknown" : `${(Number(value) * 100).toFixed(1)}%`;

  return <main className="dashboard-shell">
    <section className="dashboard-heading"><div><span className="eyebrow">Command center · governed snapshot</span><h1>{project?.name ?? "Project controls at a glance."}</h1><p>{message || (snapshot ? `Snapshot ${snapshot.snapshot_number} · data date ${new Date(snapshot.data_date).toLocaleString(undefined, { timeZone: project?.timezone ?? "UTC" }) + ` (${project?.timezone ?? "UTC"})`}` : "No project-control snapshot has been issued for this project.")}</p></div><div className="dashboard-heading-actions"><Link href="/setup" className="dashboard-secondary-action">Choose project</Link><Link href="/decision-center" className="primary-action">Open decision queue <span>→</span></Link></div></section>
    <section className="metric-grid" aria-label="Project summary"><Metric label="Verified completion" value={snapshot?.shared_metrics.actual.display ?? "Unknown"} change={snapshot ? `${snapshot.progress_status} · planned ${snapshot.shared_metrics.planned.display}` : "Snapshot required"} icon="%" tone="burgundy"/><Metric label="Open decision cases" value={project ? String(openCases.length) : "Unknown"} change={project ? `${materialCases.length} high or critical` : "Project required"} icon="◫" tone="amber"/><Metric label="Active signals" value={signalCount === null ? "Unknown" : String(signalCount)} change="Stored project signals" icon="⌁" tone="red"/><Metric label="Bound cost assessments" value={snapshot ? String(costs.length) : "Unknown"} change="See scoped EAC below" icon="$" tone="blue"/></section>
    <ProjectHealthPanel health={snapshot?.health} timezone={project?.timezone ?? "UTC"} />
    <SnapshotAssistantPanel key={snapshot?.id ?? "no-snapshot"} snapshotId={snapshot?.id} timezone={project?.timezone ?? "UTC"} />
    <section className="dashboard-main-grid">
      <article className="dashboard-card performance-card"><div className="dashboard-card-head"><div><span className="section-kicker">Project performance</span><h2>Authorized plan versus verified actual</h2></div><span className="period-select">{snapshot ? snapshot.progress_status.replaceAll("_", " ") : "UNKNOWN"}</span></div>{snapshot ? <><div className="chart-legend"><span>Planned <strong>{snapshot.shared_metrics.planned.display}</strong></span><span>Actual <strong>{snapshot.shared_metrics.actual.display}</strong></span><span className="chart-gap">Variance <strong>{snapshot.shared_metrics.variance.display}</strong></span></div><div className="health-bars"><Health label="Planned" value={Number(snapshot.planned_ratio) * 100} tone="burgundy"/><Health label="Verified actual" value={Number(snapshot.actual_ratio) * 100} tone={snapshot.progress_status === "BEHIND" ? "critical" : "good"}/></div></> : <p className="empty-state">Create an authorized weighting context and immutable project-control snapshot to calculate completion.</p>}</article>
      <article className="dashboard-card attention-card"><div className="dashboard-card-head"><div><span className="section-kicker">Attention required</span><h2>Decision priority</h2></div><Link href="/decision-center">View all →</Link></div><div className="signal-feed-list">{materialCases.slice(0, 4).map((item) => <div className="feed-item" key={item.case_id}><span className="feed-symbol critical">!</span><div><span className="signal-type critical">{item.priority_band}</span><strong>{item.case_number} · {item.title}</strong><small>{item.governance_state.replaceAll("_", " ")}</small></div></div>)}{!materialCases.length ? <p className="empty-state">No high or critical cases in the current queue.</p> : null}</div></article>
    </section>
    <section className="dashboard-lower-grid"><article className="dashboard-card signal-feed"><div className="dashboard-card-head"><div><span className="section-kicker">Work-package lineage</span><h2>Snapshot contributions</h2></div><Link href="/progress">Progress evidence →</Link></div><div className="signal-feed-list">{snapshot?.package_results.map((item) => <div className="feed-item" key={item.controlled_object_code}><span className="feed-symbol neutral">%</span><div><strong>{item.controlled_object_code}</strong><small>Plan {percent(item.planned_ratio)} · actual {percent(item.actual_ratio)} · {item.actual_truth_type.replaceAll("_", " ")}</small></div></div>)}{!snapshot ? <p className="empty-state">No frozen package contributions.</p> : null}</div></article><article className="dashboard-card health-card"><div className="dashboard-card-head"><div><span className="section-kicker">Control health</span><h2>Evidence and forecast</h2></div><span className="health-score">{snapshot ? percent(snapshot.confidence) : "Unknown"}</span></div><p><strong>Forecast finish:</strong> {finishes.length ? finishes.map((item, index) => <span key={index}>{index ? " · " : ""}{item.result_point} {item.result_unit}</span>) : "Unknown"}</p><p><strong>Scoped EAC:</strong> {costs.length ? costs.map((item) => <span key={item.assessment_id}> {item.controlled_object_id} · {item.currency} {item.values.estimate_at_completion ?? "Unknown"} · {item.assessment_status} </span>) : "Unknown"}</p><p><strong>Limitations:</strong> {snapshot?.limitations.length ? snapshot.limitations.map((item) => item.code.replaceAll("_", " ")).join(" · ") : snapshot ? "None recorded" : "Snapshot required"}</p><p className="semantic-note"><span>i</span> Values come from one immutable project-control snapshot. Unknown is never displayed as zero, and indicators are not human decisions or execution authority.</p></article></section>
  </main>;
}

function Metric({ label, value, change, icon, tone }: { label: string; value: string; change: string; icon: string; tone: string }) { return <article className="metric-card"><div className={`metric-icon ${tone}`}>{icon}</div><div><span>{label}</span><strong>{value}</strong><small className={tone}>{change}</small></div></article>; }
function Health({ label, value, tone }: { label: string; value: number; tone: string }) { return <div className="health-row"><div><span>{label}</span><strong>{value.toFixed(1)}%</strong></div><div className="health-track"><i className={tone} style={{ width: `${Math.max(0, Math.min(100, value))}%` }}/></div></div>; }
