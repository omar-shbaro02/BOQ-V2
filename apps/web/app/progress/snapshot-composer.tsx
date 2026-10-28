"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import Link from "next/link";
import { ProjectContextFields } from "../project-context-fields";

const API = process.env.NEXT_PUBLIC_VAI_API_URL ?? "http://localhost:8000";
type Connection = { projectId: string; actorId: string; organizationId: string };
type Source = { id: string; context_type: string; version_number: number; semantic_state: string; payload: { entries?: { controlled_object_code: string; weight: string }[] } };
type ObjectRecord = { id: string; code: string; name: string; active: boolean };
type Measurement = { id: string; controlled_object_id: string; measurement_kind: string; authorized_context_id: string | null; numerator: string; denominator: string; unit: string; as_of: string; truth_type: string };
type Assessment = { id: string; controlled_object_id: string; assessment_status: string; data_date: string; caseLabel?: string };
const policyFields = [
  ["progress_yellow_deficit", "Progress yellow deficit ratio", "1"], ["progress_red_deficit", "Progress red deficit ratio", "1"],
  ["schedule_yellow_days", "Schedule yellow exposure (days)", ""], ["schedule_red_days", "Schedule red exposure (days)", ""],
  ["cost_yellow_overrun", "Cost yellow overrun ratio", "1"], ["cost_red_overrun", "Cost red overrun ratio", "1"],
  ["evidence_red_below", "Evidence red below confidence", "1"], ["evidence_green_at_least", "Evidence green at least confidence", "1"],
  ["material_weight_threshold", "Material red package weight", "1"], ["maximum_source_age_days", "Maximum source age (days)", "365"],
];

