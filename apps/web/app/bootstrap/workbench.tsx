"use client";

import { createContext, FormEvent, useCallback, useContext, useEffect, useRef, useState } from "react";
import { ProjectContextFields } from "../project-context-fields";
import { ControlInputs, type ControlInput, type ControlObject } from "./control-inputs";
import { SourceReview } from "./source-review";
import { JsonAction } from "./schedule-input-form";
import { MaterialCorrection, type CorrectionDraft } from "./material-correction";

const API = process.env.NEXT_PUBLIC_VAI_API_URL ?? "http://localhost:8000";
type Connection = { actorId: string; organizationId: string; projectId: string };
type Source = { id: string; artifact_id: string; version_number: number; extraction_status: string; extracted_row_count: number };
type Release = { id: string; state: string; version_number: number; authorized_context_id: string | null };
type Calculation = { id: string; readiness: string; proposed_finish: string | null; validation_findings: { code: string; severity: string; message: string }[] };
type Grant = { id: string; actor_id: string; authority_type: string; active: boolean };
type Artifact = { id: string; original_filename: string };
type PlanningStructure = { id: string; work_packages: { id: string; name: string; classification: string }[]; unmapped_lines: unknown[]; assumptions: unknown[] };
type DraftDetail = CorrectionDraft;
type RevisionDelta = { added_scope: unknown[]; removed_scope: unknown[]; changed_scope: unknown[]; mapping_changes: unknown[]; activity_changes: unknown[]; schedule_effects: Record<string, unknown> };
type PlannerEdit = { field_path: string; original_value: string; revised_value: string; reason: string };
const PhaseContext = createContext(0);
const phases = [
  { title: "Project & BOQ", detail: "Select the project and upload the BOQ document.", owner: "Project team", steps: "01–02" },
  { title: "Review the scope", detail: "Check extracted items and confirm how the work is grouped.", owner: "Planner / quantity surveyor", steps: "03–05" },
  { title: "Plan the schedule", detail: "Enter sourced durations, working days and task dependencies, then check the dates.", owner: "Planner", steps: "06–09" },
  { title: "Review & approve", detail: "Review the calculated plan, obtain separate approval and download the schedule.", owner: "Planner, then authorized approver", steps: "10–12" },
];
function phaseFor(number: string) { const value = Number(number); return value <= 2 ? 0 : value <= 5 ? 1 : value <= 9 ? 2 : 3; }

