"use client";

import { FormEvent, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_VAI_API_URL ?? "http://localhost:8000";
type Connection = { actorId: string; organizationId: string; projectId: string; caseId: string };
type Policy = { policy_version: string; lower_rate_factor: string; upper_rate_factor: string; lower_cost_factor: string; upper_cost_factor: string; confidence_decay_per_30_days: string; confidence_floor: string; maximum_horizon_days: number; validity_days: number; rationale: string };
type Forecast = { id: string; forecast_number: number; target: string; scenario_type: string; method: string; status: string; semantic_state: string; result_unit: string; result_point: string; result_lower: string; result_upper: string; horizon_days: number; upstream_confidence: string; horizon_confidence: string; validity: string; valid_until: string; assumptions: string[]; limitations: { code: string; description: string }[] };

export function ForecastWorkbench() {
  const [connection, setConnection] = useState<Connection | null>(null);
  const [policies, setPolicies] = useState<Policy[]>([]);
  const [forecasts, setForecasts] = useState<Forecast[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  function headers(active = connection): HeadersInit { if (!active) return {}; return { "Content-Type": "application/json", "X-VAI-Actor-ID": active.actorId, "X-VAI-Organization-ID": active.organizationId }; }
  async function connect(event: FormEvent<HTMLFormElement>) { event.preventDefault(); const form = new FormData(event.currentTarget); const next = { actorId: String(form.get("actorId")), organizationId: String(form.get("organizationId")), projectId: String(form.get("projectId")), caseId: String(form.get("caseId")) }; setConnection(next); await refresh(next); }
  async function refresh(active = connection) {
    if (!active) return; setBusy(true);
    try {
      const [policyResponse, forecastResponse] = await Promise.all([
        fetch(`${API_URL}/api/v1/projects/${active.projectId}/forecast/policies`, { headers: headers(active) }),
        fetch(`${API_URL}/api/v1/projects/${active.projectId}/decision-cases/${active.caseId}/forecasts`, { headers: headers(active) }),
      ]);
      if (!policyResponse.ok) throw new Error(await readError(policyResponse));
      if (!forecastResponse.ok) throw new Error(await readError(forecastResponse));
      setPolicies((await policyResponse.json()) as Policy[]); setForecasts((await forecastResponse.json()) as Forecast[]); setMessage(null);
    } catch (caught) { setMessage(errorMessage(caught)); } finally { setBusy(false); }
  }
  return <div className="workbench-grid">
    <section className="workbench-card full-width"><span className="step-number">01</span><h2>Case context</h2><form className="inline-form" onSubmit={connect}><label>Actor ID<input name="actorId" defaultValue="local-admin" required /></label><label>Organization UUID<input name="organizationId" required /></label><label>Project UUID<input name="projectId" required /></label><label>Decision Case UUID<input name="caseId" required /></label><button>Load history</button><button type="button" className="secondary" disabled={!connection || busy} onClick={() => refresh()}>Refresh</button></form></section>
    <section className="workbench-card"><span className="step-number">02</span><h2>Visible forecast policies</h2><div className="mini-ledger">{policies.map((policy) => <div key={policy.policy_version}><strong>{policy.policy_version}</strong><span>Rate {policy.lower_rate_factor}–{policy.upper_rate_factor} · cost {policy.lower_cost_factor}–{policy.upper_cost_factor}</span><small>{Number(policy.confidence_decay_per_30_days) * 100}% confidence decay / 30 days · valid {policy.validity_days} days · maximum horizon {policy.maximum_horizon_days} days</small><small>{policy.rationale}</small></div>)}</div></section>
    <section className="workbench-card"><span className="step-number">03</span><h2>Semantic boundary</h2><div className="semantic-boundary"><span><b>FORECAST</b> Continued performance or an authorized active response.</span><span><b>SCENARIO</b> Hypothetical assumptions; never authorized state.</span><span><b>FACT / BASELINE</b> Never rewritten by this module.</span></div></section>
    <section className="workbench-card full-width"><div className="card-heading"><div><span className="step-number">04</span><h2>Immutable forecast history</h2></div><span className="ledger-count">{forecasts.length} projections</span></div><div className="forecast-grid">{forecasts.map((item) => <article className="forecast-card" key={item.id}><div><span className={`truth ${item.semantic_state.toLowerCase()}`}>{item.semantic_state}</span><small>#{item.forecast_number} · {item.scenario_type.replaceAll("_", " ")}</small></div><strong>{item.target.replaceAll("_", " ")}</strong><span>{item.result_point} {item.result_unit === "DATE" ? "" : item.result_unit}</span><small>Range {item.result_lower} → {item.result_upper} · {item.method.replaceAll("_", " ")}</small><small>Confidence {item.upstream_confidence} → {item.horizon_confidence} over {item.horizon_days} days</small><b>{item.validity.replaceAll("_", " ")} · valid until {new Date(item.valid_until).toLocaleString()}</b>{item.assumptions.map((assumption) => <small key={assumption}>Assumption: {assumption}</small>)}{item.limitations.map((limitation) => <small key={limitation.code}>{limitation.code}: {limitation.description}</small>)}</article>)}</div></section>
    {message ? <p className="workbench-message full-width" role="status">{message}</p> : null}
  </div>;
}
function errorMessage(caught: unknown): string { return caught instanceof Error ? caught.message : "Forecast request failed"; }
async function readError(response: Response): Promise<string> { const payload = (await response.json().catch(() => null)) as { detail?: string | { msg?: string }[] } | null; if (typeof payload?.detail === "string") return payload.detail; if (Array.isArray(payload?.detail)) return payload.detail.map((entry) => entry.msg).join("; "); return `Request failed with status ${response.status}`; }
