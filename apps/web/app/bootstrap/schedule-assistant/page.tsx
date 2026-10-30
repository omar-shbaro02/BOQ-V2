"use client";

import Link from "next/link";
import { type FormEvent, useState } from "react";

const API = process.env.NEXT_PUBLIC_VAI_API_URL ?? "http://localhost:8000";

export default function ScheduleAssistantPage() {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [filename, setFilename] = useState("");
  const [request, setRequest] = useState("");
  const [result, setResult] = useState<Blob | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const body = new FormData(event.currentTarget);
    setBusy(true); setError(""); setMessage("");
    setResult(null);
    try {
      const response = await fetch(`${API}/api/v1/ms-project/revise-with-ai`, { method: "POST", body });
      if (!response.ok) throw new Error(await readError(response));
      const packageFile = await response.blob();
      setResult(packageFile);
      download(packageFile, "proposed_schedule_change.zip");
      setMessage("Your proposal package is ready. Read the Word report, then import the XLSX into Microsoft Project and recalculate before seeking approval.");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Schedule revision failed"); }
    finally { setBusy(false); }
  }

  return <main className="workbench-shell schedule-change-page">
    <header className="sc-heading"><span className="eyebrow">Schedule planning assistant</span><h1>Propose a schedule change</h1><p>Upload your current schedule and explain what needs to change. Receive a proposed workbook and a report for your planner to review.</p></header>
    <nav className="sc-navigation" aria-label="BOQ to schedule navigation"><Link href="/bootstrap"><span aria-hidden="true">01</span>Generate schedule</Link><Link href="/bootstrap/advanced"><span aria-hidden="true">02</span>Review & approve</Link><Link href="/bootstrap/schedule-assistant" aria-current="page"><span aria-hidden="true">03</span>Schedule assistant</Link></nav>
    <div className="sc-layout">
      <section className="sc-form-card" aria-labelledby="sc-form-title"><div className="sc-card-heading"><span className="sc-icon" aria-hidden="true">⇄</span><div><span className="eyebrow">Create a proposal</span><h2 id="sc-form-title">What needs to change?</h2></div></div>
        <form onSubmit={submit} aria-busy={busy}>
          <fieldset disabled={busy}>
            <label className="sc-field" htmlFor="sc-file"><span><b className="sc-field-number" aria-hidden="true">1</b>Upload the current schedule <small>Required</small></span></label>
            <div className={`sc-file-box ${filename ? "has-file" : ""}`}><input id="sc-file" name="schedule" type="file" accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" required aria-describedby="sc-file-help" onChange={event => { setFilename(event.currentTarget.files?.[0]?.name ?? ""); setResult(null); setMessage(""); }} /><span className="sc-file-note">{filename ? "Schedule selected · ready for your request" : "Excel workbook (.xlsx)"}</span></div>
            <p id="sc-file-help" className="sc-help">Use the VAI schedule with ID, Name, Duration, Start, Finish and Dependency columns. Task IDs and names stay unchanged.</p>
            <label className="sc-field" htmlFor="sc-request"><span><b className="sc-field-number" aria-hidden="true">2</b>Describe the requested change <small>Required</small></span></label>
            <textarea id="sc-request" name="change_request" minLength={10} maxLength={8000} rows={7} required value={request} onChange={event => { setRequest(event.currentTarget.value); setResult(null); setMessage(""); }} aria-describedby="sc-request-help sc-request-count" placeholder="For example: Propose a completion date three weeks earlier. Keep the existing scope, explain which tasks could overlap, and flag dependencies, assumptions and risks that need review." />
            <div className="sc-input-meta"><p id="sc-request-help" className="sc-help">Include the affected task names or IDs, the delay or target date, and any fixed constraints.</p><small id="sc-request-count">{request.length.toLocaleString()} / 8,000</small></div>
            <div className="sc-submit-row"><button className="primary-action" type="submit">{busy ? "Preparing your proposal…" : "Create schedule proposal"}<span aria-hidden="true">→</span></button><span>Downloads one ZIP package</span></div>
          </fieldset>
        </form>
        {busy ? <p className="sc-feedback" role="status">Preparing the workbook and planner report. Your original schedule is unchanged.</p> : null}
        {error ? <p className="sc-feedback sc-feedback-error" role="alert">{error}</p> : null}
        {message ? <div className="sc-feedback sc-feedback-success"><p role="status">{message}</p>{result ? <button type="button" onClick={() => download(result, "proposed_schedule_change.zip")}>Download proposal again ↓</button> : null}</div> : null}
      </section>
      <aside className="sc-side" aria-label="Proposal contents and review steps"><section className="sc-output-card"><span className="eyebrow">Included in your download</span><h2>Three files. One review package.</h2><div className="sc-deliverables"><Boundary icon="XLSX" title="Proposed schedule" text="MS Project import workbook with the existing task IDs and names." /><Boundary icon="DOCX" title="Planner report" text="Proposed changes, feasibility, assumptions, risks and review actions." /><Boundary icon="JSON" title="Source manifest" text="Structured proposal data and source-workbook traceability." /></div></section><section className="sc-review-card"><h2>Before using the new dates</h2><ol><li>Read the planner report and its limitations.</li><li>Import the XLSX into Microsoft Project and recalculate.</li><li>Review the result and obtain the required human approval.</li></ol><Link href="/bootstrap/advanced">Open review & approval →</Link></section><p className="sc-boundary">This creates a proposal. It does not approve work or change the authorized schedule.</p></aside>
    </div>
  </main>;
}

function Boundary({ icon, title, text }: { icon: string; title: string; text: string }) { return <div><span className="sc-file-type" aria-hidden="true">{icon}</span><div><h3>{title}</h3><p>{text}</p></div></div>; }
async function readError(response: Response) { const body = await response.json().catch(() => null) as { detail?: string | { msg?: string }[] } | null; return typeof body?.detail === "string" ? body.detail : Array.isArray(body?.detail) ? body.detail.map(item => item.msg).filter(Boolean).join("; ") : `Request failed (${response.status})`; }
function download(blob: Blob, filename: string) { const url = URL.createObjectURL(blob); const link = document.createElement("a"); link.href = url; link.download = filename; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); }
