"use client";

import { useState } from "react";

const API = process.env.NEXT_PUBLIC_VAI_API_URL ?? "http://localhost:8000";
type Connection = { actorId: string; organizationId: string; projectId: string };
type Recipient = { id: string; record_type: string; status: string; payload: { name?: string; report_recipient?: boolean } };
type Report = { id: string; report_number: number; lifecycle_status: string; payload: { project_control: { supporting_context: { project_context: Recipient[] } } } };
type Deck = { id: string; report_snapshot_id: string; lifecycle_status: string; content_hash: string; lifecycle_events: unknown[] };
type Snapshot = { id: string; snapshot_number: number; data_date: string };
type Grant = { id: string; actor_id: string; active: boolean; authority_type: string; controlled_object_id: string | null; max_amount: string | null };

export function ReportPresentations({ connection }: { connection: Connection }) {
  const [reports, setReports] = useState<Report[]>([]);
  const [decks, setDecks] = useState<Deck[]>([]);
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [grants, setGrants] = useState<Grant[]>([]);
  const [snapshotId, setSnapshotId] = useState("");
  const [reportId, setReportId] = useState("");
  const [recipients, setRecipients] = useState<string[]>([]);
  const [grantId, setGrantId] = useState("");
  const [reason, setReason] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const root = `${API}/api/v1/projects/${connection.projectId}`;
  const headers = { "X-VAI-Actor-ID": connection.actorId, "X-VAI-Organization-ID": connection.organizationId };
  const selectedReport = reports.find((item) => item.id === reportId);
  const registry = selectedReport?.payload.project_control.supporting_context?.project_context.filter((item) => item.record_type === "STAKEHOLDER" && item.status === "ACTIVE" && item.payload.report_recipient) ?? [];
  async function request(path: string, data?: object) {
    const response = await fetch(`${root}${path}`, { method: data ? "POST" : "GET", headers: { ...headers, ...(data ? { "Content-Type": "application/json", "Idempotency-Key": crypto.randomUUID() } : {}) }, body: data ? JSON.stringify(data) : undefined });
    if (!response.ok) { const error = await response.json().catch(() => null); throw new Error(typeof error?.detail === "string" ? error.detail : `Request failed (${response.status})`); }
    return response;
  }
  async function refresh() {
    const values = await Promise.all([request("/decision-center/report-snapshots"), request("/decision-center/presentations"), request("/project-control/snapshots"), request("/authority-grants")]);
    setReports(await values[0].json()); setDecks(await values[1].json()); setSnapshots(await values[2].json()); setGrants(await values[3].json());
  }
  async function act(work: () => Promise<void>) {
    setBusy(true); setMessage("");
    try { await work(); await refresh(); setMessage("History refreshed. Review and approval remain separate human actions."); }
    catch (error) { setMessage(error instanceof Error ? error.message : "Unable to update history"); }
    finally { setBusy(false); }
  }
  async function transition(kind: "report-snapshots" | "presentations", id: string, status: string, version?: number) {
    await request(`/decision-center/${kind}/${id}/lifecycle-events`, { to_status: status, reason, authority_grant_id: status === "APPROVED" ? grantId || null : null, ...(version ? { expected_version: version } : {}) });
  }
  async function download(deck: Deck, approved: boolean) {
    const response = await request(`/decision-center/${approved ? "approved-presentations" : "presentations"}/${deck.id}/content`);
    const url = URL.createObjectURL(await response.blob()); const link = document.createElement("a"); link.href = url; link.download = `presentation-${deck.id}.html`; link.click(); URL.revokeObjectURL(url);
  }
  return <section className="workbench-card full-width report-history"><details><summary>Report and presentation history</summary>
    <p>Freeze a report from one control snapshot, review it, and approve it before generating a stakeholder deck. The self-contained HTML slides include the full source and print in the browser.</p>
    <button disabled={busy} onClick={() => void act(refresh)}>Load report history</button>
    <div className="stack-form context-form">
      <label>Report source snapshot<select value={snapshotId} onChange={(event) => setSnapshotId(event.target.value)}><option value="">Choose snapshot</option>{snapshots.map((item) => <option key={item.id} value={item.id}>Snapshot {item.snapshot_number} · {item.data_date}</option>)}</select></label>
      <button disabled={busy || !snapshotId} onClick={() => void act(async () => { await request("/decision-center/report-snapshots", { report_type: "ON_DEMAND_STATUS_REPORT", project_control_snapshot_id: snapshotId }); })}>Freeze status report</button>
      <label>Human review or approval reason<input value={reason} onChange={(event) => setReason(event.target.value)} /></label>
      <label>My report approval grant<select value={grantId} onChange={(event) => setGrantId(event.target.value)}><option value="">Choose active authority</option>{grants.filter((item) => item.active && item.actor_id === connection.actorId && item.authority_type === "REPORT_APPROVAL" && !item.controlled_object_id && !item.max_amount).map((item) => <option key={item.id} value={item.id}>{item.id}</option>)}</select></label>
    </div>
    <ul>{reports.map((item) => <li key={item.id}>Report {item.report_number} · {item.lifecycle_status} {item.lifecycle_status === "DRAFT" ? <button disabled={busy || reason.length < 3} onClick={() => void act(() => transition("report-snapshots", item.id, "REVIEWED"))}>Review report {item.report_number}</button> : item.lifecycle_status === "REVIEWED" ? <button disabled={busy || reason.length < 3 || !grantId} onClick={() => void act(() => transition("report-snapshots", item.id, "APPROVED"))}>Approve report {item.report_number}</button> : null}</li>)}</ul>
    <label>Approved presentation source<select value={reportId} onChange={(event) => { setReportId(event.target.value); setRecipients([]); }}><option value="">Choose approved report</option>{reports.filter((item) => item.lifecycle_status === "APPROVED").map((item) => <option key={item.id} value={item.id}>Report {item.report_number}</option>)}</select></label>
    <fieldset><legend>Recipients frozen in source report</legend>{registry.map((item) => <label key={item.id}><input type="checkbox" checked={recipients.includes(item.id)} onChange={(event) => setRecipients(event.target.checked ? [...recipients, item.id] : recipients.filter((id) => id !== item.id))} />{item.payload.name ?? item.id}</label>)}{reportId && !registry.length ? <p>No eligible recipients in this snapshot. Register recipients before freezing a new snapshot.</p> : null}</fieldset>
    <button disabled={busy || !reportId || !recipients.length} onClick={() => void act(async () => { await request("/decision-center/presentations", { report_snapshot_id: reportId, recipient_record_ids: recipients }); })}>Generate stakeholder presentation</button>
    <ul>{decks.map((deck, index) => <li key={deck.id}>Presentation {index + 1} · {deck.lifecycle_status} <small>SHA-256 {deck.content_hash}</small><button disabled={busy} onClick={() => void act(() => download(deck, false))}>Download for review</button>{deck.lifecycle_status === "DRAFT" ? <button disabled={busy || reason.length < 3} onClick={() => void act(() => transition("presentations", deck.id, "REVIEWED", deck.lifecycle_events.length))}>Review presentation</button> : deck.lifecycle_status === "REVIEWED" ? <button disabled={busy || reason.length < 3 || !grantId} onClick={() => void act(() => transition("presentations", deck.id, "APPROVED", deck.lifecycle_events.length))}>Approve presentation</button> : <button disabled={busy} onClick={() => void act(() => download(deck, true))}>Download approved presentation</button>}</li>)}</ul>
    <p className="semantic-note">Generation does not authorize distribution, spend, baseline changes, or execution. Approval requires your matching active authority grant; the API validates its dates and scope.</p>
    <p role="status">{message}</p>
  </details></section>;
}
