"use client";

import { FormEvent, useState } from "react";
import { ProjectContextFields } from "../project-context-fields";
import { ProgressTemplate } from "./progress-template";

const API_URL = process.env.NEXT_PUBLIC_VAI_API_URL ?? "http://localhost:8000";

type Connection = { actorId: string; organizationId: string; projectId: string };
type Measurement = {
  id: string;
  evidence_item_id: string;
  controlled_object_id: string;
  measurement_kind: string;
  measurement_basis: string;
  numerator: string;
  denominator: string;
  completion_ratio: string;
  semantic_state: string;
  truth_type: string;
  as_of: string;
};
type Policy = {
  policy_version: string;
  deviation_threshold: string;
  persistence_min_observations: number;
  persistence_min_duration_days: number;
  rationale: string;
};
type ProgressRow = {
  task_id: number; subdivision: string; task_name: string; planned_percent: number;
  reported_percent: number | null; status: string; schedule_variance_days: number | null;
  evidence_state: string; recommendation: string;
};
type WorkbookAnalysis = {
  semantic_notice: string;
  as_of: string; counts: Record<string, number>; potential_deadline_exposure_days: number;
  deadline_basis: string; rows: ProgressRow[];
};
type AuthorizedSchedule = { id: string; version_number: number; payload: { activities: { code: string; name: string; controlled_object_code?: string | null }[] } };
type ControlledObject = { id: string; code: string; active: boolean };
type WorkbookImport = { id: string; data_date: string; schedule_context_id: string; rows: { task_id: number; task_name: string; reported_percent: string | null; planned_percent: string | null; truth_type: string }[]; limitations: { code: string; description: string }[] };

