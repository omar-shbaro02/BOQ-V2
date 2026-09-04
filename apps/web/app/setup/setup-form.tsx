"use client";

import { FormEvent, useState } from "react";

type CreatedProject = {
  organizationId: string;
  projectId: string;
};

const API_URL = process.env.NEXT_PUBLIC_VAI_API_URL ?? "http://localhost:8000";

export function SetupForm() {
  const [result, setResult] = useState<CreatedProject | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    const form = new FormData(event.currentTarget);
    const actorId = String(form.get("actorId"));
    try {
      const organizationResponse = await fetch(`${API_URL}/api/v1/organizations`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-VAI-Actor-ID": actorId,
          "X-VAI-Roles": "ORGANIZATION_ADMIN",
        },
        body: JSON.stringify({
          name: form.get("organizationName"),
          slug: form.get("organizationSlug"),
        }),
      });
      if (!organizationResponse.ok) {
        throw new Error(await readError(organizationResponse));
      }
      const organization = (await organizationResponse.json()) as { id: string };
      const projectResponse = await fetch(
        `${API_URL}/api/v1/organizations/${organization.id}/projects`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-VAI-Actor-ID": actorId,
            "X-VAI-Organization-ID": organization.id,
          },
          body: JSON.stringify({
            code: form.get("projectCode"),
            name: form.get("projectName"),
            timezone: form.get("timezone"),
            currency: form.get("currency"),
            delivery_model: form.get("deliveryModel"),
            reporting_cadence: form.get("reportingCadence"),
          }),
        },
      );
      if (!projectResponse.ok) {
        throw new Error(await readError(projectResponse));
      }
      const project = (await projectResponse.json()) as { id: string };
      setResult({ organizationId: organization.id, projectId: project.id });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Setup failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form className="setup-form" onSubmit={submit}>
      <fieldset>
        <legend>Organization boundary</legend>
        <label>
          Organization name
          <input name="organizationName" required minLength={2} />
        </label>
        <label>
          Organization slug
          <input name="organizationSlug" required pattern="[a-z0-9]+(?:-[a-z0-9]+)*" />
        </label>
        <label>
          Development actor ID
          <input name="actorId" defaultValue="local-admin" required />
        </label>
      </fieldset>
      <fieldset>
        <legend>Initial project</legend>
        <label>
          Project code
          <input name="projectCode" required />
        </label>
        <label>
          Project name
          <input name="projectName" required minLength={2} />
        </label>
        <label>
          IANA timezone
          <input name="timezone" defaultValue="Asia/Beirut" required />
        </label>
        <label>
          Currency
          <input name="currency" defaultValue="USD" pattern="[A-Z]{3}" required />
        </label>
        <label>
          Delivery model
          <input name="deliveryModel" defaultValue="DESIGN_BID_BUILD" required />
        </label>
        <label>
          Reporting cadence
          <input name="reportingCadence" defaultValue="WEEKLY" required />
        </label>
      </fieldset>
      <button disabled={submitting} type="submit">
        {submitting ? "Creating governed context…" : "Create organization and project"}
      </button>
      {error ? <p className="form-message error">{error}</p> : null}
      {result ? (
        <div className="form-message success">
          <strong>Project boundary created.</strong>
          <span>Organization: {result.organizationId}</span>
          <span>Project: {result.projectId}</span>
        </div>
      ) : null}
    </form>
  );
}

async function readError(response: Response): Promise<string> {
  const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
  return payload?.detail ?? `Request failed with status ${response.status}`;
}