export function BootstrapWorkbench() {
  const [phase, setPhase] = useState(0);
  const phaseHeading = useRef<HTMLHeadingElement>(null);
  const previousPhase = useRef(0);
  useEffect(() => {
    if (previousPhase.current === phase) return;
    previousPhase.current = phase;
    phaseHeading.current?.focus({ preventScroll: true });
    phaseHeading.current?.scrollIntoView({ block: "start", behavior: "smooth" });
  }, [phase]);
  const [connection, setConnection] = useState<Connection | null>(null);
  const [sources, setSources] = useState<Source[]>([]);
  const [releases, setReleases] = useState<Release[]>([]);
  const [calculation, setCalculation] = useState<Calculation | null>(null);
  const [grants, setGrants] = useState<Grant[]>([]);
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [latest, setLatest] = useState<Record<string, string>>({});
  const [structure, setStructure] = useState<PlanningStructure | null>(null);
  const [draft, setDraft] = useState<DraftDetail | null>(null);
  const [delta, setDelta] = useState<RevisionDelta | null>(null);
  const [controlObjects, setControlObjects] = useState<ControlObject[]>([]);
  const [controlInputs, setControlInputs] = useState<ControlInput[]>([]);
  const [plannerEdits, setPlannerEdits] = useState<PlannerEdit[]>([]);
  const [message, setMessage] = useState("Connect a project to begin.");
  const [busy, setBusy] = useState(false);

  const changeProject = useCallback(() => {
    setConnection(null); setGrants([]); setSources([]); setReleases([]); setArtifacts([]); setLatest({});
    setStructure(null); setDraft(null); setCalculation(null); setDelta(null);
    setControlInputs([]); setPlannerEdits([]); setControlObjects([]);
    setMessage("Load the selected project to begin.");
  }, []);

  const headers = (idempotency?: string, active = connection): HeadersInit => ({
    "Content-Type": "application/json",
    ...(active ? { "X-VAI-Actor-ID": active.actorId, "X-VAI-Organization-ID": active.organizationId } : {}),
    ...(idempotency ? { "Idempotency-Key": idempotency } : {}),
  });
  async function request(path: string, body?: unknown, idempotency?: string) {
    if (!connection) throw new Error("Connect a project first.");
    const response = await fetch(`${API}/api/v1/projects/${connection.projectId}/bootstrap${path}`, { method: body === undefined ? "GET" : "POST", headers: headers(idempotency), body: body === undefined ? undefined : JSON.stringify(body) });
    if (!response.ok) throw new Error(await readError(response));
    return response;
  }
  async function run(label: string, action: () => Promise<void>) {
    setBusy(true);
    try { await action(); setMessage(label); } catch (error) { setMessage(error instanceof Error ? error.message : "Request failed"); } finally { setBusy(false); }
  }
  async function refresh(active = connection) {
    if (!active) return;
    const [sourceResponse, releaseResponse, artifactResponse, objectResponse, grantResponse] = await Promise.all([
      fetch(`${API}/api/v1/projects/${active.projectId}/bootstrap/boq-sources`, { headers: headers(undefined, active) }),
      fetch(`${API}/api/v1/projects/${active.projectId}/bootstrap/schedule-releases`, { headers: headers(undefined, active) }),
      fetch(`${API}/api/v1/projects/${active.projectId}/evidence/artifacts`, { headers: headers(undefined, active) }),
      fetch(`${API}/api/v1/projects/${active.projectId}/controlled-objects`, { headers: headers(undefined, active) }),
      fetch(`${API}/api/v1/projects/${active.projectId}/authority-grants`, { headers: headers(undefined, active) }).catch(() => null),
    ]);
    setGrants(grantResponse?.ok ? await grantResponse.json() : []);
    if (!objectResponse.ok) throw new Error(await readError(objectResponse));
    setControlObjects(await objectResponse.json());
    if (!sourceResponse.ok) throw new Error(await readError(sourceResponse));
    if (!releaseResponse.ok) throw new Error(await readError(releaseResponse));
    if (!artifactResponse.ok) throw new Error(await readError(artifactResponse));
    setSources(await sourceResponse.json()); setReleases(await releaseResponse.json()); setArtifacts(await artifactResponse.json());
  }
  async function create<T extends { id: string } = { id: string }>(path: string, body: unknown, key: string): Promise<T> {
    const response = await request(path, body, crypto.randomUUID());
    const result = await response.json() as T;
    setLatest((current) => ({ ...current, [key]: result.id }));
    if (key === "source") setPhase(1);
    if (key === "reviewedStructure") setPhase(2);
    return result;
  }
  async function download(releaseId: string, format: string) {
    if (!connection) return;
    await run(`${format.toUpperCase()} export downloaded.`, async () => {
      const response = await request(`/schedule-releases/${releaseId}/export/${format}`);
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `schedule-${releaseId}.${format}`;
      anchor.click();
      URL.revokeObjectURL(url);
    });
  }
  async function connect(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = new FormData(event.currentTarget);
    if (busy) return;
    const next = { actorId: String(form.get("actorId")), organizationId: String(form.get("organizationId")), projectId: String(form.get("projectId")) };
    setConnection(null); setBusy(true);
    setSources([]); setReleases([]); setArtifacts([]); setLatest({}); setStructure(null);
    setDraft(null); setCalculation(null); setDelta(null); setPlannerEdits([]); setControlInputs([]); setControlObjects([]);
    try { await refresh(next); setConnection(next); setMessage("Project connected. Upload a BOQ or inspect its stored source history."); } catch (error) { setMessage(error instanceof Error ? error.message : "Connection failed"); } finally { setBusy(false); }
  }
  async function uploadAndRegister(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await run("BOQ file uploaded and source version preserved.", async () => {
      if (!connection) throw new Error("Connect a project first.");
      const priorId = String(form.get("priorId") ?? "").trim();
      const prior = priorId ? sources.find((item) => item.id === priorId) : null;
      if (priorId && !prior) throw new Error("Select a known prior BOQ source version.");
      const upload = new FormData();
      upload.set("source_type", "BOQ");
      upload.set("source_id", String(form.get("sourceId")));
      upload.set("upload", form.get("file") as File);
      if (prior) upload.set("supersedes_artifact_id", prior.artifact_id);
      const response = await fetch(`${API}/api/v1/projects/${connection.projectId}/evidence/artifacts`, {
        method: "POST",
        headers: {
          "X-VAI-Actor-ID": connection.actorId,
          "X-VAI-Organization-ID": connection.organizationId,
        },
        body: upload,
      });
      if (!response.ok) throw new Error(await readError(response));
      const artifact = await response.json() as { id: string };
      await create("/boq-sources", {
        artifact_id: artifact.id,
        prior_source_version_id: priorId || null,
      }, "source");
      await refresh();
    });
  }
  function values(event: FormEvent<HTMLFormElement>) { event.preventDefault(); return new FormData(event.currentTarget); }
  return <PhaseContext.Provider value={phase}><nav className="planning-stage-nav" aria-label="Schedule preparation stages">{phases.map((item, index) => <button key={item.title} type="button" aria-current={phase === index ? "step" : undefined} disabled={busy} onClick={() => setPhase(index)}><span aria-hidden="true">{index + 1}</span><strong>{item.title}</strong></button>)}</nav><section className="planning-stage-intro" aria-label="Current planning stage"><div><span className="eyebrow">Stage {phase + 1} of 4 · {phases[phase].owner}</span><h2 ref={phaseHeading} tabIndex={-1}>{phases[phase].title}</h2><p>{phases[phase].detail}</p></div><p className="planning-save-note">Changing stages only changes the view. Save each form before continuing; approval always needs an authorized human.</p></section><div className="workbench-grid bootstrap-grid">
    <Step number="01" title="Choose project"><form className="stack-form compact context-form" onSubmit={connect}><fieldset className="planning-project-fields" disabled={busy}><ProjectContextFields onConnectionChange={changeProject} /><button disabled={busy}>Load project</button></fieldset></form>{connection && sources.length > 0 ? <form className="stack-form compact" onSubmit={event => { const form = values(event); const selected = sources.find(item => item.id === form.get("savedSource")); if (!selected) return; setLatest({source:selected.id}); setStructure(null); setDraft(null); setCalculation(null); setControlInputs([]); setPlannerEdits([]); setDelta(null); setPhase(1); setMessage("Saved BOQ selected. Read and review its items before continuing."); }}><label>Or continue with a saved BOQ<select name="savedSource" required><option value="">Choose a saved BOQ version</option>{sources.map(item => <option key={item.id} value={item.id}>BOQ version {item.version_number}</option>)}</select></label><button disabled={busy}>Review saved BOQ</button></form> : null}</Step>
    <Step number="02" title="Preserve BOQ source"><form key={connection?.projectId ?? "no-project"} className="stack-form compact" onSubmit={(event) => void uploadAndRegister(event)}><label>BOQ file (Excel or PDF)<input name="file" type="file" accept=".xlsx,.xlsm,.pdf" required aria-describedby="boq-file-help" onChange={(event) => { const name = event.currentTarget.files?.[0]?.name; const reference = event.currentTarget.form?.elements.namedItem("sourceId") as HTMLInputElement | null; if (name && reference && !reference.value) reference.value = name; }} /></label><small id="boq-file-help" className="planning-field-help">Choose the BOQ containing descriptions, quantities and units. Excel and searchable PDFs are supported. Scans need a searchable copy.</small><label>Document name or revision<input name="sourceId" placeholder="e.g. Contract BOQ, revision 1" required /></label><small className="planning-field-help">The filename is filled in for you. Change it to the document title or revision printed on your BOQ.</small><details className="planning-optional"><summary>This replaces an earlier BOQ (optional)</summary><p>Choose the version it replaces. Leave Initial version for a first upload.</p><label>Prior BOQ version (revision only)<select name="priorId"><option value="">Initial version</option>{sources.map(item => <option key={item.id} value={item.id}>BOQ version {item.version_number}</option>)}</select></label></details><button disabled={!connection || busy}>Upload BOQ</button>{!connection ? <p className="planning-field-help">Load your project in step 01 to enable uploading.</p> : null}</form><details className="planning-optional"><summary>Use a file already saved to this project</summary><p>Select an existing BOQ instead of uploading again.</p><button type="button" disabled={!connection || busy} onClick={() => void run("Artifacts refreshed.", () => refresh())}>Refresh artifacts</button><form className="stack-form compact" onSubmit={(event) => { const form = values(event); void run("BOQ source preserved.", async () => { await create("/boq-sources", { artifact_id: form.get("artifactId"), prior_source_version_id: form.get("priorId") || null }, "source"); await refresh(); }); }}><label>Saved BOQ file<select name="artifactId" required><option value="">Choose a saved document</option>{artifacts.map(item => <option key={item.id} value={item.id}>{item.original_filename}</option>)}</select></label><label>Previous BOQ version (if revised)<select name="priorId"><option value="">First version</option>{sources.map(item => <option key={item.id} value={item.id}>BOQ version {item.version_number}</option>)}</select></label><button disabled={!connection || busy}>Use saved BOQ</button></form></details></Step>
    <Step number="03" title="Normalize and classify"><IdForm label="Source reference" suggested={latest.source} button="Normalize" disabled={!connection || busy} onSubmit={(form) => run("BOQ normalized and classified.", async () => { await create(`/boq-sources/${form.get("id")}/normalizations`, {}, "normalization"); })} /></Step>
    {connection && <div className="full-width" hidden={phase !== 1}><SourceReview key={`${connection.organizationId}:${connection.projectId}:${latest.source ?? ""}`} api={API} connection={connection} sources={sources} artifacts={artifacts} disabled={busy} /></div>}
    <Step number="04" title="Propose WBS and packages"><IdForm label="Source reference" suggested={latest.source} button="Generate structure" disabled={!connection || busy} onSubmit={(form) => run("Planning structure proposed.", async () => { const result = await create<PlanningStructure>(`/boq-sources/${form.get("id")}/planning-structures`, {}, "structure"); setStructure(result); })} />{structure && <div className="mini-ledger"><strong>{structure.work_packages.length} proposed packages</strong>{structure.work_packages.map((item) => <div key={item.id}>{item.name} · {item.classification}<small>{item.id}</small></div>)}<p>{structure.unmapped_lines.length} unmapped lines · {structure.assumptions.length} assumptions</p></div>}</Step>
    <Step number="05" title="Planner structure review"><form className="stack-form compact" onSubmit={(event) => { const form = values(event); void run("Structure review recorded.", async () => { await create(`/planning-structures/${form.get("id")}/revisions`, { action: "ACCEPT_PROPOSAL", reason: form.get("reason") }, "reviewedStructure"); }); }}><ReferenceField name="id" value={latest.structure} /><label>Review reason<input name="reason" minLength={10} required /></label><button disabled={!connection || busy || !latest.structure}>Accept proposal</button></form></Step>
    <Step number="06" title="Generate activities and durations"><JsonAction validationOwner={connection?.actorId ?? ""} idLabel="Reviewed structure reference" suggested={latest.reviewedStructure} placeholder='{"validation_owner":"planner@example.com","duration_inputs":[],"productivity_inputs":[]}' button="Generate draft" disabled={!connection || busy} onSubmit={(id, body) => run("Activity draft generated.", async () => { const result = await create(`/planning-structures/${id}/schedule-drafts`, body, "draft"); const detail = await request(`/schedule-drafts/${result.id}`); setDraft(await detail.json()); setControlInputs([]); })} />{draft && <div className="mini-ledger"><strong>{draft.activities.length} proposed activities</strong>{draft.activities.map((item) => <div key={item.id}>{item.activity_code} · {item.activity_name} · {item.duration_working_days ?? "duration unresolved"}<small>{item.id} · {item.activity_type} · package {item.work_package_id} · {item.boq_line_refs.length} BOQ lines</small></div>)}<p>{draft.assumptions.length} assumptions need review</p></div>}</Step>
    <Step number="07" title="Propose logic and calendar"><JsonAction validationOwner={connection?.actorId ?? ""} idLabel="Draft generation reference" suggested={latest.draft} placeholder='{"validation_owner":"planner@example.com","calendar":{"calendar_id":"PROJECT","name":"Project calendar","working_weekdays":[0,1,2,3,4,5],"working_hours_per_day":8,"holidays":[],"review_state":"ACCEPTED"},"dependencies":[],"milestones":[],"constraints":[],"sequence_templates":[]}' button="Create logic" disabled={!connection || busy} onSubmit={(id, body) => run("Schedule logic proposed.", async () => { await create(`/schedule-drafts/${id}/logic`, body, "logic"); })} /></Step>
    <Step number="08" title="Calculate CPM"><form className="stack-form compact" onSubmit={(event) => { const form = values(event); void run("Deterministic CPM completed.", async () => { const result = await create(`/schedule-drafts/${form.get("id")}/calculations`, { project_start: form.get("start") }, "calculation"); setCalculation(result as Calculation); }); }}><ReferenceField name="id" value={latest.draft} /><label>Project start<input name="start" type="date" required /></label><button disabled={!connection || busy || !latest.draft || !latest.logic}>Calculate and validate</button></form></Step>
    {connection && <div className="full-width" hidden={phase !== 2}><MaterialCorrection key={`${connection.projectId}:${draft?.id ?? latest.draft ?? ""}`} api={API} connection={connection} draftId={draft?.id ?? latest.draft} disabled={busy} onBusy={setBusy} onSaved={(detail, logicId) => {
      setDraft(detail); setCalculation(null); setPlannerEdits([]); setControlInputs([]); setDelta(null);
      setLatest((current) => ({ source: detail.source_version_id ?? current.source, normalization: current.normalization, structure: detail.planning_structure_id, reviewedStructure: detail.planning_structure_id, draft: detail.id, logic: logicId ?? "" }));
      setMessage("Corrected draft saved. Recalculate CPM in step 8, review the new calculation, and obtain separate authority.");
    }} /></div>}
    {draft?.correction_history && <section hidden={phase !== 2} className="workbench-card full-width source-review" aria-label="Recorded material correction"><h2>Recorded material correction</h2><p>Original inputs, revised inputs, actor and reason remain in immutable history. Dates and authority require separate steps.</p><pre>{JSON.stringify(draft.correction_history, null, 2)}</pre></section>}
    <Step number="09" title="Resolve validation"><p><strong>{calculation?.readiness ?? "No calculation loaded"}</strong>{calculation?.proposed_finish ? ` · proposed finish ${calculation.proposed_finish}` : ""}</p><div className="mini-ledger">{calculation?.validation_findings.map((item, index) => <div key={`${item.code}-${index}`}><strong>{item.severity} · {item.code}</strong><span>{item.message}</span></div>)}</div>{calculation?.readiness === "VALIDATION_BLOCKED" && <div><p>Correct the inputs in a new immutable reviewed version, then regenerate activities and logic and recalculate. The blocked version remains in history.</p><button type="button" disabled={busy || !latest.reviewedStructure} onClick={() => void run("New reviewed structure version created. Return to step 6 with corrected inputs.", async () => { await create(`/planning-structures/${latest.reviewedStructure}/revisions`, { action: "ACCEPT_PROPOSAL", reason: "Supersede blocked schedule calculation with corrected planning inputs." }, "reviewedStructure"); setCalculation(null); })}>Create corrected version</button></div>}</Step>
    <Step number="10" title="Planner schedule review"><ControlInputs key={`${draft?.id ?? ""}:${calculation?.id ?? ""}`} activities={draft?.activities ?? []} objects={controlObjects} inputs={controlInputs} onChange={setControlInputs} disabled={!connection || busy} /><p>Confirm dates, logic, and traceability before submitting. Material duration or logic corrections require a new reviewed draft and CPM calculation.</p><form className="stack-form compact" onSubmit={(event) => { const form = values(event); const code = String(form.get("activityCode") ?? ""); const field = String(form.get("field") ?? ""); const selected = draft?.activities.find((item) => item.activity_code === code); const revisedValue = String(form.get("revisedValue") ?? "").trim(); const reason = String(form.get("editReason") ?? "").trim(); if (!selected || !field) { setMessage("Choose an activity and a permitted field before adding an edit."); return; } const originalValue = field === "name" ? selected.activity_name : field === "responsible_owner" ? selected.responsible_role || "PROJECT_DELIVERY_MANAGER" : ""; if (!revisedValue || revisedValue === originalValue) { setMessage("Enter a value different from the recorded value."); return; } if (reason.length < 10) { setMessage("Explain each planner edit in at least ten characters."); return; } const edit = { field_path: `activities.${code}.${field}`, original_value: originalValue, revised_value: revisedValue, reason }; setPlannerEdits((current) => [...current.filter((item) => item.field_path !== edit.field_path), edit]); event.currentTarget.reset(); setMessage("Planner edit staged for immutable review history."); }}><label>Activity<select name="activityCode" required><option value="">Select an activity</option>{draft?.activities.map((item) => <option key={item.id} value={item.activity_code}>{item.activity_code} · {item.activity_name}</option>)}</select></label><label>Permitted reviewed field<select name="field" required><option value="">Select a field</option><option value="name">Activity name</option><option value="responsible_owner">Responsible owner</option></select></label><label>Revised value<input name="revisedValue" required /></label><label>Reason for this edit<input name="editReason" minLength={10} required /></label><button type="submit" disabled={!connection || busy}>Stage edit</button></form>{plannerEdits.length > 0 && <div className="mini-ledger"><strong>{plannerEdits.length} staged planner edit{plannerEdits.length === 1 ? "" : "s"}</strong>{plannerEdits.map((edit) => <div key={edit.field_path}><span>{edit.field_path} · {edit.original_value} → {edit.revised_value}</span><small>{edit.reason}</small><button type="button" disabled={busy} onClick={() => setPlannerEdits((current) => current.filter((item) => item.field_path !== edit.field_path))}>Remove</button></div>)}</div>}<form className="stack-form compact" onSubmit={(event) => { const form = values(event); void run("Planner review stored; PM approval required.", async () => { await create(`/schedule-calculations/${form.get("id")}/reviews`, { reason: form.get("reason"), edits: plannerEdits, control_inputs: controlInputs }, "reviewedRelease"); setPlannerEdits([]); setControlInputs([]); await refresh(); }); }}><ReferenceField name="id" value={calculation?.id} /><label>Review reason<input name="reason" minLength={10} required /></label><button disabled={!connection || busy || calculation?.readiness !== "PLANNER_REVIEW_REQUIRED"}>Submit for approval</button></form></Step>
    <Step number="11" title="Human authorization"><p>A project admin must create the exact active grant separately. A planner review does not grant approval authority.</p><details className="planning-optional"><summary>Administrator: set up approval permissions</summary><form className="stack-form compact" onSubmit={(event) => { const form = values(event); void run("Project-scoped schedule authority grant created.", async () => { if (!connection) throw new Error("Connect a project first."); const response = await fetch(`${API}/api/v1/projects/${connection.projectId}/authority-grants`, { method: "POST", headers: headers(), body: JSON.stringify({ actor_id: form.get("grantee") || connection.actorId, authority_type: form.get("authorityType"), valid_from: form.get("validFrom") || null, valid_until: form.get("validUntil") || null }) }); if (!response.ok) throw new Error(await readError(response)); const grant = await response.json() as { id: string }; setLatest((current) => ({ ...current, grant: grant.id })); await refresh(); }); }}><label>Authorized human account<input name="grantee" defaultValue={connection?.actorId} key={connection?.actorId} required /></label><label>Grant type<select name="authorityType"><option value="CURRENT_SCHEDULE_APPROVAL">Current schedule approval</option><option value="BASELINE_SCHEDULE_APPROVAL">Baseline schedule approval</option></select></label><label>Valid from<input name="validFrom" type="date" required /></label><label>Valid until (optional)<input name="validUntil" type="date" /></label><button disabled={!connection || busy}>Create exact authority grant</button></form></details><form className="stack-form compact" onSubmit={(event) => { const form = values(event); void run("Schedule authorized through exact human grant.", async () => { await create(`/schedule-releases/${form.get("releaseId")}/approve`, { authority_grant_id: form.get("grantId"), approval_reference: form.get("reference"), reason: form.get("reason"), authorize_as_baseline: form.get("baseline") === "on" }, "authorizedRelease"); await refresh(); }); }}><label>Schedule to approve<select name="releaseId" key={`${latest.reviewedRelease}:${releases.length}`} defaultValue={latest.reviewedRelease ?? ""} required><option value="">Choose a planner-reviewed schedule</option>{releases.filter(item => item.state === "PM_APPROVAL_REQUIRED").map(item => <option key={item.id} value={item.id}>Schedule version {item.version_number} - planner review complete</option>)}</select></label><label>Approval permission<select name="grantId" defaultValue={latest.grant ?? ""} key={`${latest.grant}:${grants.length}`} required><option value="">Choose your approval permission</option>{grants.filter(item => item.active && item.actor_id === connection?.actorId && ["CURRENT_SCHEDULE_APPROVAL", "BASELINE_SCHEDULE_APPROVAL"].includes(item.authority_type)).map(item => <option key={item.id} value={item.id}>{item.authority_type === "BASELINE_SCHEDULE_APPROVAL" ? "Approve baseline schedule" : "Approve current schedule"}</option>)}</select></label><p className="planning-field-help">No permission listed? Ask your project administrator to grant the matching schedule approval permission. Approval will still be checked by the server.</p><label>Approval reference<input name="reference" placeholder="e.g. approval memo or meeting minute reference" required /></label><label>Reason<input name="reason" minLength={10} required /></label><label><input name="baseline" type="checkbox" /> Baseline authorization</label><button disabled={!connection || busy || !releases.some(item => item.state === "PM_APPROVAL_REQUIRED") || !grants.some(item => item.active && item.actor_id === connection?.actorId && ["CURRENT_SCHEDULE_APPROVAL", "BASELINE_SCHEDULE_APPROVAL"].includes(item.authority_type))}>Authorize schedule</button></form></Step>
    <Step number="12" title="Publish, export, and revisions"><div className="mini-ledger">{sources.map((item) => <div key={item.id}><strong>BOQ v{item.version_number} · {item.extraction_status}</strong><small>{item.id}</small></div>)}{releases.map((item) => <div key={item.id}><strong>Schedule v{item.version_number} · {item.state}</strong><span>{["json", "csv", "xlsx"].map((format) => <button type="button" key={format} disabled={busy} onClick={() => void download(item.id, format)}>{format.toUpperCase()}</button>)}</span><small>{item.id}</small></div>)}</div><IdForm label="New BOQ source reference" suggested={latest.source} button="Create revision delta" disabled={!connection || busy} onSubmit={(form) => run("Revision delta created; authorized schedule unchanged.", async () => { const result = await create<RevisionDelta & { id: string }>(`/boq-sources/${form.get("id")}/revision-delta`, {}, "revisionDelta"); setDelta(result); })} />{delta && <div className="mini-ledger"><strong>Revision comparison · authorized schedule unchanged</strong><p>{delta.added_scope.length} added · {delta.removed_scope.length} removed · {delta.changed_scope.length} changed scope</p><p>{delta.mapping_changes.length} mapping changes · {delta.activity_changes.length} activity changes</p><p>Schedule effect: {String(delta.schedule_effects.status)}</p></div>}</Step>
    <p className="workbench-message full-width" role="status">{busy ? "Working…" : message}</p>
  </div><div className="planning-stage-actions">{phase > 0 ? <button type="button" disabled={busy} onClick={() => setPhase(value => value - 1)}>← Back: {phases[phase - 1].title}</button> : <span />}{phase < 3 ? <button type="button" disabled={busy || !connection} onClick={() => setPhase(value => value + 1)}>Next: {phases[phase + 1].title} →</button> : null}</div></PhaseContext.Provider>;
}

