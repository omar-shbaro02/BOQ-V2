"use client";

import { FormEvent, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_VAI_API_URL ?? "http://localhost:8000";
type Connection = { actorId: string; organizationId: string; projectId: string; caseId: string };
type RecoveryQualification = {
  qualified: boolean; reason_codes: string[]; conclusion_boundary: string;
  comparisons: { response_forecast_id: string; continued_forecast_id: string; target: string; continued_point: string; response_point: string; result_unit: string }[];
};
type Assessment = {
  id: string; assessment_number: number; assessment_status: string;
  consequence_severity: string; urgency: string; priority_band: string; priority_score: string;
  truth_confidence: string; forecast_confidence: string; consequence_confidence: string;
  overall_confidence: string; upstream_confidence_ceiling: string; urgency_margin_days: number | null;
  priority_reason_codes: string[]; decision_clocks: { clock_type: string; duration_days: number | null; target_date: string | null }[];
  consequence_paths: (Record<string, unknown> & { recovery_qualification?: RecoveryQualification })[]; limitations: Record<string, unknown>[];
  policy_version: string; formula_version: string;
};
type Policy = { policy_version: string; rationale: string; [key: string]: unknown };

export function ImpactWorkbench() {
  const [connection, setConnection] = useState<Connection | null>(null);
  const [history, setHistory] = useState<Assessment[]>([]);
  const [policies, setPolicies] = useState<Policy[]>([]);
  const [version, setVersion] = useState(1);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  function headers(active: Connection) { return { "Content-Type": "application/json", "X-VAI-Actor-ID": active.actorId, "X-VAI-Organization-ID": active.organizationId }; }
  function base(active: Connection) { return `${API_URL}/api/v1/projects/${active.projectId}`; }
  async function checked(response: Response) {
    const value = await response.json();
    if (!response.ok) throw new Error(typeof value.detail === "string" ? value.detail : JSON.stringify(value.detail));
    return value;
  }
  async function load(active: Connection) {
    const [items, configured, current] = await Promise.all([
      fetch(`${base(active)}/decision-cases/${active.caseId}/impact-assessments`, { headers: headers(active) }).then(checked),
      fetch(`${base(active)}/impact/policies`, { headers: headers(active) }).then(checked),
      fetch(`${base(active)}/decision-cases/${active.caseId}`, { headers: headers(active) }).then(checked),
    ]);
    setHistory(items); setPolicies(configured); setVersion(current.version);
  }
  async function connect(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = new FormData(event.currentTarget);
    const active = Object.fromEntries(["actorId", "organizationId", "projectId", "caseId"].map(key => [key, String(form.get(key))])) as Connection;
    setBusy(true); setMessage(null); setConnection(null); setHistory([]); setPolicies([]);
    try { await load(active); setConnection(active); } catch (error) { setMessage(String(error)); } finally { setBusy(false); }
  }
  async function assess(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!connection) return;
    const form = new FormData(event.currentTarget);
    const body: Record<string, unknown> = { expected_version: version };
    for (const key of ["snapshot_id", "controlled_object_id", "schedule_assessment_id", "cost_assessment_id", "progress_evaluation_id", "consequence_date", "recovery_window_end", "policy_version"]) {
      if (form.get(key)) body[key] = String(form.get(key));
    }
    for (const key of ["verification_duration_days", "approval_duration_days", "mobilization_duration_days"]) body[key] = Number(form.get(key));
    body.forecast_projection_ids = String(form.get("forecast_projection_ids") ?? "")
      .split(",").map(value => value.trim()).filter(Boolean);
    setBusy(true); setMessage(null);
    try {
      await checked(await fetch(`${base(connection)}/decision-cases/${connection.caseId}/impact-assessments`, { method: "POST", headers: { ...headers(connection), "Idempotency-Key": crypto.randomUUID() }, body: JSON.stringify(body) }));
      await load(connection);
    } catch (error) { setMessage(String(error)); } finally { setBusy(false); }
  }
  return <div className="workbench-grid">
    <section className="workbench-card full-width"><h2>Case context</h2><form className="inline-form" onSubmit={connect}>
      <label>Actor ID<input name="actorId" defaultValue="local-admin" required /></label>
      <label>Organization UUID<input name="organizationId" required /></label><label>Project UUID<input name="projectId" required /></label><label>Case UUID<input name="caseId" required /></label>
      <button disabled={busy}>Load case</button>
    </form></section>
    {connection && <section className="workbench-card full-width"><h2>Create assessment</h2><p>Case version {version}. Select at least one specialist result from the same snapshot and controlled object. Clock durations are explicit planning inputs in calendar days.</p>
      <form className="inline-form" onSubmit={assess}>
        <label>Snapshot UUID<input name="snapshot_id" required /></label><label>Controlled object UUID<input name="controlled_object_id" required /></label>
        <label>Schedule assessment UUID<input name="schedule_assessment_id" /></label><label>Cost assessment UUID<input name="cost_assessment_id" /></label><label>Progress evaluation UUID<input name="progress_evaluation_id" /></label>
        <label>Forecast UUIDs (comma separated)<input name="forecast_projection_ids" /></label>
        <label>Consequence date<input name="consequence_date" type="date" /></label><label>Recovery window end<input name="recovery_window_end" type="date" /></label>
        {[["verification_duration_days", "Verification days"], ["approval_duration_days", "Approval days"], ["mobilization_duration_days", "Mobilization days"]].map(([name, label]) => <label key={name}>{label}<input name={name} type="number" min="0" max="365" defaultValue="0" required /></label>)}
        <label>Policy<select name="policy_version">{policies.map(policy => <option key={policy.policy_version}>{policy.policy_version}</option>)}</select></label>
        <button disabled={busy}>Assess consequence and priority</button>
      </form>{policies.map(policy => <details key={policy.policy_version}><summary>{policy.policy_version}: {policy.rationale}</summary><pre style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{JSON.stringify(policy, null, 2)}</pre></details>)}
    </section>}
    <section className="workbench-card full-width"><h2>Assessment history</h2>{connection && history.length === 0 && <p>No assessments yet.</p>}
      {history.map(item => <article className="forecast-card" key={item.id}>
        <h3>Assessment {item.assessment_number} · {item.assessment_status}</h3>
        <p>Consequence: <strong>{item.consequence_severity}</strong> · Urgency: <strong>{item.urgency}</strong> · Priority: <strong>{item.priority_band}</strong> ({item.priority_score})</p>
        <p>Confidence — truth {item.truth_confidence}, forecast {item.forecast_confidence}, consequence {item.consequence_confidence}, overall {item.overall_confidence}; upstream ceiling {item.upstream_confidence_ceiling}.</p>
        <p>Decision margin: {item.urgency_margin_days === null ? "Unknown" : `${item.urgency_margin_days} days`}</p>
        <ul>{item.decision_clocks.map(clock => <li key={clock.clock_type}>{clock.clock_type.replaceAll("_", " ")}: {clock.duration_days === null ? "Unknown" : `${clock.duration_days} days`}{clock.target_date ? ` · ${clock.target_date}` : ""}</li>)}</ul>
        <p>Ranking reasons: {item.priority_reason_codes.join(", ")}</p>
        {item.limitations.map((limitation, index) => <p role="note" key={index}>{String(limitation.code)}: {String(limitation.description ?? JSON.stringify(limitation))}</p>)}
        {item.consequence_paths.filter(path => path.source === "AUTHORIZED_RESPONSE").map((path, index) => {
          const recovery = path.recovery_qualification;
          return <section key={index}><h4>Recovery option · {String(path.authorization_reference)}</h4>
            {recovery ? <><p>{recovery.qualified ? "Projected benefit qualifies" : "Does not qualify for priority reduction"}</p>
              <p>{recovery.reason_codes.join(", ")}</p>
              {recovery.comparisons.map(comparison => <p key={`${comparison.response_forecast_id}-${comparison.continued_forecast_id}`}>{comparison.target}: continued {comparison.continued_point} → response {comparison.response_point} ({comparison.result_unit})</p>)}
              <small>{recovery.conclusion_boundary}</small></> : <p>Qualification was not recorded in this historical assessment.</p>}
          </section>;
        })}
        <details><summary>Consequence paths and lineage</summary><pre style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{JSON.stringify(item.consequence_paths, null, 2)}</pre></details>
        <small>{item.policy_version} · {item.formula_version}</small>
      </article>)}
    </section>
    {message && <p className="workbench-message full-width" role="alert">{message}</p>}
  </div>;
}
