"use client";

import { FormEvent, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_VAI_API_URL ?? "http://localhost:8000";
type Connection = { actorId: string; organizationId: string; projectId: string };
type Policy = { policy_version: string; on_time_tolerance_days: string; maximum_schedule_age_days: number; require_dependency_for_consequence: boolean; allow_calculated_float: boolean; rationale: string };
type Activity = { code: string; name: string; planned_start: string; planned_finish: string; calendar_id: string; total_float_days: string | null; controlled_object_code: string | null };
type Dependency = { predecessor_code: string; successor_code: string; relation_type: string; lag_days: string };
type Milestone = { code: string; name: string; planned_date: string; activity_code: string | null; material: boolean };
type Network = { context_id: string; version_number: number; effective_from: string; data_date: string; activity_count: number; dependency_count: number; milestone_count: number; calendar_count: number; activities: Activity[]; dependencies: Dependency[]; milestones: Milestone[] };

export function ScheduleWorkbench() {
  const [connection, setConnection] = useState<Connection | null>(null);
  const [network, setNetwork] = useState<Network | null>(null);
  const [policies, setPolicies] = useState<Policy[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function headers(active = connection): HeadersInit {
    if (!active) return {};
    return { "Content-Type": "application/json", "X-VAI-Actor-ID": active.actorId, "X-VAI-Organization-ID": active.organizationId };
  }

  async function connect(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const next = { actorId: String(form.get("actorId")), organizationId: String(form.get("organizationId")), projectId: String(form.get("projectId")) };
    setConnection(next);
    await refresh(next);
  }

  async function refresh(active = connection) {
    if (!active) return;
    setBusy(true);
    try {
      const [networkResponse, policyResponse] = await Promise.all([
        fetch(`${API_URL}/api/v1/projects/${active.projectId}/schedule/network`, { headers: headers(active) }),
        fetch(`${API_URL}/api/v1/projects/${active.projectId}/schedule/policies`, { headers: headers(active) }),
      ]);
      if (!networkResponse.ok) throw new Error(await readError(networkResponse));
      if (!policyResponse.ok) throw new Error(await readError(policyResponse));
      setNetwork((await networkResponse.json()) as Network);
      setPolicies((await policyResponse.json()) as Policy[]);
      setMessage(null);
    } catch (caught) {
      setMessage(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  async function createPolicy(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!connection) return;
    const form = new FormData(event.currentTarget);
    setBusy(true);
    try {
      const response = await fetch(`${API_URL}/api/v1/projects/${connection.projectId}/schedule/policies`, {
        method: "POST",
        headers: headers(),
        body: JSON.stringify({
          policy_version: form.get("policyVersion"),
          on_time_tolerance_days: form.get("tolerance"),
          maximum_schedule_age_days: Number(form.get("maximumAge")),
          require_dependency_for_consequence: true,
          allow_calculated_float: true,
          rationale: form.get("rationale"),
        }),
      });
      if (!response.ok) throw new Error(await readError(response));
      setMessage("Immutable schedule analysis policy created.");
      await refresh();
    } catch (caught) {
      setMessage(errorMessage(caught));
      setBusy(false);
    }
  }

  return <div className="workbench-grid">
    <section className="workbench-card full-width"><span className="step-number">01</span><h2>Project context</h2><form className="inline-form" onSubmit={connect}><label>Actor ID<input name="actorId" defaultValue="local-admin" required /></label><label>Organization UUID<input name="organizationId" required /></label><label>Project UUID<input name="projectId" required /></label><button>Load schedule</button><button type="button" className="secondary" disabled={!connection || busy} onClick={() => refresh()}>Refresh</button></form></section>
    <section className="workbench-card"><span className="step-number">02</span><h2>Network identity</h2>{network ? <div className="network-summary"><strong>Authorized v{network.version_number}</strong><span>Data date {network.data_date}</span><small>{network.context_id}</small><div className="network-counts"><b>{network.activity_count} activities</b><b>{network.dependency_count} links</b><b>{network.milestone_count} milestones</b><b>{network.calendar_count} calendars</b></div></div> : <p className="empty-state">Connect a project with an authorized schedule.</p>}</section>
    <section className="workbench-card"><span className="step-number">03</span><h2>Analysis policy</h2><div className="mini-ledger">{policies.map((policy) => <div key={policy.policy_version}><strong>{policy.policy_version}</strong><span>±{policy.on_time_tolerance_days} day tolerance · maximum age {policy.maximum_schedule_age_days} days</span><small>{policy.rationale}</small></div>)}</div><form className="stack-form compact" onSubmit={createPolicy}><label>New policy version<input name="policyVersion" required /></label><div className="form-pair"><label>Tolerance days<input name="tolerance" type="number" min="0" max="30" step="0.1" defaultValue="0.5" required /></label><label>Maximum age<input name="maximumAge" type="number" min="1" defaultValue="14" required /></label></div><label>Rationale<input name="rationale" required /></label><button disabled={!connection || busy}>Create policy version</button></form></section>
    <section className="workbench-card full-width"><div className="card-heading"><div><span className="step-number">04</span><h2>Authorized activity network</h2></div></div><div className="schedule-network">{network?.activities.map((activity) => <article key={activity.code}><strong>{activity.code} · {activity.name}</strong><span>{activity.planned_start} → {activity.planned_finish}</span><small>{activity.controlled_object_code ?? "UNMAPPED"} · calendar {activity.calendar_id} · float {activity.total_float_days ?? "calculate"}</small></article>)}</div><div className="dependency-list">{network?.dependencies.map((dependency) => <span key={`${dependency.predecessor_code}-${dependency.successor_code}`}>{dependency.predecessor_code} → {dependency.successor_code} · {dependency.relation_type.replaceAll("_", " ")} · lag {dependency.lag_days}</span>)}</div><div className="dependency-list milestones">{network?.milestones.map((milestone) => <span key={milestone.code}>{milestone.code} · {milestone.planned_date} · {milestone.activity_code ?? "unlinked"}{milestone.material ? " · MATERIAL" : ""}</span>)}</div></section>
    {message ? <p className="workbench-message full-width" role="status">{message}</p> : null}
  </div>;
}

function errorMessage(caught: unknown): string { return caught instanceof Error ? caught.message : "Schedule request failed"; }
async function readError(response: Response): Promise<string> { const payload = (await response.json().catch(() => null)) as { detail?: string | { msg?: string }[] } | null; if (typeof payload?.detail === "string") return payload.detail; if (Array.isArray(payload?.detail)) return payload.detail.map((entry) => entry.msg).join("; "); return `Request failed with status ${response.status}`; }
