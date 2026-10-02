"use client";

import Link from "next/link";
import { type FormEvent, useState } from "react";

const API = process.env.NEXT_PUBLIC_VAI_API_URL ?? "http://localhost:8000";

export default function ScheduleAssistantPage() {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true); setError(""); setMessage("");
    try {
      const response = await fetch(`${API}/api/v1/ms-project/revise-with-ai`, { method: "POST", body: new FormData(event.currentTarget) });
      if (!response.ok) throw new Error(await readError(response));
      download(await response.blob(), "proposed_schedule_change.zip");
      setMessage(`Proposed change package downloaded (${response.headers.get("X-VAI-Model") ?? "configured model"}). Review the report, then import the XLSX into Microsoft Project and recalculate.`);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Schedule revision failed"); }
    finally { setBusy(false); }
  }

  return <main className="workbench-shell project-workspace">
    <header className="workbench-heading"><div><span className="eyebrow">BOQ to schedule · proposal assistant</span><h1 className="workbench-title">Ask for a schedule change.</h1></div><p>Describe a delay, deadline, sequence, or duration change. VAI returns a proposed MS Project import workbook and a concise planner report.</p></header>
    <nav className="workspace-flow" aria-label="BOQ to schedule navigation"><Link href="/bootstrap">Generate schedule</Link><Link href="/bootstrap/advanced">Governed workflow</Link><span className="active">3 <b>Schedule assistant</b></span></nav>
    <div className="workspace-layout">
      <section className="workbench-card workspace-main"><span className="step-number">01</span><h2>Schedule-change chat</h2><p className="panel-note">Use the six-column XLSX VAI generated or exported for MS Project. The assistant preserves task IDs and names, and can propose duration, start/finish, and predecessor changes only.</p>
        <form className="stack-form" onSubmit={submit}>
          <label>Current schedule XLSX<input name="schedule" type="file" accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" required /></label>
          <label>What should change?<textarea name="change_request" minLength={10} maxLength={8000} required placeholder="Example: Keep the scope, but propose a completion date three weeks earlier. Explain feasible parallel work, dependencies that must change, constraints, and risks." /></label>
          <button className="primary-action" disabled={busy}>{busy ? "Preparing proposed schedule…" : "Create proposed schedule and report"}</button>
        </form>
        {error ? <p className="form-message error" role="alert">{error}</p> : null}{message ? <p className="form-message success" role="status">{message}</p> : null}
      </section>
      <aside className="workbench-card workspace-side"><span className="section-kicker">What you receive</span><h2>Actionable, reviewable output</h2><div className="boundary-list"><Boundary icon="1" title="Re-import XLSX" text="Preserved IDs and six MS Project import columns." /><Boundary icon="2" title="Word report" text="Changed tasks, construction strategy, assumptions, risks, and planner actions." /><Boundary icon="3" title="No silent authority" text="A proposal only; Microsoft Project recalculates it and human approval remains separate." /></div><p className="panel-note">The assistant uses construction-planning reasoning, but it does not invent contractual authority, crews, productivity, or entitlement.</p></aside>
    </div>
  </main>;
}

function Boundary({ icon, title, text }: { icon: string; title: string; text: string }) { return <span><i>{icon}</i><b>{title}</b><small>{text}</small></span>; }
async function readError(response: Response) { const body = await response.json().catch(() => null) as { detail?: string } | null; return body?.detail ?? `Request failed (${response.status})`; }
function download(blob: Blob, filename: string) { const url = URL.createObjectURL(blob); const link = document.createElement("a"); link.href = url; link.download = filename; link.click(); URL.revokeObjectURL(url); }
