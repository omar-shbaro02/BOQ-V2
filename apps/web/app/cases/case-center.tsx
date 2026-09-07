"use client";

import { FormEvent, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_VAI_API_URL ?? "http://localhost:8000";

type Connection = { actorId: string; organizationId: string; projectId: string };
type Case = {
  id: string;
  case_number: string;
  title: string;
  case_type: string;
  lifecycle: string;
  readiness: string | null;
  governance_state: string;
  owner_actor_id: string;
  version: number;
  last_snapshot_id: string | null;
  last_progress_evaluation_id: string | null;
  blocker_description: string | null;
  outcome_reference: string | null;
  close_reason: string | null;
  reopen_trigger: string | null;
};
type Evidence = { id: string; field_name: string; value: unknown; semantic_state: string; truth_type: string; is_stale: boolean };
type Limitation = { id: string; code: string; description: string; material: boolean; owner_actor_id: string; due_at: string; status: string };
type Snapshot = { id: string; snapshot_number: number; snapshot_hash: string; baseline_validity: string; data_date: string; active_response_ids: string[] };
type Assessment = { id: string; conclusion_type: string; readiness: string; maximum_supported_conclusion: string; missing_evidence: object[]; weak_evidence_ids: string[] };
type Ledger = { id: string; case_version: number; event_type: string; actor_id: string; reason: string; occurred_at: string };
type ActiveResponse = { id: string; response_type: string; authorization_reference: string; status: string };
type ProgressEvaluation = { id: string; evaluation_number: number; reconciliation_status: string; reconciled_measurements: Record<string, { completion_ratio: string; measurement_basis: string; truth_type: string }>; planned_ratio: string; actual_ratio: string; variance_ratio: string; direction: string; duration_days: number; threshold_crossed: boolean; persistence: string; trend_direction: string; supporting_observation_count: number; planned_productivity: string | null; actual_productivity: string | null; productivity_variance_ratio: string | null; truth_type: string; confidence: string; limitations: object[]; policy_version: string; formula_version: string };
type Assembly = { case: Case; evidence: Evidence[]; limitations: Limitation[]; snapshots: Snapshot[]; assessments: Assessment[]; ledger: Ledger[]; active_responses: ActiveResponse[]; progress_evaluations: ProgressEvaluation[] };

export function CaseCenter() {
  const [connection, setConnection] = useState<Connection | null>(null);
  const [cases, setCases] = useState<Case[]>([]);
  const [assembly, setAssembly] = useState<Assembly | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function headers(active = connection, extra: Record<string, string> = {}): HeadersInit {
    if (!active) return extra;
    return { "Content-Type": "application/json", "X-VAI-Actor-ID": active.actorId, "X-VAI-Organization-ID": active.organizationId, ...extra };
  }

  async function connect(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const next = { actorId: String(form.get("actorId")), organizationId: String(form.get("organizationId")), projectId: String(form.get("projectId")) };
    setConnection(next);
    await refreshCases(next);
  }

  async function refreshCases(active = connection) {
    if (!active) return;
    setBusy(true);
    try {
      const response = await fetch(`${API_URL}/api/v1/projects/${active.projectId}/decision-cases`, { headers: headers(active) });
      if (!response.ok) throw new Error(await readError(response));
      setCases((await response.json()) as Case[]);
      setMessage(null);
    } catch (caught) {
      setMessage(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  async function loadAssembly(caseId: string) {
    if (!connection) return;
    setBusy(true);
    try {
      const [response, progressResponse] = await Promise.all([
        fetch(`${API_URL}/api/v1/projects/${connection.projectId}/decision-cases/${caseId}/evidence-assembly`, { headers: headers() }),
        fetch(`${API_URL}/api/v1/projects/${connection.projectId}/decision-cases/${caseId}/progress-evaluations`, { headers: headers() }),
      ]);
      if (!response.ok) throw new Error(await readError(response));
      if (!progressResponse.ok) throw new Error(await readError(progressResponse));
      const caseAssembly = (await response.json()) as Omit<Assembly, "progress_evaluations">;
      setAssembly({ ...caseAssembly, progress_evaluations: (await progressResponse.json()) as ProgressEvaluation[] });
      setMessage(null);
    } catch (caught) {
      setMessage(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  async function command(path: string, body: object, success: string, extraHeaders: Record<string, string> = {}) {
    if (!connection || !assembly) return;
    setBusy(true);
    try {
      const response = await fetch(`${API_URL}/api/v1/projects/${connection.projectId}/decision-cases/${assembly.case.id}${path}`, { method: "POST", headers: headers(connection, extraHeaders), body: JSON.stringify(body) });
      if (!response.ok) throw new Error(await readError(response));
      setMessage(success);
      await loadAssembly(assembly.case.id);
      await refreshCases();
    } catch (caught) {
      setMessage(errorMessage(caught));
      setBusy(false);
    }
  }

  async function attachEvidence(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!assembly) return;
    const form = new FormData(event.currentTarget);
    await command("/evidence", { expected_version: assembly.case.version, evidence_item_ids: String(form.get("evidenceIds")).split(",").map((value) => value.trim()).filter(Boolean), attachment_reason: form.get("reason") }, "Evidence attached; create a new snapshot to include it.");
  }

  async function createSnapshot() {
    if (!assembly) return;
    await command("/snapshots", { expected_version: assembly.case.version, data_date: nowIso() }, "Immutable case snapshot created.", { "Idempotency-Key": crypto.randomUUID() });
  }

  async function assess(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!assembly?.case.last_snapshot_id || !connection) return;
    const form = new FormData(event.currentTarget);
    await command("/sufficiency-assessments", { expected_version: assembly.case.version, snapshot_id: assembly.case.last_snapshot_id, conclusion_type: form.get("conclusionType"), gap_owner_actor_id: form.get("gapOwner") || connection.actorId, gap_due_at: twoDaysFromNow() }, "Conclusion-specific sufficiency assessment recorded.");
  }

  async function addResponse(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!assembly || !connection) return;
    const form = new FormData(event.currentTarget);
    await command("/active-responses", { expected_version: assembly.case.version, response_type: form.get("responseType"), authorization_reference: form.get("authorizationReference"), owner_actor_id: connection.actorId, status: "ACTIVE", effective_from: nowIso(), details: {} }, "Authorized response reference linked; it will be detected in the next snapshot.");
  }

  async function transition(target: string) {
    if (!assembly) return;
    await command("/transition", { expected_version: assembly.case.version, target_lifecycle: target, reason: `Reviewer advanced case to ${target}` }, `Case advanced to ${target}.`);
  }

  async function resolveLimitation(limitation: Limitation) {
    if (!assembly) return;
    await command(`/limitations/${limitation.id}/resolve`, { expected_version: assembly.case.version, resolution: "Reviewer confirmed the limitation was addressed with updated evidence" }, "Limitation resolution recorded; readiness still requires a new snapshot and assessment.");
  }

  async function blockOrResume() {
    if (!assembly) return;
    if (assembly.case.lifecycle === "BLOCKED") {
      await command("/resume", { expected_version: assembly.case.version, reason: "Recorded blocker has been addressed" }, "Case resumed to its prior lifecycle.");
    } else {
      await command("/block", { expected_version: assembly.case.version, blocker_code: "HUMAN_REVIEW_BLOCK", blocker_description: "Reviewer paused the case pending governed clarification" }, "Case blocked with explicit reason.");
    }
  }

  async function challengeBaseline(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!assembly?.case.last_snapshot_id) return;
    const form = new FormData(event.currentTarget);
    await command("/baseline-assessments", {
      expected_version: assembly.case.version,
      snapshot_id: assembly.case.last_snapshot_id,
      validity: "DISPUTED",
      rationale: form.get("rationale"),
    }, "Baseline challenge recorded; reassess sufficiency against this snapshot.");
  }

  async function closeCase(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!assembly) return;
    const form = new FormData(event.currentTarget);
    const outcomeReference = String(form.get("outcomeReference") ?? "").trim();
    const administrativeRationale = String(form.get("administrativeRationale") ?? "").trim();
    await command("/close", {
      expected_version: assembly.case.version,
      outcome_reference: outcomeReference || null,
      administrative_rationale: administrativeRationale || null,
    }, "Case closed with an explicit governed basis.");
  }

  async function reopenCase(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!assembly) return;
    const form = new FormData(event.currentTarget);
    await command("/reopen", {
      expected_version: assembly.case.version,
      trigger: "NEW_MATERIAL_EVIDENCE",
      reason: form.get("reason"),
      new_evidence_item_id: form.get("evidenceId"),
    }, "Case reopened from new material evidence.");
  }

  async function evaluateProgress(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!assembly?.case.last_snapshot_id) return;
    const form = new FormData(event.currentTarget);
    const priorPlanned = String(form.get("priorPlannedMeasurementId") ?? "").trim();
    const priorActual = String(form.get("priorActualMeasurementId") ?? "").trim();
    await command("/progress-evaluations", {
      expected_version: assembly.case.version,
      snapshot_id: assembly.case.last_snapshot_id,
      planned_measurement_id: form.get("plannedMeasurementId"),
      actual_measurement_id: form.get("actualMeasurementId"),
      prior_planned_measurement_id: priorPlanned || null,
      prior_actual_measurement_id: priorActual || null,
      policy_version: form.get("policyVersion"),
    }, "Progress truth, deviation, productivity, and persistence evaluated.", { "Idempotency-Key": crypto.randomUUID() });
  }

  const nextLifecycle: Record<string, string> = { OPEN: "EVIDENCE_ASSEMBLY", REOPENED: "EVIDENCE_ASSEMBLY", EVIDENCE_ASSEMBLY: "ANALYSIS", ANALYSIS: "REVIEW", REVIEW: "DECISION_READY" };

  return <div className="case-layout">
    <section className="workbench-card case-connect">
      <span className="step-number">01</span><h2>Project context</h2>
      <form className="stack-form" onSubmit={connect}><label>Actor ID<input name="actorId" defaultValue="local-admin" required /></label><label>Organization UUID<input name="organizationId" required /></label><label>Project UUID<input name="projectId" required /></label><button>Load cases</button></form>
      <div className="case-list">{cases.map((item) => <button className={assembly?.case.id === item.id ? "case-select active" : "case-select"} key={item.id} onClick={() => loadAssembly(item.id)}><strong>{item.case_number}</strong><span>{item.title}</span><small>{item.lifecycle} · {item.readiness ?? "NOT ASSESSED"}</small></button>)}{connection && !cases.length ? <p className="empty-state">No reviewed signal correlation has opened a case yet.</p> : null}</div>
    </section>
    <section className="case-detail">
      {!assembly ? <div className="workbench-card empty-state">Select a Decision Case to assemble its evidence and inspect its governed ledger.</div> : <>
        <article className="workbench-card case-summary"><div><span className="step-number">02</span><h2>{assembly.case.title}</h2><p>{assembly.case.case_number} · {assembly.case.case_type}</p></div><div className="case-state"><span className="truth verified">{assembly.case.lifecycle}</span><strong>{assembly.case.readiness ?? "READINESS NOT ASSESSED"}</strong><small>{assembly.case.governance_state} · v{assembly.case.version}</small></div></article>
        <div className="case-actions"><button disabled={busy || !nextLifecycle[assembly.case.lifecycle]} onClick={() => transition(nextLifecycle[assembly.case.lifecycle])}>Advance lifecycle</button><button className="secondary" disabled={busy || assembly.case.lifecycle === "CLOSED"} onClick={blockOrResume}>{assembly.case.lifecycle === "BLOCKED" ? "Resume" : "Block"}</button><button className="secondary" disabled={busy || assembly.case.lifecycle === "CLOSED"} onClick={createSnapshot}>Freeze snapshot</button></div>
        {assembly.case.blocker_description ? <p className="workbench-message">Blocked: {assembly.case.blocker_description}</p> : null}
        <div className="case-panels">
          <article className="workbench-card"><h3>Evidence assembly</h3><form className="stack-form compact" onSubmit={attachEvidence}><label>Evidence UUIDs, comma separated<input name="evidenceIds" required /></label><label>Attachment reason<input name="reason" defaultValue="Decision-critical case evidence" required /></label><button disabled={busy || assembly.case.lifecycle === "CLOSED"}>Attach evidence</button></form><div className="mini-ledger">{assembly.evidence.map((item) => <div key={item.id}><strong>{item.field_name}: {JSON.stringify(item.value)}</strong><small>{item.semantic_state} · {item.truth_type}{item.is_stale ? " · STALE" : ""}</small></div>)}</div></article>
          <article className="workbench-card"><h3>Progress deviation</h3><p className="panel-note">Register evidence-backed measurements in Progress Reconciliation, attach their evidence here, then freeze a snapshot before evaluating.</p><form className="stack-form compact" onSubmit={evaluateProgress}><label>Planned measurement UUID<input name="plannedMeasurementId" required /></label><label>Actual measurement UUID<input name="actualMeasurementId" required /></label><div className="form-pair"><label>Prior planned UUID<input name="priorPlannedMeasurementId" /></label><label>Prior actual UUID<input name="priorActualMeasurementId" /></label></div><label>Threshold policy<input name="policyVersion" defaultValue="PROGRESS-DEFAULT-1.0.0" required /></label><button disabled={busy || !assembly.case.last_snapshot_id || assembly.case.lifecycle === "CLOSED"}>Evaluate progress</button></form><div className="mini-ledger">{assembly.progress_evaluations.map((item) => <div className="progress-result" key={item.id}><strong>{item.direction} · {(Number(item.variance_ratio) * 100).toFixed(1)}%</strong><span>{item.persistence} after {item.supporting_observation_count} observation(s) / {item.duration_days} days · {item.trend_direction}</span><small>{item.reconciliation_status} · {item.truth_type} · confidence {item.confidence} · {item.formula_version}</small><div className="gate-strip">{Object.entries(item.reconciled_measurements).map(([gate, value]) => <span key={gate}>{gate.replaceAll("_", " ")} <b>{(Number(value.completion_ratio) * 100).toFixed(1)}%</b><small>{value.measurement_basis.replaceAll("_", " ")} · {value.truth_type.replaceAll("_", " ")}</small></span>)}</div></div>)}</div></article>
          <article className="workbench-card"><h3>Sufficiency and readiness</h3><form className="stack-form compact" onSubmit={assess}><label>Candidate conclusion<select name="conclusionType"><option>VERIFY_EVIDENCE</option><option>MONITOR_CONDITION</option><option>PROGRESS_INTERVENTION</option><option>SCHEDULE_INTERVENTION</option><option>COST_INTERVENTION</option></select></label><label>Gap owner<input name="gapOwner" defaultValue={connection?.actorId} /></label><button disabled={busy || !assembly.case.last_snapshot_id || assembly.case.lifecycle === "CLOSED"}>Assess latest snapshot</button></form>{assembly.assessments.map((item) => <div className="assessment-box" key={item.id}><strong>{item.readiness}</strong><span>{item.conclusion_type} → {item.maximum_supported_conclusion}</span><small>{item.missing_evidence.length} missing · {item.weak_evidence_ids.length} weak</small></div>)}</article>
          <article className="workbench-card"><h3>Limitations</h3><div className="mini-ledger">{assembly.limitations.map((item) => <div key={item.id}><strong>{item.code}{item.material ? " · MATERIAL" : ""}</strong><span>{item.description}</span><small>{item.status} · owner {item.owner_actor_id} · due {new Date(item.due_at).toLocaleString()}</small>{item.status === "OPEN" ? <button className="text-button" onClick={() => resolveLimitation(item)}>Resolve with record</button> : null}</div>)}{!assembly.limitations.length ? <p className="empty-state">No recorded limitations.</p> : null}</div></article>
          <article className="workbench-card"><h3>Authorized active response</h3><form className="stack-form compact" onSubmit={addResponse}><label>Response type<input name="responseType" defaultValue="RECOVERY_PLAN" required /></label><label>Authorization reference<input name="authorizationReference" required /></label><button disabled={busy || assembly.case.lifecycle === "CLOSED"}>Link response reference</button></form><div className="mini-ledger">{assembly.active_responses.map((item) => <div key={item.id}><strong>{item.response_type} · {item.status}</strong><small>{item.authorization_reference}</small></div>)}</div></article>
          <article className="workbench-card"><h3>Baseline governance</h3><p className="panel-note">A challenge is append-only and affects later sufficiency assessments; it never rewrites the frozen snapshot.</p><form className="stack-form compact" onSubmit={challengeBaseline}><label>Challenge rationale<input name="rationale" defaultValue="Authorized schedule baseline is disputed pending controller verification" required /></label><button disabled={busy || !assembly.case.last_snapshot_id || assembly.case.lifecycle === "CLOSED"}>Record disputed baseline</button></form></article>
          <article className="workbench-card"><h3>Close or reopen</h3>{assembly.case.lifecycle === "CLOSED" ? <><p className="panel-note">Closed: {assembly.case.close_reason}{assembly.case.outcome_reference ? ` · ${assembly.case.outcome_reference}` : ""}</p><form className="stack-form compact" onSubmit={reopenCase}><label>New material evidence UUID<input name="evidenceId" required /></label><label>Reopen reason<input name="reason" defaultValue="New material evidence changes the case basis" required /></label><button disabled={busy}>Reopen case</button></form></> : <form className="stack-form compact" onSubmit={closeCase}><label>Outcome reference<input name="outcomeReference" placeholder="Required for authority-led closure" /></label><label>Administrative rationale<input name="administrativeRationale" placeholder="Admin-only alternative to an outcome reference" /></label><button disabled={busy}>Close with recorded basis</button></form>}</article>
          <article className="workbench-card full-span"><h3>Immutable snapshots</h3><div className="mini-ledger horizontal">{assembly.snapshots.map((item) => <div key={item.id}><strong>Snapshot {item.snapshot_number} · {item.baseline_validity}</strong><span>{new Date(item.data_date).toLocaleString()} · {item.active_response_ids.length} active responses</span><small title={item.snapshot_hash}>{item.snapshot_hash}</small></div>)}</div></article>
          <article className="workbench-card full-span"><h3>Chronological case ledger</h3><div className="mini-ledger">{assembly.ledger.map((item) => <div className="ledger-entry" key={item.id}><span>v{item.case_version}</span><strong>{item.event_type.replaceAll("_", " ")}</strong><span>{item.reason}</span><small>{item.actor_id} · {new Date(item.occurred_at).toLocaleString()}</small></div>)}</div></article>
        </div>
      </>}
    </section>
    {message ? <p className="workbench-message full-width" role="status">{message}</p> : null}
  </div>;
}

function nowIso(): string { return new Date().toISOString(); }
function twoDaysFromNow(): string { return new Date(Date.now() + 2 * 86_400_000).toISOString(); }
function errorMessage(caught: unknown): string { return caught instanceof Error ? caught.message : "Case command failed"; }
async function readError(response: Response): Promise<string> { const payload = (await response.json().catch(() => null)) as { detail?: string | { msg?: string }[] } | null; if (typeof payload?.detail === "string") return payload.detail; if (Array.isArray(payload?.detail)) return payload.detail.map((entry) => entry.msg).join("; "); return `Request failed with status ${response.status}`; }
