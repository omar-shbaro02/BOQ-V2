"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { ProjectContextFields } from "../project-context-fields";
import { ProgressBasisValues, ProgressWeightingBasisValues } from "../../src/generated/taxonomies";

const API = process.env.NEXT_PUBLIC_VAI_API_URL ?? "http://localhost:8000";
type Connection = { projectId: string; actorId: string; organizationId: string };
type ObjectRecord = { id: string; code: string; name: string; object_type: string; active: boolean };
type ContextRecord = { id: string; record_type: string; record_key: string; version_number: number; current_status: string; lifecycle_events: unknown[]; payload: Record<string, unknown>; evidence_item_ids: string[] };
type Grant = { id: string; actor_id: string; authority_type: string; active: boolean; controlled_object_id: string | null };
type Evidence = { id: string; field_name: string; semantic_state: string; value: unknown; as_of: string };
type Source = { id: string; context_type: string; version_number: number; semantic_state: string; payload: Record<string, unknown> };
const lines = (value: FormDataEntryValue | null) => String(value ?? "").split("\n").map((line) => line.trim()).filter(Boolean);
const text = (form: FormData, key: string) => String(form.get(key) ?? "").trim();
const instant = (form: FormData, key: string) => new Date(text(form, key)).toISOString();

export function ProjectControls() {
  const [connection, setConnection] = useState<Connection | null>(null);
  const [project, setProject] = useState<{ name: string; timezone: string; currency: string } | null>(null);
  const [objects, setObjects] = useState<ObjectRecord[]>([]);
  const [records, setRecords] = useState<ContextRecord[]>([]);
  const [grants, setGrants] = useState<Grant[]>([]);
  const [evidence, setEvidence] = useState<Evidence[]>([]);
  const [sources, setSources] = useState<Source[]>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("Load a project to manage its charter, work packages and report recipients.");
  const [approvalGrant, setApprovalGrant] = useState("");
  const [reason, setReason] = useState("");
  const [reference, setReference] = useState("");
  const [sourceKind, setSourceKind] = useState("PROGRESS_WEIGHTING");
  const [sourceId, setSourceId] = useState("");
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);

  function clear() {
    controller.current?.abort(); setConnection(null); setProject(null); setObjects([]); setRecords([]);
    setEvidence([]); setSources([]); setGrants([]); setApprovalGrant(""); setReason(""); setReference("");
    setSourceId("");
    setMessage("Load the selected project before recording changes.");
  }
  async function request(path: string, body?: unknown, active = connection) {
    if (!active) throw new Error("Load a project first.");
    const response = await fetch(`${API}/api/v1/projects/${active.projectId}${path}`, {
      method: body === undefined ? "GET" : "POST", signal: controller.current?.signal,
      headers: { "Content-Type": "application/json", "X-VAI-Actor-ID": active.actorId,
        "X-VAI-Organization-ID": active.organizationId, ...(body === undefined ? {} : { "Idempotency-Key": crypto.randomUUID() }) },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const result = await response.json().catch(() => null);
    if (!response.ok) throw new Error(typeof result?.detail === "string" ? result.detail : JSON.stringify(result?.detail ?? `Request failed (${response.status})`));
    return result;
  }
  async function refresh(active = connection) {
    const data = await Promise.all(["", "/controlled-objects", "/project-context/records", "/authority-grants", "/evidence/items", "/authorized-context/versions"].map((path) => request(path, undefined, active)));
    setProject(data[0]); setObjects(data[1]); setRecords(data[2]); setGrants(data[3]); setEvidence(data[4]); setSources(data[5]);
  }
  async function act(action: () => Promise<void>, success: string) {
    setBusy(true);
    try { await action(); setMessage(success); }
    catch (error) { if (!(error instanceof DOMException && error.name === "AbortError")) setMessage(error instanceof Error ? error.message : "Project request failed."); }
    finally { setBusy(false); }
  }
  function connect(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = new FormData(event.currentTarget);
    clear(); controller.current = new AbortController();
    const active = { projectId: text(form, "projectId"), actorId: text(form, "actorId"), organizationId: text(form, "organizationId") };
    void act(async () => { await refresh(active); setConnection(active); localStorage.setItem("vai-active-project", active.projectId); }, "Project controls loaded.");
  }
  function latest(kind: string, key: string) { return records.filter((item) => item.record_type === kind && item.record_key === key).sort((a, b) => b.version_number - a.version_number)[0]; }
  function saveRecord(event: FormEvent<HTMLFormElement>, kind: string, payload: (form: FormData) => Record<string, unknown>) {
    event.preventDefault(); const form = new FormData(event.currentTarget);
    const key = kind === "CHARTER" ? "PROJECT_CHARTER" : text(form, "recordKey");
    void act(async () => {
      await request("/project-context/records", { record_type: kind, record_key: key,
        effective_from: instant(form, "effectiveFrom"), payload: payload(form),
        evidence_item_ids: form.getAll("evidenceIds"), supersedes_record_id: latest(kind, key)?.id ?? null });
      await refresh();
    }, `${kind.replaceAll("_", " ")} version recorded. Review and authority remain separate.`);
  }
  function transition(item: ContextRecord, status: "REVIEWED" | "APPROVED") {
    void act(async () => {
      await request(`/project-context/records/${item.id}/transitions?expected_version=${item.lifecycle_events.length}`, {
        to_status: status, reason, authority_grant_id: status === "APPROVED" ? approvalGrant || null : null,
        approval_reference: status === "APPROVED" ? reference : null,
      }); await refresh();
    }, `Charter ${status.toLowerCase()}. Operational evidence has not been verified by this action.`);
  }
  const charterGrants = grants.filter((item) => item.active && item.actor_id === connection?.actorId && item.authority_type === "CHARTER_APPROVAL" && !item.controlled_object_id);
  return <section className="project-control-workspace" aria-label="Project governance setup">
    <section className="workbench-card">
      <h2>Project governance setup</h2><p>Create the working context before planning and reporting. Stored assertions, human approvals and verified operational evidence remain separate.</p>
      <form className="inline-form context-form" onSubmit={connect} onChange={clear}><fieldset disabled={busy}><ProjectContextFields /><button>Load project controls</button></fieldset></form>
      <p role="status">{message}</p>
      {project && <p><strong>{project.name}</strong> · {project.timezone} · {project.currency}. Acting user: {connection?.actorId}. Time entries use your browser timezone ({Intl.DateTimeFormat().resolvedOptions().timeZone}); reporting dates are checked against the project timezone.</p>}
    </section>
    <fieldset disabled={!connection || busy} className="project-control-sections">
      <legend>Project context and planning controls</legend>
      <section className="workbench-card" aria-label="Work package setup"><h3>Work packages and WBS</h3>
        <form className="stack-form" onSubmit={(event) => {
          event.preventDefault(); const form = new FormData(event.currentTarget);
          void act(async () => {
            const item = await request("/controlled-objects", { object_type: text(form, "objectType"), code: text(form, "code"), name: text(form, "name") });
            await refresh();
            if (form.get("parent")) await request("/relations", { source_id: text(form, "parent"), target_id: item.id, relation_type: "CONTAINS" });
          }, "Controlled object saved. Any selected containment link was recorded separately.");
        }}>
          <label>Object type<select name="objectType"><option value="AREA">WBS area</option><option value="WORK_PACKAGE">Work package</option><option value="ACTIVITY">Activity</option></select></label>
          <label>Object code<input name="code" required /></label><label>Object name<input name="name" required /></label>
          <label>Parent WBS object<select name="parent"><option value="">No parent</option>{objects.filter((item) => item.active).map((item) => <option key={item.id} value={item.id}>{item.code} · {item.name}</option>)}</select></label>
          <button>Create controlled object</button>
        </form>
        <ul>{objects.map((item) => <li key={item.id}>{item.code} · {item.name} · {item.object_type.replaceAll("_", " ")}</li>)}</ul>
      </section>
      <section className="workbench-card" aria-label="Project charter"><h3>Project charter</h3><p>Saving a revision preserves the prior version. Review and approval are explicit actions below.</p>
        <form className="stack-form" onSubmit={(event) => saveRecord(event, "CHARTER", (form) => ({ objectives: lines(form.get("objectives")), constraints: lines(form.get("constraints")), success_criteria: lines(form.get("criteria")), delivery_strategy: text(form, "strategy"), authority_reference: text(form, "authorityReference") }))}>
          <label>Objectives (one per line)<textarea name="objectives" required /></label><label>Constraints (one per line)<textarea name="constraints" /></label>
          <label>Success criteria (one per line)<textarea name="criteria" required /></label><label>Delivery strategy<input name="strategy" minLength={3} required /></label>
          <label>Charter authority reference<input name="authorityReference" minLength={3} required /></label><EffectiveFrom /><button>Save charter version</button>
        </form>
        <div className="stack-form"><label>My charter approval authority<select value={approvalGrant} onChange={(event) => setApprovalGrant(event.target.value)}><option value="">No authority selected</option>{charterGrants.map((item) => <option key={item.id} value={item.id}>{item.authority_type} · {item.id}</option>)}</select></label>
          <label>Charter review or approval rationale<input value={reason} onChange={(event) => setReason(event.target.value)} /></label><label>Charter approval reference<input value={reference} onChange={(event) => setReference(event.target.value)} /></label></div>
        {!charterGrants.length && <p>No matching active charter grant is available. A project administrator must provision authority; saving or reviewing cannot approve the charter.</p>}
        <ul>{records.filter((item) => item.record_type === "CHARTER").map((item) => <li key={item.id}>Charter version {item.version_number} · <strong>{item.current_status}</strong>{latest(item.record_type, item.record_key)?.id === item.id && <>{item.current_status === "DRAFT" ? <button disabled={reason.trim().length < 3} onClick={() => transition(item, "REVIEWED")}>Review charter version {item.version_number}</button> : item.current_status === "REVIEWED" ? <button disabled={!approvalGrant || reason.trim().length < 3 || reference.trim().length < 3} onClick={() => transition(item, "APPROVED")}>Approve charter version {item.version_number}</button> : null}</>}<details><summary>Stored charter and lineage</summary><pre>{JSON.stringify(item.payload, null, 2)}</pre><small>{item.id} · {item.lifecycle_events.length} lifecycle events</small></details></li>)}</ul>
      </section>
      <section className="workbench-card" aria-label="Stakeholder registry"><h3>Stakeholders and report recipients</h3>
        <form className="stack-form" onSubmit={(event) => saveRecord(event, "STAKEHOLDER", (form) => ({ name: text(form, "name"), project_role: text(form, "role"), communication_rules: lines(form.get("rules")), report_recipient: form.get("recipient") === "on" }))}>
          <label>Stakeholder key<input name="recordKey" required /></label><label>Stakeholder name<input name="name" minLength={2} required /></label><label>Project role<input name="role" minLength={2} required /></label>
          <label>Communication rules (one per line)<textarea name="rules" required /></label><label className="checkbox-label"><input type="checkbox" name="recipient" />Eligible for approved reports</label><EffectiveFrom /><button>Save stakeholder version</button>
        </form>
        <ul>{records.filter((item) => item.record_type === "STAKEHOLDER").map((item) => <li key={item.id}>{String(item.payload.name)} · {item.record_key} · version {item.version_number} · {item.current_status}</li>)}</ul>
      </section>
      <section className="workbench-card" aria-label="Daily update"><h3>Evidence-linked daily update</h3><p>Updates remain reported. Verify claims separately in Evidence before using verified progress.</p>
        <form className="stack-form" onSubmit={(event) => saveRecord(event, "DAILY_UPDATE", (form) => ({ data_date: text(form, "dataDate"), reporting_cutoff: instant(form, "cutoff"), weather: { condition: text(form, "weather") }, labor: [], equipment: [], quantities: [{ controlled_object_id: text(form, "object"), quantity: text(form, "quantity"), unit: text(form, "unit") }], blockers: lines(form.get("blockers")), safety_quality_observations: lines(form.get("observations")) }))}>
          <label>Daily update key<input name="recordKey" required /></label><label>Project reporting date<input type="date" name="dataDate" required /></label><label>Reporting cutoff<input type="datetime-local" name="cutoff" required /></label><EffectiveFrom />
          <label>Reported weather<input name="weather" required /></label><label>Updated work package<select name="object" required><option value="">Choose object</option>{objects.filter((item) => item.active).map((item) => <option key={item.id} value={item.id}>{item.code} · {item.name}</option>)}</select></label>
          <label>Reported quantity<input type="number" name="quantity" min="0" step="any" required /></label><label>Quantity unit<input name="unit" required /></label>
          <label>Blockers (one per line)<textarea name="blockers" /></label><label>Safety and quality observations (one per line)<textarea name="observations" /></label>
          <label>Supporting evidence (select one or more)<select name="evidenceIds" multiple required>{evidence.map((item) => <option key={item.id} value={item.id}>{item.field_name} · {String(item.value)} · {item.semantic_state}</option>)}</select></label><button>Record reported daily update</button>
        </form>
      </section>
      <section className="workbench-card" aria-label="Budget and weighting controls"><h3>Budget and progress weights</h3>
        <p>Save a proposed source first. Authorization is a separate human action with a matching grant. No weights or amounts are inferred.</p>
        <form className="stack-form" onSubmit={(event) => {
          event.preventDefault(); const form = new FormData(event.currentTarget);
          void act(async () => {
            const payload = sourceKind === "BUDGET" ? { currency: project?.currency, approved_budget: text(form, "budget"), controlled_object_code: text(form, "budgetObject"), measurement_basis: "COST_VALUE" } : {
              data_date: text(form, "dataDate"), weighting_basis: text(form, "weightingBasis"), measurement_basis: text(form, "measurementBasis"), source_reference: text(form, "sourceReference"),
              entries: objects.filter((item) => item.active && item.object_type === "WORK_PACKAGE" && text(form, `weight-${item.id}`) !== "").map((item) => ({ controlled_object_code: item.code, weight: text(form, `weight-${item.id}`) })),
            };
            const source = await request("/authorized-context/versions", { context_type: sourceKind, semantic_state: "PROPOSED", effective_from: instant(form, "effectiveFrom"), payload });
            await refresh(); setSourceId(source.id);
          }, "Proposed control source saved. It is not authorized.");
        }}>
          <label>Control source type<select value={sourceKind} onChange={(event) => { setSourceKind(event.target.value); setSourceId(""); }}><option value="PROGRESS_WEIGHTING">Progress weights</option><option value="BUDGET">Budget</option></select></label>
          {sourceKind === "BUDGET" ? <><label>Budget proposal amount ({project?.currency ?? "project currency"})<input name="budget" type="number" min="0" step="any" required /></label><label>Budget work package<select name="budgetObject" required><option value="">Choose budget scope</option>{objects.filter((item) => item.active && item.object_type === "WORK_PACKAGE").map((item) => <option key={item.id} value={item.code}>{item.code} · {item.name}</option>)}</select></label></> : <>
            <label>Weight source data date<input name="dataDate" type="date" required /></label><label>Weighting basis<select name="weightingBasis">{ProgressWeightingBasisValues.map((value) => <option key={value}>{value}</option>)}</select></label>
            <label>Weighted measurement basis<select name="measurementBasis" defaultValue="PHYSICAL_VERIFIED">{ProgressBasisValues.map((value) => <option key={value}>{value}</option>)}</select></label><label>Weight source reference<input name="sourceReference" minLength={3} required /></label>
            {objects.filter((item) => item.active && item.object_type === "WORK_PACKAGE").map((item) => <label key={item.id}>Weight for {item.code} (0–1)<input name={`weight-${item.id}`} type="number" min="0.000000001" max="1" step="any" /></label>)}
            <p>Enter positive weights for the selected work packages. They must total exactly 1; omitted packages remain excluded with visible limitations.</p>
          </>}
          <EffectiveFrom /><button>Save proposed control source</button>
        </form>
        <form className="stack-form" key={sourceId} onSubmit={(event) => {
          event.preventDefault(); const form = new FormData(event.currentTarget);
          void act(async () => {
            const source = sources.find((item) => item.id === sourceId);
            if (!source || source.semantic_state !== "PROPOSED") throw new Error("Choose a proposed control source.");
            await request("/authorized-context/activate", { source_version_id: source.id, authority_grant_id: text(form, "grant"), expected_current_context_id: sources.find((item) => item.context_type === source.context_type && item.semantic_state === "CURRENT_AUTHORIZED")?.id ?? null, approval_reference: text(form, "approvalReference"), reason: text(form, "reason") });
            await refresh(); setSourceId("");
          }, "Control source authorized through the separate human authority route.");
        }}>
          <label>Proposed source to authorize<select required value={sourceId} onChange={(event) => setSourceId(event.target.value)}><option value="">Choose proposed source</option>{sources.filter((item) => item.semantic_state === "PROPOSED").map((item) => <option key={item.id} value={item.id}>{item.context_type} · version {item.version_number}</option>)}</select></label>
          {sourceId && <details open><summary>Review exact proposed control inputs</summary><pre>{JSON.stringify(sources.find((item) => item.id === sourceId)?.payload, null, 2)}</pre></details>}
          <label>My control approval authority<select name="grant" required key={sourceId}><option value="">Choose matching authority</option>{grants.filter((item) => item.active && item.actor_id === connection?.actorId && !item.controlled_object_id && item.authority_type === `${sources.find((source) => source.id === sourceId)?.context_type}_APPROVAL`).map((item) => <option key={item.id} value={item.id}>{item.authority_type} · {item.id}</option>)}</select></label>
          <label>Control approval reference<input name="approvalReference" minLength={3} required /></label><label>Control authorization rationale<input name="reason" minLength={3} required /></label><button disabled={!sourceId}>Authorize selected control source</button>
        </form>
      </section>
      <section className="workbench-card" aria-label="Project context history"><h3>Immutable context history</h3><p>Reported context does not become a verified operational fact through review or approval.</p><ul>{records.map((item) => <li key={item.id}>{item.record_type.replaceAll("_", " ")} · {item.record_key} · version {item.version_number} · {item.current_status} · {item.evidence_item_ids.length} evidence links</li>)}</ul><h3>Schedule, budget and weighting history</h3><ul>{sources.map((item) => <li key={item.id}>{item.context_type} · version {item.version_number} · {item.semantic_state}</li>)}</ul></section>
    </fieldset>
  </section>;
}

function EffectiveFrom() { return <label>Effective from<input type="datetime-local" name="effectiveFrom" required /></label>; }
