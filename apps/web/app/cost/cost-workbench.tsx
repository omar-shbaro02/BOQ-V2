"use client";

import { FormEvent, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_VAI_API_URL ?? "http://localhost:8000";
type Connection = { actorId: string; organizationId: string; projectId: string };
type Budget = { context_id: string; version_number: number; currency: string; approved_budget: string; authorized_changes: string; current_authorized_budget: string; measurement_basis: string };
type Policy = { policy_version: string; alignment_tolerance: string; minimum_earned_ratio_for_forecast: string; include_accruals_in_recognized_cost: boolean; rationale: string };
type CostRecord = { id: string; record_kind: string; amount: string; currency: string; reporting_period_start: string; reporting_period_end: string; commercial_effect: string; truth_type: string; controlled_object_id: string };

export function CostWorkbench() {
  const [connection, setConnection] = useState<Connection | null>(null);
  const [budget, setBudget] = useState<Budget | null>(null);
  const [policies, setPolicies] = useState<Policy[]>([]);
  const [records, setRecords] = useState<CostRecord[]>([]);
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
      const [budgetResponse, policyResponse, recordResponse] = await Promise.all([
        fetch(`${API_URL}/api/v1/projects/${active.projectId}/cost/budget`, { headers: headers(active) }),
        fetch(`${API_URL}/api/v1/projects/${active.projectId}/cost/policies`, { headers: headers(active) }),
        fetch(`${API_URL}/api/v1/projects/${active.projectId}/cost/records`, { headers: headers(active) }),
      ]);
      if (!budgetResponse.ok) throw new Error(await readError(budgetResponse));
      if (!policyResponse.ok) throw new Error(await readError(policyResponse));
      if (!recordResponse.ok) throw new Error(await readError(recordResponse));
      setBudget((await budgetResponse.json()) as Budget);
      setPolicies((await policyResponse.json()) as Policy[]);
      setRecords((await recordResponse.json()) as CostRecord[]);
      setMessage(null);
    } catch (caught) { setMessage(errorMessage(caught)); } finally { setBusy(false); }
  }
  async function normalize(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!connection) return;
    const form = new FormData(event.currentTarget);
    const effect = String(form.get("commercialEffect"));
    setBusy(true);
    try {
      const response = await fetch(`${API_URL}/api/v1/projects/${connection.projectId}/cost/records`, {
        method: "POST", headers: headers(), body: JSON.stringify({
          evidence_item_id: form.get("evidenceId"), record_kind: form.get("recordKind"), amount: form.get("amount"), currency: form.get("currency"), measurement_basis: form.get("basis"), reporting_period_start: form.get("periodStart"), reporting_period_end: form.get("periodEnd"), commercial_effect: effect, effect_explanation: effect === "NONE" ? null : form.get("explanation"),
        }),
      });
      if (!response.ok) throw new Error(await readError(response));
      setMessage("Immutable cost record normalized with source lineage.");
      await refresh();
    } catch (caught) { setMessage(errorMessage(caught)); setBusy(false); }
  }
  return <div className="workbench-grid">
    <section className="workbench-card full-width"><span className="step-number">01</span><h2>Project context</h2><form className="inline-form" onSubmit={connect}><label>Actor ID<input name="actorId" defaultValue="local-admin" required /></label><label>Organization UUID<input name="organizationId" required /></label><label>Project UUID<input name="projectId" required /></label><button>Load cost controls</button><button type="button" className="secondary" disabled={!connection || busy} onClick={() => refresh()}>Refresh</button></form></section>
    <section className="workbench-card"><span className="step-number">02</span><h2>Authorized budget</h2>{budget ? <div className="network-summary"><strong>{budget.currency} {budget.current_authorized_budget}</strong><span>Approved {budget.approved_budget} + changes {budget.authorized_changes}</span><small>Authorized v{budget.version_number} · {budget.measurement_basis} · {budget.context_id}</small></div> : <p className="empty-state">Connect a project with an authorized budget.</p>}</section>
    <section className="workbench-card"><span className="step-number">03</span><h2>Visible policy</h2><div className="mini-ledger">{policies.map((policy) => <div key={policy.policy_version}><strong>{policy.policy_version}</strong><span>Alignment ±{Number(policy.alignment_tolerance) * 100}% · forecast after {Number(policy.minimum_earned_ratio_for_forecast) * 100}% earned</span><small>{policy.rationale}</small></div>)}</div></section>
    <section className="workbench-card"><span className="step-number">04</span><h2>Normalize cost evidence</h2><form className="stack-form compact" onSubmit={normalize}><label>Evidence UUID<input name="evidenceId" required /></label><div className="form-pair"><label>Record kind<select name="recordKind"><option>ACTUAL</option><option>ACCRUAL</option><option>COMMITMENT</option><option>EARNED_VALUE</option><option>PHYSICAL_VALUE</option><option>BOQ_VALUE</option></select></label><label>Amount<input name="amount" type="number" min="0" step="any" required /></label></div><div className="form-pair"><label>Currency<input name="currency" defaultValue="USD" required /></label><label>Basis<input name="basis" defaultValue="COST_VALUE" required /></label></div><div className="form-pair"><label>Period start<input name="periodStart" type="date" required /></label><label>Period end<input name="periodEnd" type="date" required /></label></div><label>Commercial effect<select name="commercialEffect"><option>NONE</option><option>TIMING</option><option>PROCUREMENT</option><option>PREPAYMENT</option><option>RETENTION</option><option>MOBILIZATION</option></select></label><label>Evidence-backed explanation<input name="explanation" placeholder="Required when an effect is selected" /></label><button disabled={!connection || busy}>Normalize record</button></form></section>
    <section className="workbench-card"><span className="step-number">05</span><h2>Cost ledger</h2><div className="mini-ledger">{records.map((record) => <div key={record.id}><strong>{record.record_kind.replaceAll("_", " ")} · {record.currency} {record.amount}</strong><span>{record.reporting_period_start} → {record.reporting_period_end} · {record.commercial_effect}</span><small>{record.truth_type} · scope {record.controlled_object_id} · {record.id}</small></div>)}</div></section>
    {message ? <p className="workbench-message full-width" role="status">{message}</p> : null}
  </div>;
}

function errorMessage(caught: unknown): string { return caught instanceof Error ? caught.message : "Cost request failed"; }
async function readError(response: Response): Promise<string> { const payload = (await response.json().catch(() => null)) as { detail?: string | { msg?: string }[] } | null; if (typeof payload?.detail === "string") return payload.detail; if (Array.isArray(payload?.detail)) return payload.detail.map((entry) => entry.msg).join("; "); return `Request failed with status ${response.status}`; }
