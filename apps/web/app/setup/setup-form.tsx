"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_VAI_API_URL ?? "http://localhost:8000";
const LOCAL_ACTOR = "local-admin";
const WORKSPACE_KEY = "vai-project-workspace";

type Workspace = { actorId: string; organizationId: string; organizationName?: string };
type CreatedProject = { code: string; name: string };

export function SetupForm() {
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [ready, setReady] = useState(false);
  const [result, setResult] = useState<CreatedProject | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    async function initialize() {
      await Promise.resolve();
      const saved = localStorage.getItem(WORKSPACE_KEY) ?? sessionStorage.getItem(WORKSPACE_KEY);
      if (saved) {
        try { setWorkspace(JSON.parse(saved) as Workspace); } catch { localStorage.removeItem(WORKSPACE_KEY); }
      }
      setReady(true);
    }
    void initialize();
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    setResult(null);
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    try {
      let active = workspace;
      if (!active) {
        const organizationName = String(form.get("organizationName"));
        const organizationResponse = await fetch(`${API_URL}/api/v1/organizations`, {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-VAI-Actor-ID": LOCAL_ACTOR, "X-VAI-Roles": "ORGANIZATION_ADMIN" },
          body: JSON.stringify({ name: organizationName, slug: workspaceSlug(organizationName) }),
        });
        if (!organizationResponse.ok) throw new Error(await readError(organizationResponse));
        const organization = await organizationResponse.json() as { id: string };
        active = { actorId: LOCAL_ACTOR, organizationId: organization.id, organizationName };
        localStorage.setItem(WORKSPACE_KEY, JSON.stringify(active));
        setWorkspace(active);
      }

      const projectResponse = await fetch(`${API_URL}/api/v1/organizations/${active.organizationId}/projects`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-VAI-Actor-ID": active.actorId, "X-VAI-Organization-ID": active.organizationId },
        body: JSON.stringify({
          code: String(form.get("projectCode")).toUpperCase(),
          name: form.get("projectName"),
          timezone: form.get("timezone"),
          currency: String(form.get("currency")).toUpperCase(),
          delivery_model: form.get("deliveryModel"),
          reporting_cadence: form.get("reportingCadence"),
        }),
      });
      if (!projectResponse.ok) throw new Error(await readError(projectResponse));
      const project = await projectResponse.json() as { code: string; name: string };
      setResult({ code: project.code, name: project.name });
      formElement.reset();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Project creation failed");
    } finally {
      setSubmitting(false);
    }
  }

  if (!ready) return <p className="form-message">Loading project workspace…</p>;

  return <form className="setup-form project-create-form" onSubmit={submit}>
    <div className="setup-form-heading">
      <div><span className="workspace-step">1</span><div><h2>Project details</h2><p>{workspace?.organizationName ? `Adding to ${workspace.organizationName}` : "Create your local workspace and first project."}</p></div></div>
      <Link href="/bootstrap">Back to BOQ workspace</Link>
    </div>
    {!workspace ? <fieldset>
      <legend>Workspace</legend>
      <label>Company or workspace name<input name="organizationName" placeholder="Example Construction" required minLength={2} /></label>
    </fieldset> : null}
    <fieldset>
      <legend>Project information</legend>
      <label>Project name<input name="projectName" placeholder="Marina redevelopment" required minLength={2} /></label>
      <label>Project code<input name="projectCode" placeholder="MAR-01" required /></label>
      <label>Timezone<input name="timezone" defaultValue="Asia/Beirut" required /></label>
      <label>Currency<input name="currency" defaultValue="USD" pattern="[A-Za-z]{3}" required /></label>
      <label>Delivery model<select name="deliveryModel" defaultValue="DESIGN_BID_BUILD"><option value="DESIGN_BID_BUILD">Design–bid–build</option><option value="DESIGN_BUILD">Design–build</option><option value="CONSTRUCTION_MANAGEMENT">Construction management</option></select></label>
      <label>Reporting cadence<select name="reportingCadence" defaultValue="WEEKLY"><option value="WEEKLY">Weekly</option><option value="BIWEEKLY">Every two weeks</option><option value="MONTHLY">Monthly</option></select></label>
    </fieldset>
    <div className="setup-submit-row"><div><strong>Ready to create</strong><span>You can add the BOQ from the schedule workspace next.</span></div><button disabled={submitting} type="submit">{submitting ? "Creating project…" : "Create project"}</button></div>
    {error ? <p className="form-message error" role="alert">{error}</p> : null}
    {result ? <div className="form-message success" role="status"><strong>{result.code} · {result.name} created</strong><span>The project is ready to use in the BOQ workspace.</span><Link href="/bootstrap">Open BOQ workspace →</Link></div> : null}
  </form>;
}

function workspaceSlug(name: string) {
  const base = name.toLowerCase().trim().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "local-workspace";
  return `${base}-${crypto.randomUUID().slice(0, 8)}`;
}

async function readError(response: Response) {
  const payload = await response.json().catch(() => null) as { detail?: string } | null;
  return payload?.detail ?? `Request failed (${response.status})`;
}
