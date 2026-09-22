"use client";

import { FormEvent, useState } from "react";

const API = process.env.NEXT_PUBLIC_VAI_API_URL ?? "http://localhost:8000";
type Connection = { actorId: string; organizationId: string; projectId: string };
type Source = { id: string; artifact_id: string; version_number: number; extraction_status: string; extracted_row_count: number };
type Release = { id: string; state: string; version_number: number; authorized_context_id: string | null };
type Calculation = { id: string; readiness: string; proposed_finish: string | null; validation_findings: { code: string; severity: string; message: string }[] };
type Artifact = { id: string; original_filename: string };
type PlanningStructure = { id: string; work_packages: { id: string; name: string; classification: string }[]; unmapped_lines: unknown[]; assumptions: unknown[] };
type DraftDetail = { id: string; activities: { id: string; activity_code: string; activity_name: string; activity_type: string; work_package_id: string; duration_working_days: string | null; boq_line_refs: string[]; responsible_role: string | null }[]; assumptions: unknown[] };
type RevisionDelta = { added_scope: unknown[]; removed_scope: unknown[]; changed_scope: unknown[]; mapping_changes: unknown[]; activity_changes: unknown[]; schedule_effects: Record<string, unknown> };

export function BootstrapWorkbench() {
  const [connection, setConnection] = useState<Connection | null>(null);
  const [sources, setSources] = useState<Source[]>([]);
  const [releases, setReleases] = useState<Release[]>([]);
  const [calculation, setCalculation] = useState<Calculation | null>(null);
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [latest, setLatest] = useState<Record<string, string>>({});
  const [structure, setStructure] = useState<PlanningStructure | null>(null);
  const [draft, setDraft] = useState<DraftDetail | null>(null);
  const [delta, setDelta] = useState<RevisionDelta | null>(null);
  const [message, setMessage] = useState("Connect a project to begin.");
  const [busy, setBusy] = useState(false);

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
    const [sourceResponse, releaseResponse, artifactResponse] = await Promise.all([
      fetch(`${API}/api/v1/projects/${active.projectId}/bootstrap/boq-sources`, { headers: headers(undefined, active) }),
      fetch(`${API}/api/v1/projects/${active.projectId}/bootstrap/schedule-releases`, { headers: headers(undefined, active) }),
      fetch(`${API}/api/v1/projects/${active.projectId}/evidence/artifacts`, { headers: headers(undefined, active) }),
    ]);
    if (!sourceResponse.ok) throw new Error(await readError(sourceResponse));
    if (!releaseResponse.ok) throw new Error(await readError(releaseResponse));
    if (!artifactResponse.ok) throw new Error(await readError(artifactResponse));
    setSources(await sourceResponse.json()); setReleases(await releaseResponse.json()); setArtifacts(await artifactResponse.json());
  }
  async function create<T extends { id: string } = { id: string }>(path: string, body: unknown, key: string): Promise<T> {
    const response = await request(path, body, crypto.randomUUID());
    const result = await response.json() as T;
    setLatest((current) => ({ ...current, [key]: result.id }));
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
    const next = { actorId: String(form.get("actorId")), organizationId: String(form.get("organizationId")), projectId: String(form.get("projectId")) };
    setConnection(next); setBusy(true);
    try { await refresh(next); setMessage("Project connected. Start with an evidence artifact created in the Evidence workbench."); } catch (error) { setMessage(error instanceof Error ? error.message : "Connection failed"); } finally { setBusy(false); }
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
  function json(form: FormData, key: string, fallback: unknown) { const raw = String(form.get(key) ?? "").trim(); return raw ? JSON.parse(raw) : fallback; }

  return <div className="workbench-grid bootstrap-grid">
    <Step number="01" title="Connect project"><form className="stack-form compact" onSubmit={connect}><label>Actor ID<input name="actorId" defaultValue="local-admin" required /></label><label>Organization UUID<input name="organizationId" required /></label><label>Project UUID<input name="projectId" required /></label><button disabled={busy}>Connect</button></form></Step>
    <Step number="02" title="Preserve BOQ source"><p>XLSX/XLSM files can continue through extraction. PDF is preserved with verification required until a governed text/OCR adapter is available.</p><form className="stack-form compact" onSubmit={(event) => void uploadAndRegister(event)}><label>BOQ Excel or PDF<input name="file" type="file" accept=".xlsx,.xlsm,.pdf" required /></label><label>Source reference<input name="sourceId" placeholder="Contract BOQ revision 1" required /></label><label>Prior BOQ version (revision only)<select name="priorId"><option value="">Initial version</option>{sources.map((item) => <option key={item.id} value={item.id}>BOQ v{item.version_number} · {item.id}</option>)}</select></label><button disabled={!connection || busy}>Upload and preserve</button></form><p>Existing evidence artifact? Refresh and register it below.</p><button type="button" disabled={!connection || busy} onClick={() => void run("Artifacts refreshed.", () => refresh())}>Refresh artifacts</button><form className="stack-form compact" onSubmit={(event) => { const form = values(event); void run("BOQ source preserved.", async () => { await create("/boq-sources", { artifact_id: form.get("artifactId"), prior_source_version_id: form.get("priorId") || null }, "source"); await refresh(); }); }}><label>Evidence artifact<select name="artifactId" required><option value="">Select BOQ artifact</option>{artifacts.map((item) => <option key={item.id} value={item.id}>{item.original_filename} · {item.id}</option>)}</select></label><label>Prior source UUID (revision only)<input name="priorId" /></label><button disabled={!connection || busy}>Register existing artifact</button></form></Step>
    <Step number="03" title="Normalize and classify"><IdForm label="Source UUID" suggested={latest.source} button="Normalize" disabled={!connection || busy} onSubmit={(form) => run("BOQ normalized and classified.", async () => { await create(`/boq-sources/${form.get("id")}/normalizations`, {}, "normalization"); })} /></Step>
    <Step number="04" title="Propose WBS and packages"><IdForm label="Source UUID" suggested={latest.source} button="Generate structure" disabled={!connection || busy} onSubmit={(form) => run("Planning structure proposed.", async () => { const result = await create<PlanningStructure>(`/boq-sources/${form.get("id")}/planning-structures`, {}, "structure"); setStructure(result); })} />{structure && <div className="mini-ledger"><strong>{structure.work_packages.length} proposed packages</strong>{structure.work_packages.map((item) => <div key={item.id}>{item.name} · {item.classification}<small>{item.id}</small></div>)}<p>{structure.unmapped_lines.length} unmapped lines · {structure.assumptions.length} assumptions</p></div>}</Step>
    <Step number="05" title="Planner structure review"><form className="stack-form compact" onSubmit={(event) => { const form = values(event); void run("Structure review recorded.", async () => { await create(`/planning-structures/${form.get("id")}/revisions`, { action: "ACCEPT_PROPOSAL", reason: form.get("reason") }, "reviewedStructure"); }); }}><label>Structure UUID<input name="id" defaultValue={latest.structure} key={latest.structure} required /></label><label>Review reason<input name="reason" minLength={10} required /></label><button disabled={!connection || busy}>Accept proposal</button></form></Step>
    <Step number="06" title="Generate activities and durations"><JsonAction idLabel="Reviewed structure UUID" suggested={latest.reviewedStructure} placeholder='{"validation_owner":"planner@example.com","duration_inputs":[],"productivity_inputs":[]}' button="Generate draft" disabled={!connection || busy} onSubmit={(id, body) => run("Activity draft generated.", async () => { const result = await create(`/planning-structures/${id}/schedule-drafts`, body, "draft"); const detail = await request(`/schedule-drafts/${result.id}`); setDraft(await detail.json()); })} />{draft && <div className="mini-ledger"><strong>{draft.activities.length} proposed activities</strong>{draft.activities.map((item) => <div key={item.id}>{item.activity_code} · {item.activity_name} · {item.duration_working_days ?? "duration unresolved"}<small>{item.id} · {item.activity_type} · package {item.work_package_id} · {item.boq_line_refs.length} BOQ lines</small></div>)}<p>{draft.assumptions.length} assumptions need review</p></div>}</Step>
    <Step number="07" title="Propose logic and calendar"><JsonAction idLabel="Draft generation UUID" suggested={latest.draft} placeholder='{"validation_owner":"planner@example.com","calendar":{"calendar_id":"PROJECT","name":"Project calendar","working_weekdays":[0,1,2,3,4,5],"working_hours_per_day":8,"holidays":[],"review_state":"ACCEPTED"},"dependencies":[],"milestones":[],"constraints":[],"sequence_templates":[]}' button="Create logic" disabled={!connection || busy} onSubmit={(id, body) => run("Schedule logic proposed.", async () => { await create(`/schedule-drafts/${id}/logic`, body, "logic"); })} /></Step>
    <Step number="08" title="Calculate CPM"><form className="stack-form compact" onSubmit={(event) => { const form = values(event); void run("Deterministic CPM completed.", async () => { const result = await create(`/schedule-drafts/${form.get("id")}/calculations`, { project_start: form.get("start") }, "calculation"); setCalculation(result as Calculation); }); }}><label>Draft generation UUID<input name="id" defaultValue={latest.draft} key={latest.draft} required /></label><label>Project start<input name="start" type="date" required /></label><button disabled={!connection || busy}>Calculate and validate</button></form></Step>
    <Step number="09" title="Resolve validation"><p><strong>{calculation?.readiness ?? "No calculation loaded"}</strong>{calculation?.proposed_finish ? ` · proposed finish ${calculation.proposed_finish}` : ""}</p><div className="mini-ledger">{calculation?.validation_findings.map((item, index) => <div key={`${item.code}-${index}`}><strong>{item.severity} · {item.code}</strong><span>{item.message}</span></div>)}</div>{calculation?.readiness === "VALIDATION_BLOCKED" && <div><p>Correct the inputs in a new immutable reviewed version, then regenerate activities and logic and recalculate. The blocked version remains in history.</p><button type="button" disabled={busy || !latest.reviewedStructure} onClick={() => void run("New reviewed structure version created. Return to step 6 with corrected inputs.", async () => { await create(`/planning-structures/${latest.reviewedStructure}/revisions`, { action: "ACCEPT_PROPOSAL", reason: "Supersede blocked schedule calculation with corrected planning inputs." }, "reviewedStructure"); setCalculation(null); })}>Create corrected version</button></div>}</Step>
    <Step number="10" title="Planner schedule review"><p>Confirm dates, logic, and traceability before submitting. Material duration or logic corrections require a new reviewed draft and CPM calculation.</p><form className="stack-form compact" onSubmit={(event) => { const form = values(event); void run("Planner review stored; PM approval required.", async () => { const edits = json(form, "edits", []) as Record<string, unknown>[]; const code = String(form.get("activityCode") ?? ""); const selected = draft?.activities.find((item) => item.activity_code === code); const revisedName = String(form.get("revisedName") ?? "").trim(); const revisedOwner = String(form.get("revisedOwner") ?? "").trim(); const editReason = String(form.get("editReason") ?? "").trim(); if (selected && (revisedName || revisedOwner) && editReason.length < 10) throw new Error("Explain each planner edit in at least ten characters."); if (selected && revisedName && revisedName !== selected.activity_name) edits.push({ field_path: `activities.${code}.name`, original_value: selected.activity_name, revised_value: revisedName, reason: editReason }); if (selected && revisedOwner && revisedOwner !== (selected.responsible_role || "PROJECT_DELIVERY_MANAGER")) edits.push({ field_path: `activities.${code}.responsible_owner`, original_value: selected.responsible_role || "PROJECT_DELIVERY_MANAGER", revised_value: revisedOwner, reason: editReason }); await create(`/schedule-calculations/${form.get("id")}/reviews`, { reason: form.get("reason"), edits }, "reviewedRelease"); await refresh(); }); }}><label>Calculation UUID<input name="id" defaultValue={calculation?.id} key={calculation?.id} required /></label><label>Review reason<input name="reason" minLength={10} required /></label><label>Activity to rename or reassign<select name="activityCode"><option value="">No field edit</option>{draft?.activities.map((item) => <option key={item.id} value={item.activity_code}>{item.activity_code} · {item.activity_name}</option>)}</select></label><label>Revised activity name<input name="revisedName" /></label><label>Revised owner<input name="revisedOwner" /></label><label>Reason for field edit<input name="editReason" /></label><label>Advanced edits JSON<textarea name="edits" defaultValue="[]" /></label><button disabled={!connection || busy || calculation?.readiness !== "PLANNER_REVIEW_REQUIRED"}>Submit for approval</button></form></Step>
    <Step number="11" title="Human authorization"><p>A project admin must create the exact active grant separately. A planner review does not grant approval authority.</p><form className="stack-form compact" onSubmit={(event) => { const form = values(event); void run("Project-scoped schedule authority grant created.", async () => { if (!connection) throw new Error("Connect a project first."); const response = await fetch(`${API}/api/v1/projects/${connection.projectId}/authority-grants`, { method: "POST", headers: headers(), body: JSON.stringify({ actor_id: form.get("grantee") || connection.actorId, authority_type: form.get("authorityType"), valid_from: form.get("validFrom") || null, valid_until: form.get("validUntil") || null }) }); if (!response.ok) throw new Error(await readError(response)); const grant = await response.json() as { id: string }; setLatest((current) => ({ ...current, grant: grant.id })); }); }}><label>Authorized human actor ID<input name="grantee" defaultValue={connection?.actorId} key={connection?.actorId} required /></label><label>Grant type<select name="authorityType"><option value="CURRENT_SCHEDULE_APPROVAL">Current schedule approval</option><option value="BASELINE_SCHEDULE_APPROVAL">Baseline schedule approval</option></select></label><label>Valid from<input name="validFrom" type="date" required /></label><label>Valid until (optional)<input name="validUntil" type="date" /></label><button disabled={!connection || busy}>Create exact authority grant</button></form><form className="stack-form compact" onSubmit={(event) => { const form = values(event); void run("Schedule authorized through exact human grant.", async () => { await create(`/schedule-releases/${form.get("releaseId")}/approve`, { authority_grant_id: form.get("grantId"), approval_reference: form.get("reference"), reason: form.get("reason"), authorize_as_baseline: form.get("baseline") === "on" }, "authorizedRelease"); await refresh(); }); }}><label>Reviewed release UUID<input name="releaseId" defaultValue={latest.reviewedRelease} key={latest.reviewedRelease} required /></label><label>Authority grant UUID<input name="grantId" defaultValue={latest.grant} key={latest.grant} required /></label><label>Approval reference<input name="reference" required /></label><label>Reason<input name="reason" minLength={10} required /></label><label><input name="baseline" type="checkbox" /> Baseline authorization</label><button disabled={!connection || busy}>Authorize schedule</button></form></Step>
    <Step number="12" title="Publish, export, and revisions"><div className="mini-ledger">{sources.map((item) => <div key={item.id}><strong>BOQ v{item.version_number} · {item.extraction_status}</strong><small>{item.id}</small></div>)}{releases.map((item) => <div key={item.id}><strong>Schedule v{item.version_number} · {item.state}</strong><span>{["json", "csv", "xlsx"].map((format) => <button type="button" key={format} disabled={busy} onClick={() => void download(item.id, format)}>{format.toUpperCase()}</button>)}</span><small>{item.id}</small></div>)}</div><IdForm label="New BOQ source UUID" suggested={latest.source} button="Create revision delta" disabled={!connection || busy} onSubmit={(form) => run("Revision delta created; authorized schedule unchanged.", async () => { const result = await create<RevisionDelta & { id: string }>(`/boq-sources/${form.get("id")}/revision-delta`, {}, "revisionDelta"); setDelta(result); })} />{delta && <div className="mini-ledger"><strong>Revision comparison · authorized schedule unchanged</strong><p>{delta.added_scope.length} added · {delta.removed_scope.length} removed · {delta.changed_scope.length} changed scope</p><p>{delta.mapping_changes.length} mapping changes · {delta.activity_changes.length} activity changes</p><p>Schedule effect: {String(delta.schedule_effects.status)}</p></div>}</Step>
    <p className="workbench-message full-width" role="status">{busy ? "Working…" : message}</p>
  </div>;
}