function Step({ number, title, children }: { number: string; title: string; children: React.ReactNode }) { const phase = useContext(PhaseContext); const help: Record<string, string> = { "01": "Choose the project these quantities and dates belong to, then load its saved records.", "02": "Upload the contract BOQ and give it a recognizable document name. Use the revision option only when replacing an earlier BOQ.", "03": "Read the saved BOQ into structured items. The document reference is filled automatically from your upload.", "04": "Group related BOQ items into proposed work packages, such as foundations or concrete works.", "05": "Check that the grouping covers the BOQ. Explain what you checked before accepting it.", "06": "Create the task list. Unconfirmed durations stay unresolved; enter supported quantities, rates or durations in the planning corrections below.", "07": "Tell us which days the site works and how long a working day lasts. Add task links in planning corrections, or use advanced structured inputs.", "08": "Enter the intended project start date. Dates are calculated from the reviewed working calendar and task links.", "09": "Read every blocking issue. Correct the planning inputs and recalculate before requesting approval.", "10": "Map tasks to project work packages, check the proposed dates and explain your review. Approval is a separate action.", "11": "An authorized approver records the approval reference and reason. A project administrator manages approval permissions separately.", "12": "Download a saved release. For a later BOQ revision, return to stage 1 and select the previous BOQ version." }; const titles: Record<string, string> = { "02": "Upload your BOQ", "03": "Read and check BOQ items", "04": "Group the work into packages", "05": "Confirm the work packages", "06": "Create the task list", "07": "Set working days and task links", "08": "Calculate schedule dates", "09": "Fix issues before review", "10": "Planner review", "11": "Approve the reviewed schedule", "12": "Download schedules & compare revisions" }; return <section hidden={phaseFor(number) !== phase} data-bootstrap-step={number} data-planning-phase={phaseFor(number)} className="workbench-card"><span className="step-number">Step {number}</span><h2>{titles[number] ?? title}</h2><p className="planning-field-help">{help[number]}</p>{children}</section>; }
function ReferenceField({ name, value }: { name: string; value?: string }) { return <><input type="hidden" name={name} value={value ?? ""} readOnly />{value ? <details className="planning-reference"><summary>Selected record - technical reference</summary><code>{value}</code></details> : <p className="planning-field-help">Complete the previous step to select this input automatically.</p>}</>; }
function IdForm({ label, suggested, button, disabled, onSubmit }: { label: string; suggested?: string; button: string; disabled: boolean; onSubmit: (form: FormData) => Promise<void> }) { return <form aria-label={label} className="stack-form compact" onSubmit={(event) => { event.preventDefault(); void onSubmit(new FormData(event.currentTarget)); }}><ReferenceField name="id" value={suggested} /><button disabled={disabled || !suggested}>{button}</button></form>; }
async function readError(response: Response) { const payload = await response.json().catch(() => null) as { detail?: string | { msg?: string }[] } | null; return typeof payload?.detail === "string" ? payload.detail : Array.isArray(payload?.detail) ? payload.detail.map((item) => item.msg).join("; ") : `Request failed (${response.status})`; }
