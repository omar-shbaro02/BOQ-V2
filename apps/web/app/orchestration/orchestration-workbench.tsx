"use client";

import { FormEvent, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_VAI_API_URL ?? "http://localhost:8000";
type Connection = { actorId: string; organizationId: string; projectId: string; caseId: string };
type Source = { id: string; snapshot_id: string; assessment_number?: number; evaluation_number?: number; target?: string; assessment_status?: string; validity?: string };
type Specialist = { id: string; specialist_kind: string; status: string; attempt: number; confidence: string; input_references: Record<string, unknown>; output_references: Record<string, string>; findings: Record<string, unknown>[]; calculations: Record<string, unknown>[]; limitations: Record<string, unknown>[]; contradictions: Record<string, unknown>[]; requested_evidence: Record<string, unknown>[]; error_class: string | null };
type Run = { id: string; run_number: number; retry_of_run_id: string | null; status: string; readiness: string; recommended_disposition: string | null; alternative_dispositions: { disposition: string; selected: boolean; reason_code: string; reason: string }[]; blockers: Record<string, unknown>[]; limitations: Record<string, unknown>[]; contradiction_findings: Record<string, unknown>[]; case_brief: Record<string, unknown>; specialist_runs: Specialist[]; formula_version: string };

export function OrchestrationWorkbench() {
  const [connection, setConnection] = useState<Connection | null>(null);
  const [version, setVersion] = useState(1);
  const [runs, setRuns] = useState<Run[]>([]);
  const [progress, setProgress] = useState<Source[]>([]); const [schedule, setSchedule] = useState<Source[]>([]);
  const [cost, setCost] = useState<Source[]>([]); const [forecasts, setForecasts] = useState<Source[]>([]); const [impact, setImpact] = useState<Source[]>([]);
  const [busy, setBusy] = useState(false); const [message, setMessage] = useState<string | null>(null);
  function headers(active: Connection) { return { "Content-Type": "application/json", "X-VAI-Actor-ID": active.actorId, "X-VAI-Organization-ID": active.organizationId }; }
  function base(active: Connection) { return `${API_URL}/api/v1/projects/${active.projectId}/decision-cases/${active.caseId}`; }
  async function checked(response: Response) { const value = await response.json(); if (!response.ok) throw new Error(typeof value.detail === "string" ? value.detail : JSON.stringify(value.detail)); return value; }
  async function load(active: Connection) {
    const [current, history, p, s, c, f, i] = await Promise.all([
      fetch(base(active), { headers: headers(active) }).then(checked),
      fetch(`${base(active)}/orchestration-runs`, { headers: headers(active) }).then(checked),
      fetch(`${base(active)}/progress-evaluations`, { headers: headers(active) }).then(checked),
      fetch(`${base(active)}/schedule-assessments`, { headers: headers(active) }).then(checked),
      fetch(`${base(active)}/cost-assessments`, { headers: headers(active) }).then(checked),
      fetch(`${base(active)}/forecasts`, { headers: headers(active) }).then(checked),
      fetch(`${base(active)}/impact-assessments`, { headers: headers(active) }).then(checked),
    ]);
    setVersion(current.version); setRuns(history); setProgress(p); setSchedule(s); setCost(c); setForecasts(f); setImpact(i);
  }
  async function connect(event: FormEvent<HTMLFormElement>) { event.preventDefault(); const form = new FormData(event.currentTarget); const active = Object.fromEntries(["actorId", "organizationId", "projectId", "caseId"].map(key => [key, String(form.get(key))])) as Connection; setBusy(true); setMessage(null); try { await load(active); setConnection(active); } catch (error) { setMessage(String(error)); } finally { setBusy(false); } }
  async function run(event: FormEvent<HTMLFormElement>) { event.preventDefault(); if (!connection) return; const form = new FormData(event.currentTarget); const body: Record<string, unknown> = { expected_version: version, snapshot_id: String(form.get("snapshot_id")), forecast_projection_ids: form.getAll("forecast_projection_ids").map(String), requested_questions: String(form.get("requested_questions") ?? "").split("\n").map(value => value.trim()).filter(Boolean) }; for (const key of ["retry_of_run_id", "progress_evaluation_id", "schedule_assessment_id", "cost_assessment_id", "impact_assessment_id"]) if (form.get(key)) body[key] = String(form.get(key)); setBusy(true); setMessage(null); try { await checked(await fetch(`${base(connection)}/orchestration-runs`, { method: "POST", headers: { ...headers(connection), "Idempotency-Key": crypto.randomUUID() }, body: JSON.stringify(body) })); await load(connection); } catch (error) { setMessage(String(error)); } finally { setBusy(false); } }
  const options = (items: Source[], label: string) => items.map(item => <option key={item.id} value={item.id}>{label} #{item.assessment_number ?? item.evaluation_number ?? ""} · {item.assessment_status ?? item.target ?? item.validity ?? "recorded"} · snapshot {item.snapshot_id}</option>);
  return <div className="workbench-grid">
    <section className="workbench-card full-width"><h2>Case context</h2><form className="inline-form" onSubmit={connect}><label>Actor ID<input name="actorId" defaultValue="local-admin" required /></label><label>Organization UUID<input name="organizationId" required /></label><label>Project UUID<input name="projectId" required /></label><label>Case UUID<input name="caseId" required /></label><button disabled={busy}>Load case</button></form></section>
    {connection && <section className="workbench-card full-width"><h2>Run bounded specialists</h2><p>Case version {version}. Every selected result must belong to the same case snapshot. A retry creates a new immutable run.</p><form className="inline-form" onSubmit={run}>
      <label>Snapshot UUID<input name="snapshot_id" required /></label><label>Retry prior run<select name="retry_of_run_id"><option value="">New run</option>{runs.filter(item => item.status !== "SUCCEEDED").map(item => <option key={item.id} value={item.id}>Run {item.run_number} · {item.status}</option>)}</select></label>
      <label>Progress<select name="progress_evaluation_id"><option value="">Not selected</option>{options(progress, "Progress")}</select></label><label>Schedule<select name="schedule_assessment_id"><option value="">Not selected</option>{options(schedule, "Schedule")}</select></label><label>Cost<select name="cost_assessment_id"><option value="">Not selected</option>{options(cost, "Cost")}</select></label><label>Impact<select name="impact_assessment_id"><option value="">Not selected — stop at VERIFY</option>{options(impact, "Impact")}</select></label>
      <label>Forecasts<select name="forecast_projection_ids" multiple size={Math.min(6, Math.max(2, forecasts.length))}>{options(forecasts, "Forecast")}</select></label><label>Requested questions<textarea name="requested_questions" rows={3} placeholder="One question per line" /></label><button disabled={busy}>Run orchestration</button>
    </form></section>}
    <section className="workbench-card full-width"><h2>Run history and case briefs</h2>{connection && runs.length === 0 && <p>No orchestration runs yet.</p>}{runs.map(item => <article className="forecast-card" key={item.id}><h3>Run {item.run_number} · {item.status}</h3><p>Readiness: <strong>{item.readiness}</strong> · Recommended disposition: <strong>{item.recommended_disposition ?? "WITHHELD"}</strong>{item.retry_of_run_id ? ` · retry of ${item.retry_of_run_id}` : ""}</p><h4>Specialist boundaries</h4><div className="specialist-run-grid">{item.specialist_runs.map(specialist => <SpecialistCard key={specialist.id} specialist={specialist}/>)}</div><h4>Disposition alternatives</h4><ul>{item.alternative_dispositions.map(value => <li key={value.disposition}>{value.selected ? "Selected" : "Not selected"}: {value.disposition} — {value.reason}</li>)}</ul>{item.blockers.map((value, index) => <p role="alert" key={`b-${index}`}>{String(value.code)}: {String(value.description)}</p>)}{item.contradiction_findings.map((value, index) => <p role="alert" key={`c-${index}`}>{String(value.type)} contradiction: {String(value.description)}</p>)}<details><summary>Structured case brief</summary><pre style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{JSON.stringify(item.case_brief, null, 2)}</pre></details><small>{item.formula_version}</small></article>)}</section>
    {message && <p className="workbench-message full-width" role="alert">{message}</p>}
  </div>;
}

function SpecialistCard({specialist}:{specialist:Specialist}) {
  const mode=String(specialist.input_references.execution_mode??"LEGACY");
  const model=specialist.input_references.agent_model;
  const prompt=specialist.input_references.prompt_version;
  const response=specialist.output_references.openai_response_id;
  return <article className="specialist-run-card">
    <div><strong>{specialist.specialist_kind.replaceAll("_"," ")}</strong><span className={mode==="OPENAI_AGENT"?"agent-mode ai":"agent-mode"}>{mode.replaceAll("_"," ")}</span></div>
    <p>{specialist.status} · attempt {specialist.attempt} · confidence {specialist.confidence}</p>
    {model?<small>Model: {String(model)} · Prompt: {String(prompt)} · Response: {response??"not recorded"}</small>:null}
    {specialist.error_class?<p role="alert">Agent failure: {specialist.error_class}</p>:null}
    <details><summary>Validated specialist output</summary><pre>{JSON.stringify({findings:specialist.findings,calculations:specialist.calculations,limitations:specialist.limitations,contradictions:specialist.contradictions,requested_evidence:specialist.requested_evidence},null,2)}</pre></details>
  </article>;
}
