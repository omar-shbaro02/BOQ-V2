"use client";

import { FormEvent, useEffect, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_VAI_API_URL ?? "http://localhost:8000";

type Connection = { actorId: string; organizationId: string; projectId: string };
type Props = { connection: Connection; caseId: string; version: number; onChanged: () => Promise<void> };
type RecordRow = Record<string, unknown> & { id: string };
type Dossier = {
  orchestration_runs: RecordRow[];
  human_decisions: RecordRow[];
  response_proposals: RecordRow[];
  response_authorizations: RecordRow[];
  execution_observations: RecordRow[];
  outcomes: RecordRow[];
  learning_records: RecordRow[];
};

const empty: Dossier = { orchestration_runs: [], human_decisions: [], response_proposals: [], response_authorizations: [], execution_observations: [], outcomes: [], learning_records: [] };

export function GovernanceWorkflow({ connection, caseId, version, onChanged }: Props) {
  const [dossier, setDossier] = useState<Dossier>(empty);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function headers(idempotent = false): HeadersInit {
    return { "Content-Type": "application/json", "X-VAI-Actor-ID": connection.actorId, "X-VAI-Organization-ID": connection.organizationId, ...(idempotent ? { "Idempotency-Key": crypto.randomUUID() } : {}) };
  }

  async function loadDossier(): Promise<Dossier> {
    const response = await fetch(`${API_URL}/api/v1/projects/${connection.projectId}/decision-center/reports/case-dossier/${caseId}`, { headers: headers() });
    if (!response.ok) throw new Error(await readError(response));
    const report = (await response.json()) as { payload: Dossier };
    return report.payload;
  }

  useEffect(() => {
    let active = true;
    void fetch(`${API_URL}/api/v1/projects/${connection.projectId}/decision-center/reports/case-dossier/${caseId}`, { headers: { "X-VAI-Actor-ID": connection.actorId, "X-VAI-Organization-ID": connection.organizationId } })
      .then(async (response) => {
        if (!response.ok) throw new Error(await readError(response));
        return (await response.json()) as { payload: Dossier };
      })
      .then((report) => { if (active) setDossier(report.payload); })
      .catch((error: unknown) => { if (active) setMessage(error instanceof Error ? error.message : "Unable to load governance history"); });
    return () => { active = false; };
  }, [caseId, version, connection.actorId, connection.organizationId, connection.projectId]);

  async function command(path: string, body: object, success: string, idempotent = true) {
    setBusy(true);
    try {
      const response = await fetch(`${API_URL}/api/v1/projects/${connection.projectId}/decision-cases/${caseId}${path}`, { method: "POST", headers: headers(idempotent), body: JSON.stringify({ expected_version: version, ...body }) });
      if (!response.ok) throw new Error(await readError(response));
      setMessage(success);
      await onChanged();
      setDossier(await loadDossier());
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Governance command failed");
    } finally { setBusy(false); }
  }

  async function decide(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = new FormData(event.currentTarget);
    const amount = String(form.get("amount") ?? "").trim(); const currency = String(form.get("currency") ?? "").trim(); const authorization = String(form.get("responseAuthorization") ?? "").trim();
    await command("/human-decisions", { orchestration_run_id: form.get("runId"), authority_grant_id: form.get("grantId"), disposition: form.get("disposition"), recommendation_agreement: form.get("agreement"), rationale: form.get("rationale"), decision_amount: amount || null, currency: currency || null, response_authorization_reference: authorization || null, limitations: [] }, "Signed human decision recorded separately from the recommendation.");
  }

  async function propose(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = new FormData(event.currentTarget); const amount = String(form.get("amount") ?? "").trim(); const currency = String(form.get("currency") ?? "").trim();
    await command("/response-proposals", { human_decision_id: form.get("decisionId"), response_type: form.get("responseType"), objective: form.get("objective"), actions: [{ action: form.get("action"), owner: connection.actorId }], assumptions: String(form.get("assumptions") ?? "").split(";").map((value) => value.trim()).filter(Boolean), simulated_effects: { semantic_state: "SCENARIO", narrative: form.get("simulation") }, requested_amount: amount || null, currency: currency || null }, "Response proposal and scenario recorded.");
  }

  async function authorize(event: FormEvent<HTMLFormElement>) { event.preventDefault(); const form = new FormData(event.currentTarget); await command(`/response-proposals/${form.get("proposalId")}/authorization`, { authority_grant_id: form.get("grantId"), authorization_reference: form.get("reference") }, "Explicit response authorization recorded.", false); }
  async function observe(event: FormEvent<HTMLFormElement>) { event.preventDefault(); const form = new FormData(event.currentTarget); await command(`/response-proposals/${form.get("proposalId")}/execution`, { status: form.get("status"), observed_at: new Date().toISOString(), details: { note: form.get("note") }, evidence_item_ids: ids(form.get("evidenceIds")) }, "External execution status observed; no execution command was issued."); }
  async function outcome(event: FormEvent<HTMLFormElement>) { event.preventDefault(); const form = new FormData(event.currentTarget); await command(`/response-proposals/${form.get("proposalId")}/outcomes`, { classification: form.get("classification"), evidence_item_ids: ids(form.get("evidenceIds")), rationale: form.get("rationale") }, "Evidence-backed realized outcome recorded."); }
  async function learn(event: FormEvent<HTMLFormElement>) { event.preventDefault(); const form = new FormData(event.currentTarget); await command("/learning-records", { response_outcome_id: form.get("outcomeId"), category: form.get("category"), finding: form.get("finding"), contributing_factors: String(form.get("factors") ?? "").split(";").map((value) => value.trim()).filter(Boolean), calibration_notes: form.get("calibration") }, "Immutable learning and calibration record created."); }

  return <article className="workbench-card full-span governance-workflow"><h3>Human governance and response lifecycle</h3><p className="panel-note">System recommendations never sign decisions or authorize execution. Every command below records the authenticated human actor and exact authority lineage.</p>
    <div className="governance-forms">
      <form className="stack-form compact" onSubmit={decide}><h4>Signed human decision</h4><label>Orchestration run<select name="runId" required>{dossier.orchestration_runs.map((item) => <option key={item.id} value={item.id}>Run {String(item.run_number)} · {String(item.recommended_disposition)}</option>)}</select></label><label>Authority grant UUID<input name="grantId" required /></label><label>Disposition<select name="disposition"><option>NO_ACTION</option><option>MONITOR</option><option>VERIFY</option><option>INTERVENE</option><option>ESCALATE</option></select></label><label>Agreement<select name="agreement"><option>AGREE</option><option>PARTIAL_AGREEMENT</option><option>DISAGREE</option></select></label><label>Rationale<input name="rationale" minLength={20} required /></label><label>Amount<input name="amount" inputMode="decimal" /></label><label>Currency<input name="currency" pattern="[A-Z]{3}" /></label><label>Response authorization reference<input name="responseAuthorization" /></label><button disabled={busy || !dossier.orchestration_runs.length}>Record human decision</button></form>
      <form className="stack-form compact" onSubmit={propose}><h4>Response proposal / simulation</h4><label>Human decision<select name="decisionId" required>{dossier.human_decisions.map((item) => <option key={item.id} value={item.id}>{String(item.disposition)} · {item.id}</option>)}</select></label><label>Response type<input name="responseType" defaultValue="RECOVERY_PLAN" required /></label><label>Objective<input name="objective" minLength={20} required /></label><label>Action<input name="action" required /></label><label>Assumptions<input name="assumptions" placeholder="Separate with semicolons" /></label><label>Scenario effect<input name="simulation" minLength={3} required /></label><label>Amount<input name="amount" inputMode="decimal" /></label><label>Currency<input name="currency" pattern="[A-Z]{3}" /></label><button disabled={busy || !dossier.human_decisions.length}>Record proposal</button></form>
      <form className="stack-form compact" onSubmit={authorize}><h4>Explicit authorization</h4><label>Proposal<select name="proposalId" required>{dossier.response_proposals.map(option)}</select></label><label>Authority grant UUID<input name="grantId" required /></label><label>Authorization reference<input name="reference" required /></label><button disabled={busy || !dossier.response_proposals.length}>Authorize response</button></form>
      <form className="stack-form compact" onSubmit={observe}><h4>Observe execution</h4><label>Proposal<select name="proposalId" required>{dossier.response_proposals.map(option)}</select></label><label>Status<select name="status"><option>MOBILIZING</option><option>IN_PROGRESS</option><option>COMPLETED</option><option>FAILED</option><option>CANCELLED</option></select></label><label>Observation note<input name="note" required /></label><label>Attached evidence UUIDs<input name="evidenceIds" placeholder="Comma separated" /></label><button disabled={busy || !dossier.response_authorizations.length}>Record observation</button></form>
      <form className="stack-form compact" onSubmit={outcome}><h4>Realized outcome</h4><label>Proposal<select name="proposalId" required>{dossier.response_proposals.map(option)}</select></label><label>Classification<select name="classification"><option>ACHIEVED</option><option>PARTIALLY_ACHIEVED</option><option>NOT_ACHIEVED</option><option>NOT_YET_OBSERVABLE</option><option>INCONCLUSIVE</option></select></label><label>Evidence UUIDs<input name="evidenceIds" placeholder="Required unless not yet observable" /></label><label>Rationale<input name="rationale" minLength={20} required /></label><button disabled={busy || !dossier.execution_observations.length}>Record outcome</button></form>
      <form className="stack-form compact" onSubmit={learn}><h4>Learning / calibration</h4><label>Outcome<select name="outcomeId" required>{dossier.outcomes.map(option)}</select></label><label>Category<select name="category"><option>PRODUCT</option><option>DATA</option><option>POLICY</option><option>USABILITY</option><option>METHODOLOGY</option></select></label><label>Finding<input name="finding" minLength={20} required /></label><label>Factors<input name="factors" placeholder="Separate with semicolons" /></label><label>Calibration notes<input name="calibration" minLength={20} required /></label><button disabled={busy || !dossier.outcomes.length}>Record learning</button></form>
    </div>
    <div className="governance-history" aria-label="Governance history counts"><span>{dossier.human_decisions.length} decisions</span><span>{dossier.response_proposals.length} proposals</span><span>{dossier.response_authorizations.length} authorizations</span><span>{dossier.execution_observations.length} observations</span><span>{dossier.outcomes.length} outcomes</span><span>{dossier.learning_records.length} learning records</span></div>
    {message ? <p className="workbench-message" role="status">{message}</p> : null}
  </article>;
}

function option(item: RecordRow) { return <option key={item.id} value={item.id}>{item.id}</option>; }
function ids(value: FormDataEntryValue | null): string[] { return String(value ?? "").split(",").map((item) => item.trim()).filter(Boolean); }
async function readError(response: Response): Promise<string> { const payload = (await response.json().catch(() => null)) as { detail?: string } | null; return payload?.detail ?? `Request failed with status ${response.status}`; }
