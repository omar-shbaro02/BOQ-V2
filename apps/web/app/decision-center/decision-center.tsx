"use client";

import Link from "next/link";
import { FormEvent, useMemo, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_VAI_API_URL ?? "http://localhost:8000";

type Connection = { actorId: string; organizationId: string; projectId: string };
type QueueItem = {
  case_id: string;
  case_number: string;
  title: string;
  lifecycle: string;
  readiness: string | null;
  governance_state: string;
  owner_actor_id: string;
  opened_at: string;
  controlled_object_count: number;
  open_limitation_count: number;
  active_response_count: number;
  recommended_disposition: string | null;
  decision_basis_recommendation: string | null;
  human_disposition: string | null;
  recommendation_agreement: string | null;
  priority_score: string | null;
  priority_band: string | null;
  urgency: string | null;
  overall_confidence: string | null;
  consequence_window: string | null;
  next_deadline: string | null;
  next_action: string;
};
type Report = {
  report_type: string;
  schema_version: string;
  generated_at: string;
  as_of: string;
  semantic_notice: string;
  payload: Record<string, unknown>;
};
type ReviewEntry = { case: QueueItem; reason: string; deadline: string | null; required_role: string };
type ReviewQueueName = "verification" | "human_review" | "approval" | "escalation" | "governance_blocks" | "overdue_evidence" | "expiring_forecasts";
type ReviewQueues = Record<ReviewQueueName, ReviewEntry[]> & { project_timezone: string };
const reviewQueueNames: ReviewQueueName[] = ["verification", "human_review", "approval", "escalation", "governance_blocks", "overdue_evidence", "expiring_forecasts"];

export function DecisionCenter() {
  const savedContext = savedJson<Connection>("vai-decision-center-context");
  const [connection, setConnection] = useState<Connection | null>(null);
  const [queue, setQueue] = useState<QueueItem[]>([]);
  const [reviewQueues, setReviewQueues] = useState<ReviewQueues | null>(null);
  const [governanceFilter, setGovernanceFilter] = useState(() => savedValue("vai-governance-filter", "ALL"));
  const [lifecycleFilter, setLifecycleFilter] = useState(() => savedValue("vai-lifecycle-filter", "OPEN"));
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const visible = useMemo(
    () =>
      queue.filter(
        (item) =>
          (governanceFilter === "ALL" || item.governance_state === governanceFilter) &&
          (lifecycleFilter === "ALL" ||
            (lifecycleFilter === "OPEN" ? item.lifecycle !== "CLOSED" : item.lifecycle === "CLOSED")),
      ),
    [queue, governanceFilter, lifecycleFilter],
  );

  function headers(active: Connection): HeadersInit {
    return {
      "X-VAI-Actor-ID": active.actorId,
      "X-VAI-Organization-ID": active.organizationId,
    };
  }

  async function connect(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const next = {
      actorId: String(form.get("actorId")),
      organizationId: String(form.get("organizationId")),
      projectId: String(form.get("projectId")),
    };
    setConnection(next);
    window.sessionStorage.setItem("vai-decision-center-context", JSON.stringify(next));
    setBusy(true);
    try {
      const [response, reviewResponse] = await Promise.all([
        fetch(`${API_URL}/api/v1/projects/${next.projectId}/decision-center/queue`, { headers: headers(next) }),
        fetch(`${API_URL}/api/v1/projects/${next.projectId}/decision-center/review-queues`, { headers: headers(next) }),
      ]);
      if (!response.ok) throw new Error(await readError(response));
      if (!reviewResponse.ok) throw new Error(await readError(reviewResponse));
      setQueue((await response.json()) as QueueItem[]);
      setReviewQueues((await reviewResponse.json()) as ReviewQueues);
      setMessage(null);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to load the decision queue");
    } finally {
      setBusy(false);
    }
  }

  async function exportReport(path: string, filename: string) {
    if (!connection) return;
    setBusy(true);
    try {
      const response = await fetch(
        `${API_URL}/api/v1/projects/${connection.projectId}/decision-center/reports/${path}`,
        { headers: headers(connection) },
      );
      if (!response.ok) throw new Error(await readError(response));
      const report = (await response.json()) as Report;
      const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      link.click();
      URL.revokeObjectURL(url);
      setMessage(`${report.report_type.replaceAll("_", " ")} exported with semantic metadata.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to export report");
    } finally {
      setBusy(false);
    }
  }

  async function exportQueueCsv() {
    if (!connection) return;
    setBusy(true);
    try {
      const response = await fetch(`${API_URL}/api/v1/projects/${connection.projectId}/decision-center/exports/decision-queue.csv`, { headers: headers(connection) });
      if (!response.ok) throw new Error(await readError(response));
      download(await response.blob(), "decision-queue.csv");
      setMessage(`Decision queue CSV exported in ${response.headers.get("X-VAI-Project-Timezone") ?? "project time"}; recommendation and human decision remain separate columns.`);
    } catch (error) { setMessage(error instanceof Error ? error.message : "Unable to export queue"); }
    finally { setBusy(false); }
  }

  return (
    <div className="decision-center-grid">
      <section className="workbench-card full-width" aria-labelledby="center-context">
        <span className="step-number">01</span>
        <h2 id="center-context">Project context</h2>
        <form className="center-connect" onSubmit={connect}>
          <label>Actor ID<input name="actorId" defaultValue={savedContext?.actorId ?? "local-admin"} required /></label>
          <label>Organization UUID<input name="organizationId" defaultValue={savedContext?.organizationId} required /></label>
          <label>Project UUID<input name="projectId" defaultValue={savedContext?.projectId} required /></label>
          <button disabled={busy}>Load governed queue</button>
        </form>
      </section>

      <section className="workbench-card full-width" aria-labelledby="review-queues-heading">
        <span className="step-number">02</span><h2 id="review-queues-heading">Dedicated review queues</h2>
        <div className="review-queue-grid">
          {reviewQueues ? reviewQueueNames.map((name) => { const entries = reviewQueues[name]; return <article key={name}>
            <strong>{name.replaceAll("_", " ")}</strong><span>{entries.length}</span>
            <small>{entries[0]?.required_role ?? "No pending role"}</small>
            {entries[0] ? <p>{entries[0].case.case_number} · {entries[0].reason} · {formatProjectTime(entries[0].deadline, reviewQueues.project_timezone)}</p> : null}
          </article>; }) : <p className="empty-state">Load a project to inspect governed review queues.</p>}
        </div>
      </section>

      <section className="workbench-card full-width" aria-labelledby="queue-heading">
        <div className="card-heading">
          <div><span className="step-number">03</span><h2 id="queue-heading">Management attention queue</h2></div>
          <div className="center-filters">
            <label>Lifecycle<select value={lifecycleFilter} onChange={(event) => { setLifecycleFilter(event.target.value); window.sessionStorage.setItem("vai-lifecycle-filter", event.target.value); }}><option value="OPEN">Open</option><option value="CLOSED">Closed</option><option value="ALL">All</option></select></label>
            <label>Governance<select value={governanceFilter} onChange={(event) => { setGovernanceFilter(event.target.value); window.sessionStorage.setItem("vai-governance-filter", event.target.value); }}><option value="ALL">All routes</option><option>HUMAN_REVIEW_REQUIRED</option><option>APPROVAL_REQUIRED</option><option>ESCALATION_REQUIRED</option><option>GOVERNANCE_BLOCKED</option><option>AUTHORIZED_TO_PROCEED</option></select></label>
          </div>
        </div>
        <p className="panel-note">Sorted by governed priority and urgency. Confidence is shown separately and never drives the visual priority label.</p>
        <div className="queue-table-wrap">
          <table className="decision-queue-table">
            <caption className="sr-only">Decision Cases ordered for management attention</caption>
            <thead><tr><th scope="col">Case</th><th scope="col">Priority / urgency</th><th scope="col">Recommendation / decision</th><th scope="col">Readiness / authority</th><th scope="col">Next action</th><th scope="col">Export</th></tr></thead>
            <tbody>{visible.map((item) => <tr key={item.case_id}>
              <td><strong>{item.case_number}</strong><span>{item.title}</span><small>{item.controlled_object_count} objects · owner {item.owner_actor_id}</small></td>
              <td><span className="priority-label">{item.priority_band ?? "UNRANKED"}</span><strong>{item.urgency ?? "UNKNOWN URGENCY"}</strong><small>Score {item.priority_score ?? "unknown"} · confidence {item.overall_confidence ?? "unknown"}</small></td>
              <td><span>LATEST SYSTEM: {item.recommended_disposition ?? "NO RECOMMENDATION"}</span><strong>HUMAN: {item.human_disposition ?? "NOT DECIDED"}</strong><small>{item.recommendation_agreement ?? "Agreement not recorded"} with signed basis {item.decision_basis_recommendation ?? "unknown"}</small></td>
              <td><span>{item.readiness ?? "NOT ASSESSED"}</span><strong>{item.governance_state}</strong><small>{item.open_limitation_count} open limitations · {item.active_response_count} active responses</small></td>
              <td><strong>{item.next_action.replaceAll("_", " ")}</strong><small>Deadline {formatProjectTime(item.next_deadline, reviewQueues?.project_timezone)}</small><small>Consequence {item.consequence_window ?? "unknown"}</small></td>
              <td><button className="text-button" disabled={busy} onClick={() => exportReport(`case-dossier/${item.case_id}`, `${item.case_number}-dossier.json`)}>Case dossier</button></td>
            </tr>)}</tbody>
          </table>
          {connection && visible.length === 0 ? <p className="empty-state">No cases match the selected governed filters.</p> : null}
        </div>
      </section>

      <section className="workbench-card" aria-labelledby="reports-heading">
        <span className="step-number">04</span><h2 id="reports-heading">Governed exports</h2>
        <p className="panel-note">JSON exports preserve source IDs, timestamps, policy/formula versions, truth boundaries, and recommendation/decision separation.</p>
        <button disabled={busy || !connection} onClick={() => exportReport("weekly-decision-brief", "weekly-decision-brief.json")}>Export weekly decision brief</button>
        <button disabled={busy || !connection} onClick={() => exportReport("project-control-exceptions", "project-control-exceptions.json")}>Export exception report</button>
        <button disabled={busy || !connection} onClick={() => exportReport("pilot-kpis", "pilot-kpis.json")}>Export pilot KPI report</button>
        <button disabled={busy || !connection} onClick={() => exportReport("governance-conformity", "governance-conformity.json")}>Export conformity report</button>
        <button disabled={busy || !connection} onClick={exportQueueCsv}>Export decision queue CSV</button>
      </section>
      <section className="workbench-card" aria-labelledby="workflow-heading">
        <span className="step-number">05</span><h2 id="workflow-heading">Continue the workflow</h2>
        <p className="panel-note">Use the detailed case workbench for evidence, analysis, lifecycle commands, and the chronological ledger.</p>
        <Link className="status" href="/cases">Open Decision Cases →</Link>
      </section>
      {message ? <p className="workbench-message full-width" role="status">{message}</p> : null}
    </div>
  );
}

async function readError(response: Response): Promise<string> {
  const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
  return payload?.detail ?? `Request failed with status ${response.status}`;
}

function formatProjectTime(value: string | null, timezone = "UTC"): string {
  if (!value) return "unknown";
  return `${new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short", timeZone: timezone }).format(new Date(value))} (${timezone})`;
}

function savedValue(key: string, fallback: string): string {
  return typeof window === "undefined" ? fallback : window.sessionStorage.getItem(key) ?? fallback;
}

function savedJson<T>(key: string): T | null {
  if (typeof window === "undefined") return null;
  try { return JSON.parse(window.sessionStorage.getItem(key) ?? "null") as T | null; }
  catch { return null; }
}

function download(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url; link.download = filename; link.click(); URL.revokeObjectURL(url);
}