function Step({ number, title, children }: { number: string; title: string; children: React.ReactNode }) { return <section className="workbench-card"><span className="step-number">{number}</span><h2>{title}</h2>{children}</section>; }
function IdForm({ label, suggested, button, disabled, onSubmit }: { label: string; suggested?: string; button: string; disabled: boolean; onSubmit: (form: FormData) => Promise<void> }) { return <form className="stack-form compact" onSubmit={(event) => { event.preventDefault(); void onSubmit(new FormData(event.currentTarget)); }}><label>{label}<input name="id" defaultValue={suggested} key={suggested} required /></label><button disabled={disabled}>{button}</button></form>; }
function JsonAction({ idLabel, suggested, placeholder, button, disabled, onSubmit }: { idLabel: string; suggested?: string; placeholder: string; button: string; disabled: boolean; onSubmit: (id: string, body: unknown) => Promise<void> }) { const [error, setError] = useState(""); return <form className="stack-form compact" onSubmit={(event) => { event.preventDefault(); const form = new FormData(event.currentTarget); try { const body = JSON.parse(String(form.get("json"))); setError(""); void onSubmit(String(form.get("id")), body); } catch { setError("Inputs must be valid JSON."); } }}><label>{idLabel}<input name="id" defaultValue={suggested} key={suggested} required /></label><label>Governed inputs JSON<textarea name="json" defaultValue={placeholder} required /></label><button disabled={disabled}>{button}</button>{error && <p role="alert">{error}</p>}</form>; }
async function readError(response: Response) { const payload = await response.json().catch(() => null) as { detail?: string | { msg?: string }[] } | null; return typeof payload?.detail === "string" ? payload.detail : Array.isArray(payload?.detail) ? payload.detail.map((item) => item.msg).join("; ") : `Request failed (${response.status})`; }
