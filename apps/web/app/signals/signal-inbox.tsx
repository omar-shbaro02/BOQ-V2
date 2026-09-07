"use client";

import { FormEvent, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_VAI_API_URL ?? "http://localhost:8000";

type Connection = { actorId: string; organizationId: string; projectId: string };
type Signal = {
  id: string;
  signal_type: string;
  status: string;
  title: string;
  summary: string;
  source_field: string;
  source_evidence_ids: string[];
  source_contradiction_id: string | null;
  materiality_candidate: string;
  occurrence_count: number;
  workflow_version: number;
  expires_at: string;
};
type Suggestion = {
  id: string;
  suggested_outcome: string;
  target_case_id: string | null;
  child_case_ids: string[];
  confidence: string;
  rationale: string;
};

export function SignalInbox() {
  const [connection, setConnection] = useState<Connection | null>(null);
  const [signals, setSignals] = useState<Signal[]>([]);
  const [suggestions, setSuggestions] = useState<Record<string, Suggestion>>({});
  const [filter, setFilter] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function requestHeaders(active = connection, json = true): HeadersInit {
    if (!active) return {};
    return {
      ...(json ? { "Content-Type": "application/json" } : {}),
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
    await refresh(next);
  }

  async function refresh(active = connection) {
    if (!active) return;
    setBusy(true);
    setMessage(null);
    try {
      const query = filter ? `?signal_status=${filter}` : "";
      const response = await fetch(
        `${API_URL}/api/v1/projects/${active.projectId}/signals${query}`,
        { headers: requestHeaders(active, false) },
      );
      if (!response.ok) throw new Error(await readError(response));
      setSignals((await response.json()) as Signal[]);
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : "Signal refresh failed");
    } finally {
      setBusy(false);
    }
  }

  async function runDetection() {
    if (!connection) return;
    await command(
      `${API_URL}/api/v1/projects/${connection.projectId}/signals/detect`,
      { evidence_item_ids: [], contradiction_ids: [] },
      { "Idempotency-Key": `inbox-${crypto.randomUUID()}` },
      "Detectors completed. Candidate signals were deduplicated by project fingerprint.",
    );
  }

  async function screen(signal: Signal, outcome: "RELEVANT" | "DEFER" | "DISMISS") {
    const reason = {
      RELEVANT: "MATERIAL_THRESHOLD_CROSSED",
      DEFER: "AWAITING_EVIDENCE",
      DISMISS: "BELOW_THRESHOLD",
    }[outcome];
    await command(
      `${API_URL}/api/v1/projects/${connection?.projectId}/signals/${signal.id}/screen`,
      {
        expected_version: signal.workflow_version,
        outcome,
        reason_code: reason,
        rationale: `${outcome} recorded by Signal Inbox reviewer`,
        materiality_candidate: signal.materiality_candidate,
        ...(outcome === "DEFER"
          ? { defer_until: twoDaysFromNow() }
          : {}),
      },
      {},
      `Signal ${outcome.toLowerCase()} decision recorded.`,
    );
  }

  async function suggest(signal: Signal) {
    if (!connection) return;
    setBusy(true);
    setMessage(null);
    try {
      const response = await fetch(
        `${API_URL}/api/v1/projects/${connection.projectId}/signals/${signal.id}/correlation-suggestion`,
        { method: "POST", headers: requestHeaders() },
      );
      if (!response.ok) throw new Error(await readError(response));
      const suggestion = (await response.json()) as Suggestion;
      setSuggestions((current) => ({ ...current, [signal.id]: suggestion }));
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : "Correlation suggestion failed");
    } finally {
      setBusy(false);
    }
  }

  async function accept(signal: Signal, suggestion: Suggestion) {
    const opensCase = suggestion.suggested_outcome !== "LINK_EXISTING";
    await command(
      `${API_URL}/api/v1/projects/${connection?.projectId}/correlation-suggestions/${suggestion.id}/review`,
      {
        expected_signal_version: signal.workflow_version,
        status: "ACCEPTED",
        selected_outcome: suggestion.suggested_outcome,
        target_case_id: suggestion.target_case_id,
        child_case_ids: suggestion.child_case_ids,
        ...(opensCase
          ? { case_title: signal.title, case_owner_actor_id: connection?.actorId }
          : {}),
        rationale: "Reviewer accepted the visible correlation rationale",
      },
      {},
      "Correlation reviewed and accepted; the signal remains distinct from its case.",
    );
  }

  async function reject(signal: Signal, suggestion: Suggestion) {
    await command(
      `${API_URL}/api/v1/projects/${connection?.projectId}/correlation-suggestions/${suggestion.id}/review`,
      {
        expected_signal_version: signal.workflow_version,
        status: "REJECTED",
        rationale: "Reviewer rejected the suggested correlation",
      },
      {},
      "Correlation suggestion rejected; no case was changed.",
    );
  }

  async function command(
    url: string,
    body: object,
    extraHeaders: Record<string, string>,
    success: string,
  ) {
    if (!connection) return;
    setBusy(true);
    setMessage(null);
    try {
      const response = await fetch(url, {
        method: "POST",
        headers: { ...requestHeaders(), ...extraHeaders },
        body: JSON.stringify(body),
      });
      if (!response.ok) throw new Error(await readError(response));
      setMessage(success);
      await refresh();
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : "Signal command failed");
      setBusy(false);
    }
  }

  return (
    <div className="workbench-grid">
      <section className="workbench-card full-width">
        <div className="card-heading">
          <div><span className="step-number">01</span><h2>Connect and detect</h2></div>
          <span className={connection ? "connection active" : "connection"}>{connection ? "Connected" : "Required"}</span>
        </div>
        <form className="inline-form signal-connect" onSubmit={connect}>
          <label>Actor ID<input name="actorId" defaultValue="local-admin" required /></label>
          <label>Organization UUID<input name="organizationId" required /></label>
          <label>Project UUID<input name="projectId" required /></label>
          <button>Connect</button>
          <button type="button" className="secondary" disabled={!connection || busy} onClick={runDetection}>Run detectors</button>
        </form>
      </section>
      <section className="workbench-card full-width">
        <div className="inbox-toolbar">
          <div><span className="step-number">02</span><h2>Screen candidates</h2></div>
          <div className="filter-controls">
            <label>Status<select value={filter} onChange={(event) => setFilter(event.target.value)}><option value="">All</option><option>CANDIDATE</option><option>SCREENED</option><option>DEFERRED</option><option>DISMISSED</option><option>CORRELATED</option><option>EXPIRED</option></select></label>
            <button className="verify-button" disabled={!connection || busy} onClick={() => refresh()}>Apply</button>
          </div>
        </div>
        <div className="signal-list">
          {signals.map((signal) => {
            const suggestion = suggestions[signal.id];
            return <article className="signal-card" key={signal.id}>
              <div className="signal-main">
                <div className="signal-meta"><span className={`truth ${signal.status === "SCREENED" ? "verified" : ""}`}>{signal.status}</span><span>{signal.signal_type.replaceAll("_", " ")}</span><span>{signal.materiality_candidate}</span></div>
                <h3>{signal.title}</h3><p>{signal.summary}</p>
                <small>Source: {signal.source_field} · {signal.source_evidence_ids[0] ?? signal.source_contradiction_id} · expires {new Date(signal.expires_at).toLocaleString()}</small>
              </div>
              <div className="signal-actions">
                {signal.status === "CANDIDATE" || signal.status === "DEFERRED" ? <><button onClick={() => screen(signal, "RELEVANT")}>Relevant</button><button className="secondary" onClick={() => screen(signal, "DEFER")}>Defer</button><button className="secondary danger" onClick={() => screen(signal, "DISMISS")}>Dismiss</button></> : null}
                {signal.status === "SCREENED" && !suggestion ? <button onClick={() => suggest(signal)}>Suggest correlation</button> : null}
              </div>
              {suggestion ? <div className="correlation-box"><strong>{suggestion.suggested_outcome.replaceAll("_", " ")} · {suggestion.confidence}</strong><p>{suggestion.rationale}</p><small>{suggestion.target_case_id ? `Target ${suggestion.target_case_id}` : suggestion.child_case_ids.length ? `${suggestion.child_case_ids.length} possible child cases` : "New independent case"}</small><div className="signal-actions"><button onClick={() => accept(signal, suggestion)}>Accept</button><button className="secondary danger" onClick={() => reject(signal, suggestion)}>Reject</button></div></div> : null}
            </article>;
          })}
          {!signals.length ? <p className="empty-state">No signals in this view. Connect, run the deterministic detectors, then refresh.</p> : null}
        </div>
      </section>
      {message ? <p className="workbench-message full-width" role="status">{message}</p> : null}
    </div>
  );
}

async function readError(response: Response): Promise<string> {
  const payload = (await response.json().catch(() => null)) as { detail?: string | { msg?: string }[] } | null;
  if (typeof payload?.detail === "string") return payload.detail;
  if (Array.isArray(payload?.detail)) return payload.detail.map((entry) => entry.msg).join("; ");
  return `Request failed with status ${response.status}`;
}

function twoDaysFromNow(): string {
  return new Date(Date.now() + 2 * 86_400_000).toISOString();
}
