"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { ProjectContextFields } from "../project-context-fields";

const API = process.env.NEXT_PUBLIC_VAI_API_URL ?? "http://localhost:8000";

export async function downloadProgressTemplate(
  schedule: Blob,
  connection: { actorId: string; organizationId: string; projectId: string },
  asOf: string,
  sample = false,
) {
  const data = new FormData();
  data.set("schedule", schedule, "source-schedule.xlsx");
  data.set("as_of", asOf);
  data.set("sample", String(sample));
  const response = await fetch(`${API}/api/v1/projects/${connection.projectId}/progress/template`, {
    method: "POST", body: data,
    headers: { "X-VAI-Actor-ID": connection.actorId, "X-VAI-Organization-ID": connection.organizationId },
  });
  if (!response.ok) {
    const error = await response.json().catch(() => null) as { detail?: unknown } | null;
    throw new Error(typeof error?.detail === "string" ? error.detail : "Unable to prepare the progress template.");
  }
  const url = URL.createObjectURL(await response.blob());
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = sample ? "fictional-progress-example.xlsx" : "project-progress-template.xlsx";
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function ProgressTemplate() {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [connection, setConnection] = useState<{ actorId: string; organizationId: string; projectId: string } | null>(null);
  const [sources, setSources] = useState<{ projectId: string; items: { id: string; original_filename: string; received_at: string }[]; error?: string } | null>(null);
  const ready = sources?.projectId === connection?.projectId && !!connection;
  useEffect(() => {
    if (!connection) return;
    const controller = new AbortController();
    const active = connection;
    void fetch(`${API}/api/v1/projects/${active.projectId}/evidence/artifacts`, {
      signal: controller.signal,
      headers: { "X-VAI-Actor-ID": active.actorId, "X-VAI-Organization-ID": active.organizationId },
    }).then(async response => {
      if (!response.ok) throw new Error("Saved schedules could not be loaded.");
      const items = await response.json() as { id: string; original_filename: string; received_at: string; source_type: string; scan_result: string }[];
      if (!controller.signal.aborted) setSources({ projectId: active.projectId, items: items.filter(item => item.source_type === "AI_SCHEDULE_EXPORT" && item.original_filename.toLowerCase().endsWith(".xlsx") && item.scan_result === "CLEAN").sort((a, b) => b.received_at.localeCompare(a.received_at) || b.id.localeCompare(a.id)) });
    }).catch(error => { if (!controller.signal.aborted) setSources({ projectId: active.projectId, items: [], error: error instanceof Error ? error.message : "Saved schedules could not be loaded." }); });
    return () => controller.abort();
  }, [connection]);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    if (!connection || !ready || !sources?.items.length) return;
    if (String(form.get("projectId")) !== connection.projectId) return;
    setBusy(true); setMessage("");
    try {
      const sample = form.get("mode") === "sample";
      const artifactId = String(form.get("savedSchedule"));
      const response = await fetch(`${API}/api/v1/projects/${connection.projectId}/evidence/artifacts/${artifactId}/content`, { headers: { "X-VAI-Actor-ID": connection.actorId, "X-VAI-Organization-ID": connection.organizationId } });
      if (!response.ok) throw new Error("The saved schedule could not be opened. Reload the page and try again.");
      await downloadProgressTemplate(await response.blob(), connection, String(form.get("templateAsOf")), sample);
      setMessage(sample ? "Fictional example downloaded. Use the selected cut-off to preview it; examples cannot be saved as governed progress." : "Template downloaded. Fill in the yellow cells on Progress Report, save, then upload it in the preview below using the same cut-off.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to download template.");
    } finally { setBusy(false); }
  }
  return <section className="workbench-card full-width" aria-labelledby="progress-template-title">
    <span className="eyebrow">Ready to use · From your saved project schedule</span>
    <h2 id="progress-template-title">Download your progress template</h2>
    <p className="card-copy">Your template is ready from the BOQ schedule already saved in this project. Download it, fill in the yellow progress cells, then upload the completed workbook below to see how the work compares with the plan.</p>
    <form className="stack-form" onSubmit={submit}>
      <fieldset disabled={busy} className="progress-template-fields">
        <ProjectContextFields projectLabel="Template project" onConnectionChange={setConnection} />
        {ready && sources?.items.length ? <label key={sources.projectId}>Saved project schedule<select name="savedSchedule" defaultValue={sources.items[0].id}>{sources.items.map((item, index) => <option key={item.id} value={item.id}>{item.original_filename}{index === 0 ? " · latest" : ""}</option>)}</select></label> : null}
        <label>Template reporting cut-off<input name="templateAsOf" type="date" defaultValue={new Date().toLocaleDateString("en-CA")} required /></label>
        <label>Template contents<select name="mode" defaultValue="blank"><option value="blank">Blank — enter actual site updates</option><option value="sample">Filled example — fictional progress for testing</option></select></label>
        <button type="submit" disabled={!ready || !sources?.items.length}>{busy ? "Preparing template…" : "Download progress template"}</button>
      </fieldset>
    </form>
    {!ready ? <p className="card-copy">Loading your project’s saved schedule…</p> : sources?.error ? <p role="alert">{sources.error}</p> : !sources?.items.length ? <p className="card-copy">This project has no saved BOQ schedule yet. <Link href="/bootstrap">Generate the project schedule</Link> to make its progress template available here automatically.</p> : null}
    {message ? <p role="status">{message}</p> : null}
    <p className="card-copy">Compare in Excel or upload below. Days ahead/behind are calendar-day approximations; confirming project completion impact requires the reviewed schedule network and evidence.</p>
  </section>;
}
