"use client";

import { FormEvent, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_VAI_API_URL ?? "http://localhost:8000";

type Connection = { actorId: string; organizationId: string; projectId: string };
type Measurement = {
  id: string;
  evidence_item_id: string;
  controlled_object_id: string;
  measurement_kind: string;
  measurement_basis: string;
  numerator: string;
  denominator: string;
  completion_ratio: string;
  semantic_state: string;
  truth_type: string;
  as_of: string;
};
type Policy = {
  policy_version: string;
  deviation_threshold: string;
  persistence_min_observations: number;
  persistence_min_duration_days: number;
  rationale: string;
};

export function ProgressWorkbench() {
  const [connection, setConnection] = useState<Connection | null>(null);
  const [measurements, setMeasurements] = useState<Measurement[]>([]);
  const [policies, setPolicies] = useState<Policy[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function headers(active = connection): HeadersInit {
    if (!active) return {};
    return {
      "Content-Type": "application/json",
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
    try {
      const [measurementResponse, policyResponse] = await Promise.all([
        fetch(`${API_URL}/api/v1/projects/${active.projectId}/progress/measurements`, {
          headers: headers(active),
        }),
        fetch(`${API_URL}/api/v1/projects/${active.projectId}/progress/policies`, {
          headers: headers(active),
        }),
      ]);
      if (!measurementResponse.ok) throw new Error(await readError(measurementResponse));
      if (!policyResponse.ok) throw new Error(await readError(policyResponse));
      setMeasurements((await measurementResponse.json()) as Measurement[]);
      setPolicies((await policyResponse.json()) as Policy[]);
      setMessage(null);
    } catch (caught) {
      setMessage(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  async function normalize(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!connection) return;
    const form = new FormData(event.currentTarget);
    const contextId = String(form.get("authorizedContextId") ?? "").trim();
    setBusy(true);
    try {
      const response = await fetch(
        `${API_URL}/api/v1/projects/${connection.projectId}/progress/measurements`,
        {
          method: "POST",
          headers: headers(),
          body: JSON.stringify({
            evidence_item_id: form.get("evidenceId"),
            authorized_context_id: contextId || null,
            measurement_kind: form.get("kind"),
            numerator: form.get("numerator"),
            denominator: form.get("denominator"),
            unit: form.get("unit"),
          }),
        },
      );
      if (!response.ok) throw new Error(await readError(response));
      setMessage("Immutable progress measurement recorded from its source evidence.");
      await refresh();
    } catch (caught) {
      setMessage(errorMessage(caught));
      setBusy(false);
    }
  }

  return (
    <div className="workbench-grid">
      <section className="workbench-card full-width">
        <span className="step-number">01</span>
        <h2>Project context</h2>
        <form className="inline-form" onSubmit={connect}>
          <label>Actor ID<input name="actorId" defaultValue="local-admin" required /></label>
          <label>Organization UUID<input name="organizationId" required /></label>
          <label>Project UUID<input name="projectId" required /></label>
          <button>Load progress</button>
          <button type="button" className="secondary" disabled={!connection || busy} onClick={() => refresh()}>Refresh</button>
        </form>
      </section>
      <section className="workbench-card">
        <span className="step-number">02</span>
        <h2>Normalize evidence</h2>
        <p className="card-copy">The numerator must match an immutable evidence value. Planned values additionally require an exact point in the linked authorized schedule.</p>
        <form className="stack-form" onSubmit={normalize}>
          <label>Evidence UUID<input name="evidenceId" required /></label>
          <label>Progress gate<select name="kind"><option>PLANNED_AUTHORIZED</option><option>REPORTED</option><option>EXECUTED</option><option>VERIFIED</option><option>ACCEPTED_RELEASED</option></select></label>
          <label>Authorized schedule UUID<input name="authorizedContextId" placeholder="Required only for planned progress" /></label>
          <div className="form-pair"><label>Numerator<input name="numerator" type="number" min="0" step="any" required /></label><label>Denominator<input name="denominator" type="number" min="0.000001" step="any" required /></label></div>
          <label>Unit<input name="unit" defaultValue="%" required /></label>
          <button disabled={!connection || busy}>Record normalized measurement</button>
        </form>
      </section>
      <section className="workbench-card">
        <span className="step-number">03</span>
        <h2>Visible threshold policies</h2>
        <div className="mini-ledger">{policies.map((policy) => <div key={policy.policy_version}><strong>{policy.policy_version}</strong><span>Deviation {Number(policy.deviation_threshold) * 100}% · {policy.persistence_min_observations} observations across {policy.persistence_min_duration_days} days</span><small>{policy.rationale}</small></div>)}</div>
      </section>
      <section className="workbench-card full-width">
        <div className="card-heading"><div><span className="step-number">04</span><h2>Separated progress gates</h2></div><span className="ledger-count">{measurements.length} measurements</span></div>
        <div className="ledger-table progress-ledger" role="table">{measurements.map((item) => <article className="ledger-row" role="row" key={item.id}><div><strong>{item.measurement_kind.replaceAll("_", " ")}</strong><small>{item.id}</small></div><code>{item.numerator}/{item.denominator}</code><div><span className={`truth ${item.semantic_state.toLowerCase()}`}>{item.semantic_state}</span><small>{item.truth_type.replaceAll("_", " ")}</small></div><div><span>{item.measurement_basis.replaceAll("_", " ")}</span><small>{new Date(item.as_of).toLocaleString()}</small></div><strong>{(Number(item.completion_ratio) * 100).toFixed(1)}%</strong></article>)}</div>
      </section>
      {message ? <p className="workbench-message full-width" role="status">{message}</p> : null}
    </div>
  );
}

function errorMessage(caught: unknown): string {
  return caught instanceof Error ? caught.message : "Progress request failed";
}

async function readError(response: Response): Promise<string> {
  const payload = (await response.json().catch(() => null)) as { detail?: string | { msg?: string }[] } | null;
  if (typeof payload?.detail === "string") return payload.detail;
  if (Array.isArray(payload?.detail)) return payload.detail.map((entry) => entry.msg).join("; ");
  return `Request failed with status ${response.status}`;
}
