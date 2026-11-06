"use client";

import { FormEvent, useCallback, useState } from "react";
import { ProjectContextFields } from "../project-context-fields";

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
  const clearProject = useCallback(() => { setConnection(null); setBudget(null); setPolicies([]); setRecords([]); setMessage(null); }, []);

  function headers(active = connection): HeadersInit {
    if (!active) return {};
    return { "Content-Type": "application/json", "X-VAI-Actor-ID": active.actorId, "X-VAI-Organization-ID": active.organizationId };
  }
  async function connect(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const next = { actorId: String(form.get("actorId")), organizationId: String(form.get("organizationId")), projectId: String(form.get("projectId")) };
    setConnection(next);
    setBudget(null); setPolicies([]); setRecords([]);
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
      const issues: string[] = [];
      if (budgetResponse.ok) setBudget(await budgetResponse.json() as Budget);
      else { setBudget(null); issues.push(`Budget: ${await readError(budgetResponse)}`); }
      if (policyResponse.ok) setPolicies(await policyResponse.json() as Policy[]);
      else { setPolicies([]); issues.push(`Policy: ${await readError(policyResponse)}`); }
      if (recordResponse.ok) setRecords(await recordResponse.json() as CostRecord[]);
      else { setRecords([]); issues.push(`Cost records: ${await readError(recordResponse)}`); }
      setMessage(issues.length ? issues.join(" · ") : null);
      return issues.join(" · ");
    } catch (caught) { const issue = errorMessage(caught); setMessage(issue); return issue; } finally { setBusy(false); }
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
      const issues = await refresh();
      setMessage(`Cost record saved.${issues ? ` ${issues}` : ""}`);
    } catch (caught) { setMessage(errorMessage(caught)); setBusy(false); }
  }
  return <div className="workbench-grid cost-simple">
    <section className="workbench-card full-width"><h2>Project</h2><form className="inline-form context-form" onSubmit={connect}><fieldset className="cost-project-fields" disabled={busy}><ProjectContextFields onConnectionChange={clearProject} /></fieldset><button disabled={busy}>Load cost controls</button><button type="button" className="secondary" disabled={!connection || busy} onClick={() => refresh()}>Refresh</button></form></section>
    {budget ? <section className="cost-budget-strip full-width" aria-label="Approved budget"><span>Approved budget <strong>{budget.currency} {budget.current_authorized_budget}</strong></span><details><summary>Budget breakdown</summary><p>Original budget: {budget.approved_budget} · Approved changes: {budget.authorized_changes}</p><small>Approved version {budget.version_number} · {budget.measurement_basis} · {budget.context_id}</small></details></section> : null}
    {policies.length > 0 ? <details className="cost-policy full-width"><summary>Cost analysis rules</summary><div className="mini-ledger">{policies.map((policy) => <div key={policy.policy_version}><strong>{policy.policy_version}</strong><span>Alignment ±{Number(policy.alignment_tolerance) * 100}% · forecast after {Number(policy.minimum_earned_ratio_for_forecast) * 100}% earned</span><small>{policy.rationale}</small></div>)}</div></details> : null}
    <section className="workbench-card full-width"><h2>Add a cost record</h2><p className="planning-field-help">Enter the amount and reporting dates from your supporting evidence.</p><form key={connection?.projectId ?? "no-project"} className="stack-form compact" onSubmit={normalize}><fieldset disabled={!connection || busy}><label>Supporting evidence reference<input name="evidenceId" required aria-describedby="cost-evidence-help" /></label><small id="cost-evidence-help">Use the evidence item reference saved on the Evidence page.</small><div className="form-pair"><label>Cost type<select name="recordKind"><option value="ACTUAL">Actual cost</option><option value="ACCRUAL">Accrued cost</option><option value="COMMITMENT">Committed cost</option><option value="EARNED_VALUE">Earned value</option><option value="PHYSICAL_VALUE">Physical value</option><option value="BOQ_VALUE">BOQ value</option></select></label><label>Amount<input name="amount" type="number" min="0" step="any" required /></label></div><label>Currency<input name="currency" defaultValue={budget?.currency ?? "USD"} required /></label><div className="form-pair"><label>Period start<input name="periodStart" type="date" required /></label><label>Period end<input name="periodEnd" type="date" required /></label></div><details className="planning-optional"><summary>Additional cost details (optional)</summary><label>Measurement basis<input name="basis" defaultValue="COST_VALUE" required /></label><label>Commercial effect<select name="commercialEffect"><option>NONE</option><option>TIMING</option><option>PROCUREMENT</option><option>PREPAYMENT</option><option>RETENTION</option><option>MOBILIZATION</option></select></label><label>Evidence-backed explanation<input name="explanation" placeholder="Required when an effect is selected" /></label></details><button disabled={!connection || busy}>{busy ? "Saving…" : "Save cost record"}</button></fieldset></form>{!connection ? <p className="planning-field-help">Load a project above to add its cost records.</p> : null}</section>
    {records.length > 0 ? <section className="workbench-card full-width"><h2>Saved cost records</h2><div className="mini-ledger">{records.map((record) => <div key={record.id}><strong>{record.record_kind.replaceAll("_", " ")} · {record.currency} {record.amount}</strong><span>{record.reporting_period_start} → {record.reporting_period_end} · {record.commercial_effect}</span><small>{record.truth_type} · scope {record.controlled_object_id} · {record.id}</small></div>)}</div></section> : null}
    {message ? <p className="workbench-message full-width" role="status">{message}</p> : null}
  </div>;
}

function errorMessage(caught: unknown): string { return caught instanceof Error ? caught.message : "Cost request failed"; }
async function readError(response: Response): Promise<string> { const payload = (await response.json().catch(() => null)) as { detail?: string | { msg?: string }[] } | null; if (typeof payload?.detail === "string") return payload.detail; if (Array.isArray(payload?.detail)) return payload.detail.map((entry) => entry.msg).join("; "); return `Request failed with status ${response.status}`; }