export function SnapshotComposer() {
  const [connection, setConnection] = useState<Connection | null>(null);
  const [projectTimezone, setProjectTimezone] = useState("UTC");
  const [sources, setSources] = useState<Source[]>([]);
  const [objects, setObjects] = useState<ObjectRecord[]>([]);
  const [measurements, setMeasurements] = useState<Measurement[]>([]);
  const [cases, setCases] = useState<{ id: string; case_number: string; title: string }[]>([]);
  const [costs, setCosts] = useState<Assessment[]>([]);
  const [schedules, setSchedules] = useState<Assessment[]>([]);
  const [weightingId, setWeightingId] = useState("");
  const [scheduleId, setScheduleId] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("Load a project to choose exact authorized sources and governed measurements.");
  const [issued, setIssued] = useState<{ snapshot_number: number; planned_ratio: string; actual_ratio: string } | null>(null);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);
  function clear() {
    controller.current?.abort(); setConnection(null); setSources([]); setObjects([]); setMeasurements([]); setCases([]);
    setCosts([]); setSchedules([]); setWeightingId(""); setScheduleId(""); setProjectTimezone("UTC"); setIssued(null); setMessage("Load the selected project before composing a snapshot.");
  }
  async function request(path: string, body?: unknown, active = connection) {
    if (!active) throw new Error("Load a project first.");
    const response = await fetch(`${API}/api/v1/projects/${active.projectId}${path}`, {
      method: body === undefined ? "GET" : "POST", signal: controller.current?.signal,
      headers: { "Content-Type": "application/json", "X-VAI-Actor-ID": active.actorId, "X-VAI-Organization-ID": active.organizationId,
        ...(body === undefined ? {} : { "Idempotency-Key": crypto.randomUUID() }) },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const result = await response.json().catch(() => null);
    if (!response.ok) throw new Error(typeof result?.detail === "string" ? result.detail : JSON.stringify(result?.detail ?? `Request failed (${response.status})`));
    return result;
  }
  async function act(action: () => Promise<void>, success: string) {
    setBusy(true);
    try { await action(); setMessage(success); }
    catch (error) { if (!(error instanceof DOMException && error.name === "AbortError")) setMessage(error instanceof Error ? error.message : "Snapshot request failed."); }
    finally { setBusy(false); }
  }
  function connect(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = new FormData(event.currentTarget); clear(); controller.current = new AbortController();
    const active = { projectId: String(form.get("projectId")), actorId: String(form.get("actorId")), organizationId: String(form.get("organizationId")) };
    void act(async () => {
      const data = await Promise.all(["/authorized-context/versions", "/controlled-objects", "/progress/measurements", "/decision-cases", ""].map((path) => request(path, undefined, active)));
      setSources(data[0]); setObjects(data[1]); setMeasurements(data[2]); setCases(data[3]); setProjectTimezone(data[4].timezone); setConnection(active); localStorage.setItem("vai-active-project", active.projectId);
    }, "Snapshot sources loaded. Choose the authorized weighting and schedule explicitly.");
  }
  const entries = sources.find((item) => item.id === weightingId)?.payload.entries ?? [];
  const weighted = entries.map((entry) => ({ ...entry, object: objects.find((item) => item.active && item.code === entry.controlled_object_code) }));
  const candidateLabel = (item: Measurement) => {
    const instant = /(?:Z|[+-]\d{2}:\d{2})$/i.test(item.as_of) ? item.as_of : `${item.as_of}Z`;
    return `${item.measurement_kind.replaceAll("_", " ")} · ${item.numerator}/${item.denominator} ${item.unit} · ${new Date(instant).toLocaleString(undefined, { timeZone: projectTimezone })} ${projectTimezone} · ${item.truth_type}`;
  };
  const merge = (old: Assessment[], incoming: Assessment[]) => [...old.filter((item) => !incoming.some((value) => value.id === item.id)), ...incoming];
  return <section className="workbench-card snapshot-composer" aria-label="Issue project-control snapshot"><details><summary>Issue project-control snapshot</summary>
    <p>Freeze exact authorized plan and governed observations for reports, health and the command center. This does not authorize a schedule, verify reported work or issue an execution instruction.</p>
    <form className="inline-form context-form" onSubmit={connect} onChange={clear}><fieldset disabled={busy}><ProjectContextFields /><button>Load snapshot sources</button></fieldset></form>
    <p role="status">{message}</p>
    <fieldset disabled={busy || !connection}>
      <legend>Optional case assessments</legend>
      <p>Load exact case-bound analyses before selecting them below. Unselected or restricted analyses remain visibly unknown or limited.</p>
      <form className="stack-form" onSubmit={(event) => {
        event.preventDefault(); const form = new FormData(event.currentTarget); const id = String(form.get("caseId"));
        void act(async () => {
          const data = await Promise.all(["cost", "schedule"].map((kind) => request(`/decision-cases/${id}/${kind}-assessments`)));
          const label = cases.find((item) => item.id === id)?.case_number;
          setCosts((old) => merge(old, data[0].map((item: Assessment) => ({ ...item, caseLabel: label }))));
          setSchedules((old) => merge(old, data[1].map((item: Assessment) => ({ ...item, caseLabel: label }))));
        }, "Case assessments loaded. Select the exact records to freeze.");
      }}><label>Assessment case<select name="caseId" required><option value="">Choose case</option>{cases.map((item) => <option key={item.id} value={item.id}>{item.case_number} · {item.title}</option>)}</select></label><button>Load case assessments</button></form>
    </fieldset>
    <form className="stack-form" onSubmit={(event) => {
      event.preventDefault(); const form = new FormData(event.currentTarget);
      void act(async () => {
        const result = await request("/project-control/snapshots", {
          data_date: new Date(String(form.get("dataDate"))).toISOString(), progress_weighting_context_id: weightingId, schedule_context_id: scheduleId,
          packages: weighted.map((entry) => ({ controlled_object_id: entry.object?.id, planned_measurement_id: form.get(`planned-${entry.object?.id}`), actual_measurement_id: form.get(`actual-${entry.object?.id}`) })),
          cost_assessment_ids: form.getAll("costIds"), schedule_assessment_ids: form.getAll("scheduleIds"),
          health_policy: { version: form.get("policyVersion"), owner_actor_id: connection?.actorId, rationale: form.get("policyRationale"), effective_from: new Date(String(form.get("policyEffective"))).toISOString(), ...Object.fromEntries(policyFields.map(([name]) => [name, form.get(name)])) },
        }); setIssued(result);
      }, "Immutable project-control snapshot issued. Its sources and limitations are retained.");
    }}>
      <fieldset disabled={busy || !connection}><legend>Exact sources and observed progress</legend>
        <label>Authorized progress weights<select required value={weightingId} onChange={(event) => { setWeightingId(event.target.value); setIssued(null); }}><option value="">Choose authorized weights</option>{sources.filter((item) => item.context_type === "PROGRESS_WEIGHTING" && item.semantic_state === "CURRENT_AUTHORIZED").map((item) => <option key={item.id} value={item.id}>Weighting version {item.version_number}</option>)}</select></label>
        <label>Authorized snapshot schedule<select required value={scheduleId} onChange={(event) => { setScheduleId(event.target.value); setIssued(null); }}><option value="">Choose authorized schedule</option>{sources.filter((item) => item.context_type === "SCHEDULE" && item.semantic_state === "CURRENT_AUTHORIZED").map((item) => <option key={item.id} value={item.id}>Schedule version {item.version_number}</option>)}</select></label>
        <label>Snapshot reporting cutoff (browser timezone)<input type="datetime-local" name="dataDate" step="1" required /></label>
        <p>Each planned/actual pair must share an exact observation time, measurement basis, unit and denominator on the project reporting day ({projectTimezone}). Observation choices show project time; the cutoff input uses your browser timezone. The API revalidates every source.</p>
        {weighted.map((entry) => <fieldset key={`${weightingId}-${scheduleId}-${entry.controlled_object_code}`}><legend>{entry.controlled_object_code} · weight {entry.weight}</legend>{!entry.object ? <p role="alert">This authorized work package is missing or inactive. Correct the governed context before issuing a snapshot.</p> : <>
          <label>Planned measurement for {entry.controlled_object_code}<select name={`planned-${entry.object.id}`} required><option value="">Choose authorized planned point</option>{measurements.filter((item) => item.controlled_object_id === entry.object?.id && item.measurement_kind === "PLANNED_AUTHORIZED" && item.authorized_context_id === scheduleId).map((item) => <option key={item.id} value={item.id}>{candidateLabel(item)}</option>)}</select></label>
          <label>Actual measurement for {entry.controlled_object_code}<select name={`actual-${entry.object.id}`} required><option value="">Choose verified or accepted observation</option>{measurements.filter((item) => item.controlled_object_id === entry.object?.id && ["VERIFIED", "ACCEPTED_RELEASED"].includes(item.measurement_kind)).map((item) => <option key={item.id} value={item.id}>{candidateLabel(item)}</option>)}</select></label>
        </>}</fieldset>)}
        {[ ["costIds", "Cost assessments", costs], ["scheduleIds", "Schedule assessments", schedules] ].map(([name, label, values]) => <label key={String(name)}>{String(label)} (optional)<select multiple name={String(name)}>{(values as Assessment[]).map((item) => <option key={item.id} value={item.id}>{item.caseLabel} · {objects.find((object) => object.id === item.controlled_object_id)?.code} · {item.assessment_status} · {item.data_date} · {item.id}</option>)}</select></label>)}
      </fieldset>
      <fieldset disabled={busy || !connection} className="snapshot-policy"><legend>Explicit project health policy</legend>
        <p>Ratios use 0–1. Enter the approved project thresholds; no numerical defaults are supplied. Red/yellow ordering and ownership are checked by the API.</p>
        <p>Policy owner and acting user: {connection?.actorId ?? "Load a project first"}.</p>
        <label>Health policy version<input name="policyVersion" minLength={3} required /></label><label>Health policy rationale<textarea name="policyRationale" minLength={10} required /></label><label>Health policy effective from (browser timezone)<input type="datetime-local" step="1" name="policyEffective" required /></label>
        {policyFields.map(([name, label, max]) => <label key={name}>{label}<input type="number" name={name} min={name === "evidence_red_below" || name === "maximum_source_age_days" ? "0" : "0.000000001"} max={max || undefined} step={name === "maximum_source_age_days" ? "1" : "any"} required /></label>)}
      </fieldset>
      <button disabled={busy || !connection || !weightingId || !scheduleId || weighted.some((entry) => !entry.object)}>Issue immutable control snapshot</button>
    </form>
    {issued && <p role="status">Snapshot {issued.snapshot_number} issued · planned ratio {issued.planned_ratio} · verified/accepted actual ratio {issued.actual_ratio}. <Link href="/">Open updated command center</Link></p>}
  </details></section>;
}
