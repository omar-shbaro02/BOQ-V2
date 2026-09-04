"use client";

import { FormEvent, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_VAI_API_URL ?? "http://localhost:8000";

type EvidenceItem = {
  id: string;
  field_name: string;
  value: unknown;
  semantic_state: string;
  truth_type: string;
  status: string;
  is_stale: boolean;
  derived_from_item_id: string | null;
};

type Artifact = {
  id: string;
  original_filename: string;
  source_id: string;
  sha256: string;
  size_bytes: number;
};

type Connection = { actorId: string; organizationId: string; projectId: string };

export function EvidenceWorkbench() {
  const [connection, setConnection] = useState<Connection | null>(null);
  const [items, setItems] = useState<EvidenceItem[]>([]);
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function headers(json = false): HeadersInit {
    if (!connection) return {};
    return {
      ...(json ? { "Content-Type": "application/json" } : {}),
      "X-VAI-Actor-ID": connection.actorId,
      "X-VAI-Organization-ID": connection.organizationId,
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
      const requestHeaders = {
        "X-VAI-Actor-ID": active.actorId,
        "X-VAI-Organization-ID": active.organizationId,
      };
      const [itemsResponse, artifactsResponse] = await Promise.all([
        fetch(`${API_URL}/api/v1/projects/${active.projectId}/evidence/items`, {
          headers: requestHeaders,
        }),
        fetch(`${API_URL}/api/v1/projects/${active.projectId}/evidence/artifacts`, {
          headers: requestHeaders,
        }),
      ]);
      if (!itemsResponse.ok) throw new Error(await readError(itemsResponse));
      if (!artifactsResponse.ok) throw new Error(await readError(artifactsResponse));
      setItems((await itemsResponse.json()) as EvidenceItem[]);
      setArtifacts((await artifactsResponse.json()) as Artifact[]);
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : "Evidence refresh failed");
    } finally {
      setBusy(false);
    }
  }

  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!connection) return;
    setBusy(true);
    setMessage(null);
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    try {
      const response = await fetch(
        `${API_URL}/api/v1/projects/${connection.projectId}/evidence/artifacts`,
        { method: "POST", headers: headers(), body: form },
      );
      if (!response.ok) throw new Error(await readError(response));
      setMessage("Artifact captured with immutable SHA-256 provenance.");
      formElement.reset();
      await refresh();
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : "Artifact upload failed");
      setBusy(false);
    }
  }

  async function assertEvidence(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!connection) return;
    setBusy(true);
    setMessage(null);
    const form = new FormData(event.currentTarget);
    const rawValue = String(form.get("value"));
    let value: unknown = rawValue;
    try {
      value = JSON.parse(rawValue);
    } catch {
      // Plain text is a valid evidence value.
    }
    const fieldName = String(form.get("fieldName"));
    try {
      const response = await fetch(
        `${API_URL}/api/v1/projects/${connection.projectId}/evidence/items`,
        {
          method: "POST",
          headers: headers(true),
          body: JSON.stringify({
            controlled_object_id: form.get("controlledObjectId") || null,
            artifact_id: form.get("artifactId") || null,
            field_name: fieldName,
            value,
            unit: form.get("unit") || null,
            measurement_basis: form.get("measurementBasis") || null,
            semantic_state: "REPORTED",
            truth_type: "REPORTED_CLAIM",
            as_of: new Date(String(form.get("asOf"))).toISOString(),
            confidence: form.get("confidence"),
          }),
        },
      );
      if (!response.ok) throw new Error(await readError(response));
      setMessage(`Reported claim “${fieldName}” captured without inflating its truth status.`);
      await refresh();
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : "Evidence assertion failed");
      setBusy(false);
    }
  }

  async function verify(itemId: string) {
    if (!connection) return;
    setBusy(true);
    setMessage(null);
    try {
      const response = await fetch(
        `${API_URL}/api/v1/projects/${connection.projectId}/evidence/items/${itemId}/verify`,
        {
          method: "POST",
          headers: headers(true),
          body: JSON.stringify({
            method: "Workbench human review",
            outcome: "VERIFIED",
            rationale: "Reviewed and accepted by the signed-in verifier",
            verified_confidence: "0.90",
          }),
        },
      );
      if (!response.ok) throw new Error(await readError(response));
      setMessage("A separate verified fact was created and linked to the source claim.");
      await refresh();
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : "Verification failed");
      setBusy(false);
    }
  }

  return (
    <div className="workbench-grid">
      <section className="workbench-card full-width">
        <div className="card-heading">
          <div>
            <span className="step-number">01</span>
            <h2>Connect project context</h2>
          </div>
          <span className={connection ? "connection active" : "connection"}>
            {connection ? "Connected" : "Required"}
          </span>
        </div>
        <form className="inline-form" onSubmit={connect}>
          <label>
            Actor ID
            <input name="actorId" defaultValue="local-admin" required />
          </label>
          <label>
            Organization UUID
            <input name="organizationId" required />
          </label>
          <label>
            Project UUID
            <input name="projectId" required />
          </label>
          <button type="submit">Connect</button>
          <button type="button" className="secondary" disabled={!connection || busy} onClick={() => refresh()}>
            Refresh evidence
          </button>
        </form>
      </section>

      <section className="workbench-card">
        <span className="step-number">02</span>
        <h2>Capture source artifact</h2>
        <p className="card-copy">CSV, XLSX, PDF, image, or source export—stored with its original bytes and digest.</p>
        <form className="stack-form" onSubmit={upload}>
          <label>File<input name="upload" type="file" required /></label>
          <label>Source type<input name="source_type" defaultValue="SITE_SUBMISSION" required /></label>
          <label>Source reference<input name="source_id" placeholder="TRANS-0042" required /></label>
          <label>Classification<select name="classification" defaultValue="INTERNAL"><option>PUBLIC</option><option>INTERNAL</option><option>CONFIDENTIAL</option><option>RESTRICTED</option></select></label>
          <button disabled={!connection || busy}>Capture artifact</button>
        </form>
      </section>

      <section className="workbench-card">
        <span className="step-number">03</span>
        <h2>Add typed assertion</h2>
        <p className="card-copy">Values accept JSON, including numeric zero. Progress fields require a measurement basis.</p>
        <form className="stack-form" onSubmit={assertEvidence}>
          <label>Field name<input name="fieldName" placeholder="installed_quantity" required /></label>
          <label>Value<input name="value" placeholder="0" required /></label>
          <label>As of<input name="asOf" type="datetime-local" required /></label>
          <label>Controlled object UUID<input name="controlledObjectId" /></label>
          <label>Artifact<select name="artifactId" defaultValue=""><option value="">No artifact link</option>{artifacts.map((artifact) => <option value={artifact.id} key={artifact.id}>{artifact.original_filename}</option>)}</select></label>
          <div className="form-pair"><label>Unit<input name="unit" placeholder="m³" /></label><label>Confidence<input name="confidence" type="number" min="0" max="1" step="0.01" defaultValue="0.5" required /></label></div>
          <label>Measurement basis<input name="measurementBasis" placeholder="PHYSICAL_VERIFIED" /></label>
          <button disabled={!connection || busy}>Record reported claim</button>
        </form>
      </section>

      <section className="workbench-card full-width evidence-ledger">
        <div className="card-heading"><div><span className="step-number">04</span><h2>Evidence ledger</h2></div><span className="ledger-count">{items.length} assertions</span></div>
        {items.length ? <div className="ledger-table" role="table">
          {items.map((item) => <article className="ledger-row" role="row" key={item.id}>
            <div><strong>{item.field_name}</strong><small>{item.id}</small></div>
            <code>{JSON.stringify(item.value)}</code>
            <div><span className={`truth ${item.semantic_state.toLowerCase()}`}>{item.semantic_state}</span><small>{item.truth_type.replaceAll("_", " ")}</small></div>
            <div><span>{item.status}</span>{item.derived_from_item_id ? <small>Derived verification</small> : <small>Source assertion</small>}</div>
            {item.semantic_state === "REPORTED" && item.status === "ACTIVE" ? <button className="verify-button" disabled={busy} onClick={() => verify(item.id)}>Verify</button> : <span />}
          </article>)}
        </div> : <p className="empty-state">Connect and refresh to inspect the project evidence ledger.</p>}
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