export function ProgressWorkbench() {
  const [connection, setConnection] = useState<Connection | null>(null);
  const [measurements, setMeasurements] = useState<Measurement[]>([]);
  const [policies, setPolicies] = useState<Policy[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [analysis, setAnalysis] = useState<WorkbookAnalysis | null>(null);
  const [sourceFile, setSourceFile] = useState<File | null>(null);
  const [schedule, setSchedule] = useState<AuthorizedSchedule | null>(null);
  const [objects, setObjects] = useState<ControlledObject[]>([]);
  const [imports, setImports] = useState<WorkbookImport[]>([]);
  const [mapping, setMapping] = useState<Record<number, string>>({});

  async function analyzeWorkbook(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setMessage(null);
    setSourceFile(null);
    setMapping({});
    try {
      const form = new FormData(event.currentTarget);
      const response = await fetch(`${API_URL}/api/v1/ms-project/analyze-progress`, {
        method: "POST", body: form,
      });
      if (!response.ok) throw new Error(await readError(response));
      setAnalysis(await response.json() as WorkbookAnalysis);
      setSourceFile(form.get("schedule") as File);
    } catch (caught) {
      setAnalysis(null);
      setMessage(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  function headers(active = connection): HeadersInit {
    if (!active) return {};
    return {
      "Content-Type": "application/json",
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
    setMapping({});
    await refresh(next);
  }

  async function refresh(active = connection) {
    if (!active) return;
    setBusy(true);
    try {
      const [measurementResponse, policyResponse, scheduleResponse, objectResponse, importResponse] = await Promise.all([
        fetch(`${API_URL}/api/v1/projects/${active.projectId}/progress/measurements`, {
          headers: headers(active),
        }),
        fetch(`${API_URL}/api/v1/projects/${active.projectId}/progress/policies`, {
          headers: headers(active),
        }),
        fetch(`${API_URL}/api/v1/projects/${active.projectId}/authorized-context/current/SCHEDULE`, { headers: headers(active) }),
        fetch(`${API_URL}/api/v1/projects/${active.projectId}/controlled-objects`, { headers: headers(active) }),
        fetch(`${API_URL}/api/v1/projects/${active.projectId}/progress/workbook-imports`, { headers: headers(active) }),
      ]);
      if (!measurementResponse.ok) throw new Error(await readError(measurementResponse));
      if (!policyResponse.ok) throw new Error(await readError(policyResponse));
      if (!objectResponse.ok) throw new Error(await readError(objectResponse));
      if (!importResponse.ok) throw new Error(await readError(importResponse));
      if (!scheduleResponse.ok && scheduleResponse.status !== 404) throw new Error(await readError(scheduleResponse));
      setMeasurements((await measurementResponse.json()) as Measurement[]);
      setPolicies((await policyResponse.json()) as Policy[]);
      setSchedule(scheduleResponse.ok ? await scheduleResponse.json() as AuthorizedSchedule : null);
      setObjects(await objectResponse.json() as ControlledObject[]);
      setImports(await importResponse.json() as WorkbookImport[]);
      setMessage(null);
    } catch (caught) {
      setMessage(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  async function saveWorkbook(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!connection || !schedule || !sourceFile || !analysis) return;
    const form = new FormData(event.currentTarget);
    setBusy(true);
    try {
      const mappings = analysis.rows.map((row) => {
        const activity = schedule.payload.activities.find((item) => item.code === mapping[row.task_id]);
        const object = objects.find((item) => item.active && item.code === (activity?.controlled_object_code || activity?.code));
        if (!activity || !object) throw new Error(`Choose an authorized activity with a linked project object for task ${row.task_id}.`);
        return { task_id: row.task_id, activity_code: activity.code, controlled_object_id: object.id };
      });
      const upload = new FormData();
      upload.set("upload", sourceFile);
      upload.set("source_type", "PROGRESS_WORKBOOK");
      upload.set("source_id", sourceFile.name);
      const auth = { "X-VAI-Actor-ID": connection.actorId, "X-VAI-Organization-ID": connection.organizationId };
      const artifact = await fetch(`${API_URL}/api/v1/projects/${connection.projectId}/evidence/artifacts`, { method: "POST", headers: auth, body: upload });
      if (!artifact.ok) throw new Error(await readError(artifact));
      const saved = await artifact.json() as { id: string };
      const response = await fetch(`${API_URL}/api/v1/projects/${connection.projectId}/progress/workbook-imports`, {
        method: "POST", headers: { ...headers(), "Idempotency-Key": crypto.randomUUID() },
        body: JSON.stringify({ artifact_id: saved.id, schedule_context_id: schedule.id,
          data_date: new Date(String(form.get("dataDate"))).toISOString(),
          reported_confidence: form.get("confidence"), mappings }),
      });
      if (!response.ok) throw new Error(await readError(response));
      await refresh();
      setMessage("Workbook and reported measurements saved. Verification and acceptance remain separate.");
    } catch (caught) { setMessage(errorMessage(caught)); }
    finally { setBusy(false); }
  }

  async function normalize(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!connection) return;
    const form = new FormData(event.currentTarget);
    const contextId = String(form.get("authorizedContextId") ?? "").trim();
    setBusy(true);
    try {
      const response = await fetch(
        `${API_URL}/api/v1/projects/${connection.projectId}/progress/measurements`,
        {
          method: "POST",
          headers: headers(),
          body: JSON.stringify({
            evidence_item_id: form.get("evidenceId"),
            authorized_context_id: contextId || null,
            measurement_kind: form.get("kind"),
            numerator: form.get("numerator"),
            denominator: form.get("denominator"),
            unit: form.get("unit"),
          }),
        },
      );
      if (!response.ok) throw new Error(await readError(response));
      setMessage("Immutable progress measurement recorded from its source evidence.");
      await refresh();
    } catch (caught) {
      setMessage(errorMessage(caught));
      setBusy(false);
    }
  }

  return (
    <div className="workbench-grid">
      <ProgressTemplate />
      <section className="workbench-card full-width">
        <span className="step-number">01</span>
        <h2>Preview the latest progress workbook</h2>
        <p className="card-copy">This unpersisted preview uses calendar-day approximations. Open the schedule workbook generated from the BOQ, update the yellow cells on its Progress Report sheet, save it, then upload it here. Save governed progress below to retain evidence and exact authorized schedule lineage.</p>
        <form className="inline-form" onSubmit={analyzeWorkbook}>
          <label>Updated schedule workbook<input name="schedule" type="file" accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" required /></label>
          <label>Reporting cut-off<input name="as_of" type="date" defaultValue={new Date().toISOString().slice(0, 10)} required /></label>
          <button disabled={busy}>{busy ? "Analyzing…" : "Preview workbook"}</button>
        </form>
        {analysis ? <div className="progress-analysis">
          <p className="card-copy">{analysis.semantic_notice}</p>
          <div className="metric-grid">
            {(["LATE", "ON TIME", "EARLY", "NOT REPORTED"] as const).map((status) => <div className="metric-card" key={status}><span>{status}</span><strong>{analysis.counts[status] ?? 0}</strong></div>)}
            <div className="metric-card"><span>Unpersisted exposure scenario</span><strong>{analysis.potential_deadline_exposure_days} days</strong></div>
          </div>
          <p className="panel-note">{analysis.deadline_basis}</p>
          <div className="ledger-table progress-ledger" role="table" aria-label="Unpersisted workbook exception preview">
            <div className="sr-only" role="row"><span role="columnheader">Task and subdivision</span><span role="columnheader">Planned and reported preview</span><span role="columnheader">Evidence state</span><span role="columnheader">Unpersisted exposure and recommendation</span></div>
            {analysis.rows.filter((row) => row.status === "LATE" || row.status === "NOT REPORTED").map((row) => <article className="ledger-row" role="row" key={row.task_id}>
              <div role="cell"><strong>{row.task_id} · {row.task_name}</strong><small>{row.subdivision}</small></div>
              <div role="cell"><span>{row.planned_percent}% time-based preview</span><small>{row.reported_percent === null ? "No report" : `${row.reported_percent}% reported`}</small></div>
              <div role="cell"><span className={`truth ${row.status === "LATE" ? "restricted" : "reported"}`}>{row.status}</span><small>{row.evidence_state}</small></div>
              <div role="cell"><span>{row.schedule_variance_days === null ? "—" : `${Math.abs(row.schedule_variance_days)} preview days`}</span><small>{row.recommendation}</small></div>
            </article>)}
          </div>
          <p><a className="button-link" href="/bootstrap/schedule-assistant">Prepare a reviewed schedule-change proposal</a></p>
        </div> : null}
      </section>
      <section className="workbench-card full-width">
        <h2>Save governed workbook progress</h2>
        <p className="card-copy">Connect a project using Load progress below, preview the workbook, then match each task to its authorized schedule activity. Workbook dates and scope must match that exact version. All saved completion stays reported until separately verified.</p>
        {connection && schedule && analysis ? <form className="stack-form" onSubmit={saveWorkbook}>
          <p>Authorized schedule version {schedule.version_number}. The reporting cut-off is entered in your computer&apos;s local time and checked against the project&apos;s reporting date.</p>
          {analysis.rows.map((row) => <label key={row.task_id}>Task {row.task_id}: {row.task_name}<select required value={mapping[row.task_id] ?? ""} onChange={(event) => setMapping({ ...mapping, [row.task_id]: event.target.value })}>
            <option value="">Choose authorized activity</option>
            {schedule.payload.activities.map((activity) => <option key={activity.code} value={activity.code}>{activity.code} · {activity.name}</option>)}
          </select></label>)}
          <label>Reporting cut-off<input type="datetime-local" name="dataDate" required /></label>
          <label>Confidence in the reported source (0–1)<input type="number" min="0" max="1" step="0.01" name="confidence" required /></label>
          <button disabled={busy || !sourceFile}>Save workbook and reported measurements</button>
        </form> : <p className="empty-state">Load project progress and preview a workbook to map its tasks. An authorized schedule is required.</p>}
        <h3>Saved workbook history</h3>
        {imports.length ? imports.map((item) => <article className="mini-ledger" key={item.id}>
          <strong>{new Date(item.data_date).toLocaleString()} · {item.rows.length} task rows</strong>
          {item.rows.map((row) => <p key={row.task_id}>{row.task_name}: {row.reported_percent === null ? "Not reported" : `${row.reported_percent}% reported`} · authorized planned {row.planned_percent === null ? "Unknown" : `${row.planned_percent}%`} · {row.truth_type}</p>)}
          {item.limitations.map((limitation) => <small key={limitation.code}>{limitation.description} </small>)}
        </article>) : <p className="empty-state">No governed workbook imports loaded.</p>}
      </section>
      <section className="workbench-card full-width">
        <span className="step-number">02</span>
        <h2>Governed evidence records</h2>
        <p className="card-copy">Advanced audit view for evidence-backed measurements and authorized plan lineage.</p>
        <form className="inline-form context-form" onSubmit={connect}>
          <ProjectContextFields />
          <button>Load progress</button>
          <button type="button" className="secondary" disabled={!connection || busy} onClick={() => refresh()}>Refresh</button>
        </form>
      </section>
      <section className="workbench-card">
        <span className="step-number">03</span>
        <h2>Normalize evidence</h2>
        <p className="card-copy">The numerator must match an immutable evidence value. Planned values additionally require an exact point in the linked authorized schedule.</p>
        <form className="stack-form" onSubmit={normalize}>
          <label>Evidence record<input name="evidenceId" required /></label>
          <label>Progress gate<select name="kind"><option>PLANNED_AUTHORIZED</option><option>REPORTED</option><option>EXECUTED</option><option>VERIFIED</option><option>ACCEPTED_RELEASED</option></select></label>
          <label>Authorized schedule reference<input name="authorizedContextId" placeholder="Required only for planned progress" /></label>
          <div className="form-pair"><label>Numerator<input name="numerator" type="number" min="0" step="any" required /></label><label>Denominator<input name="denominator" type="number" min="0.000001" step="any" required /></label></div>
          <label>Unit<input name="unit" defaultValue="%" required /></label>
          <button disabled={!connection || busy}>Record normalized measurement</button>
        </form>
      </section>
      <section className="workbench-card">
        <span className="step-number">04</span>
        <h2>Visible threshold policies</h2>
        <div className="mini-ledger">{policies.map((policy) => <div key={policy.policy_version}><strong>{policy.policy_version}</strong><span>Deviation {Number(policy.deviation_threshold) * 100}% · {policy.persistence_min_observations} observations across {policy.persistence_min_duration_days} days</span><small>{policy.rationale}</small></div>)}</div>
      </section>
      <section className="workbench-card full-width">
        <div className="card-heading"><div><span className="step-number">05</span><h2>Separated progress gates</h2></div><span className="ledger-count">{measurements.length} measurements</span></div>
        {measurements.length ? <div className="ledger-table progress-ledger" role="table" aria-label="Separated progress measurements"><div className="sr-only" role="row"><span role="columnheader">Measurement kind and reference</span><span role="columnheader">Quantity</span><span role="columnheader">Truth and semantic state</span><span role="columnheader">Measurement basis and date</span><span role="columnheader">Completion</span></div>{measurements.map((item) => <article className="ledger-row" role="row" key={item.id}><div role="cell"><strong>{item.measurement_kind.replaceAll("_", " ")}</strong><small>{item.id}</small></div><code role="cell">{item.numerator}/{item.denominator}</code><div role="cell"><span className={`truth ${item.semantic_state.toLowerCase()}`}>{item.semantic_state}</span><small>{item.truth_type.replaceAll("_", " ")}</small></div><div role="cell"><span>{item.measurement_basis.replaceAll("_", " ")}</span><small>{new Date(item.as_of).toLocaleString()}</small></div><strong role="cell">{(Number(item.completion_ratio) * 100).toFixed(1)}%</strong></article>)}</div> : <p className="empty-state">No progress measurements recorded.</p>}
      </section>
      {message ? <p className="workbench-message full-width" role="status">{message}</p> : null}
    </div>
  );
}

function errorMessage(caught: unknown): string {
  return caught instanceof Error ? caught.message : "Progress request failed";
}

async function readError(response: Response): Promise<string> {
  const payload = (await response.json().catch(() => null)) as { detail?: string | { msg?: string }[] } | null;
  if (typeof payload?.detail === "string") return payload.detail;
  if (Array.isArray(payload?.detail)) return payload.detail.map((entry) => entry.msg).join("; ");
  return `Request failed with status ${response.status}`;
}
