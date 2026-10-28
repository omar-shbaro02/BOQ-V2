"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { currentWorkspace } from "./workspace-session";

const API = process.env.NEXT_PUBLIC_VAI_API_URL ?? "http://localhost:8000";
type Answer = {
  status: string; data_date: string; semantic_notice: string; answer_hash: string;
  facts: { key: string; label: string; value: unknown; unit: string | null; truth_type: string; semantic_state: string | null; source_refs: string[]; limitations: unknown[]; data_date: string }[];
  considerations: { text: string; source_refs: string[]; review_route: { url: string } | null }[];
  limitations: string[];
};

export function SnapshotAssistantPanel({ snapshotId, timezone = "UTC" }: { snapshotId?: string; timezone?: string }) {
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  async function ask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!snapshotId) return;
    const form = new FormData(event.currentTarget);
    if (!String(form.get("question") ?? "").trim() && !form.get("topic")) {
      setMessage("Enter a status question or choose a topic.");
      return;
    }
    const projectId = localStorage.getItem("vai-active-project");
    if (!projectId) { setMessage("Choose a project first."); return; }
    setBusy(true);
    setMessage("");
    setAnswer(null);
    try {
      const workspace = await currentWorkspace();
      if (!workspace) throw new Error("Choose a project first.");
      const topic = String(form.get("topic"));
      const response = await fetch(`${API}/api/v1/projects/${projectId}/project-control/snapshots/${snapshotId}/assistant`, {
        method: "POST", headers: { "Content-Type": "application/json", "X-VAI-Actor-ID": workspace.actorId, "X-VAI-Organization-ID": workspace.organizationId },
        body: JSON.stringify({ question: form.get("question"), topic: topic || null }),
      });
      if (!response.ok) throw new Error(`Unable to read the selected snapshot (${response.status}).`);
      setAnswer(await response.json() as Answer);
    } catch (error) { setMessage(error instanceof Error ? error.message : "Unable to read this snapshot."); }
    finally { setBusy(false); }
  }

  return <section className="dashboard-card" aria-labelledby="snapshot-assistant-title">
    <details>
      <summary id="snapshot-assistant-title">Ask this snapshot</summary>
      <p>Read completion, schedule, cost, forecast, health, risks, evidence, and review deadlines from this frozen snapshot. Answers do not change project records or grant authority.</p>
      <form className="stack-form" onSubmit={ask}>
        <label>Status question<input name="question" placeholder="Where does the project stand?" maxLength={2000} /></label>
        <label>Topic<select name="topic" defaultValue=""><option value="">Match the question</option>{["OVERVIEW", "COMPLETION", "SCHEDULE", "COST", "FORECAST", "RAG", "RISKS", "EVIDENCE", "NEXT_REVIEW"].map((topic) => <option key={topic} value={topic}>{topic.replaceAll("_", " ")}</option>)}</select></label>
        <button disabled={busy || !snapshotId}>{busy ? "Reading snapshot…" : "Read snapshot answer"}</button>
      </form>
      {!snapshotId ? <p className="empty-state">An immutable project-control snapshot is required.</p> : null}
      {message ? <p role="status">{message}</p> : null}
      {answer ? <div aria-label="Snapshot answer">
        <p><strong>{answer.status.replaceAll("_", " ")}</strong> · data date {new Date(answer.data_date).toLocaleString(undefined, { timeZone: timezone })} {timezone}</p>
        <p>{answer.semantic_notice}</p>
        {answer.facts.map((fact) => <article className="mini-ledger" key={fact.key}>
          <strong>{fact.label}</strong><p>{displayValue(fact.value)} {fact.unit ?? ""}</p>
          <small>{fact.semantic_state ?? (fact.truth_type === "DERIVED_METRIC" ? "DERIVED ANALYSIS" : "UNKNOWN STATE")} · {fact.truth_type} · source data date {new Date(fact.data_date).toLocaleString(undefined, { timeZone: timezone })} {timezone}</small>
          <details><summary>Sources and limitations</summary><p>{fact.source_refs.join(", ")}</p>{fact.limitations.map((limitation, index) => <p key={index}>{displayValue(limitation)}</p>)}</details>
        </article>)}
        {answer.considerations.length ? <h3>Management considerations for human review</h3> : null}
        {answer.considerations.map((item, index) => <p key={index}>{item.text} {item.review_route ? <Link href={item.review_route.url}>Open review route →</Link> : null}</p>)}
        {answer.limitations.map((limitation) => <p className="panel-note" key={limitation}>{limitation}</p>)}
      </div> : null}
    </details>
  </section>;
}

function displayValue(value: unknown): string {
  if (value === null || value === undefined) return "Unknown";
  return typeof value === "object" ? JSON.stringify(value) : String(value);
}
