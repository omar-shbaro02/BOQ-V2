"use client";

import Link from "next/link";
import { useEffect, useState, type ChangeEvent, type FormEvent } from "react";

const API = process.env.NEXT_PUBLIC_VAI_API_URL ?? "http://localhost:8000";

type Project = {
  id: string;
  code: string;
  name: string;
  timezone: string;
  currency: string;
  delivery_model: string;
  reporting_cadence: string;
};
type Workspace = { actorId: string; organizationId: string; organizationName?: string };
type Artifact = { id: string; original_filename: string; source_type: string; size_bytes: number; received_at: string };
type BoqSource = { id: string; artifact_id: string; version_number: number; extraction_status: string; extracted_row_count: number; created_at: string };
type GeneratedResult = { blob: Blob; filename: string; taskCount: string };

export default function BootstrapPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [project, setProject] = useState<Project | null>(null);
  const [fileName, setFileName] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [workspaceReady, setWorkspaceReady] = useState(false);
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [sources, setSources] = useState<BoqSource[]>([]);
  const [result, setResult] = useState<GeneratedResult | null>(null);

  useEffect(() => {
    async function initialize() {
      await Promise.resolve();
      const saved = localStorage.getItem("vai-project-workspace") ?? sessionStorage.getItem("vai-project-workspace");
      if (!saved) { setWorkspaceReady(true); return; }
      let active: Workspace;
      try { active = JSON.parse(saved) as Workspace; } catch { localStorage.removeItem("vai-project-workspace"); setWorkspaceReady(true); return; }
      setWorkspace(active);
      setBusy(true);
      try {
        const response = await fetch(`${API}/api/v1/organizations/${active.organizationId}/projects`, { headers: { "X-VAI-Actor-ID": active.actorId, "X-VAI-Organization-ID": active.organizationId } });
        if (!response.ok) throw new Error(await readError(response));
        const items = await response.json() as Project[];
        setProjects(items);
        const storedProject = localStorage.getItem("vai-active-project");
        const selected = items.find((item) => item.id === storedProject) ?? items[0] ?? null;
        setProject(selected);
        if (!items.length) setMessage("No projects are available yet. Create one from the Projects tab.");
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : "Unable to load projects");
      } finally {
        setBusy(false);
        setWorkspaceReady(true);
      }
    }
    void initialize();
  }, []);

  function chooseProject(id: string) {
    setProject(projects.find((item) => item.id === id) ?? null);
    localStorage.setItem("vai-active-project", id);
  }

  function chooseFile(event: ChangeEvent<HTMLInputElement>) {
    setFileName(event.target.files?.[0]?.name ?? "");
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!project || !workspace) return;
    setBusy(true);
    setError("");
    setMessage("");
    setResult(null);
    let boqWasSaved = false;
    try {
      const form = new FormData(event.currentTarget);
      const boq = form.get("boq");
      if (!(boq instanceof File) || !boq.size) throw new Error("Choose a BOQ PDF first.");

      setMessage("Saving the BOQ to the project…");
      const boqArtifact = await saveArtifact(boq, "BOQ_UPLOAD", `BOQ ${boq.name}`);
      boqWasSaved = true;
      await registerBoqSource(boqArtifact.id);

      setMessage("The BOQ is saved. Building the schedule workbook…");
      const response = await fetch(`${API}/api/v1/ms-project/generate-ai`, { method: "POST", body: form });
      if (!response.ok) throw new Error(await readError(response));
      const blob = await response.blob();
      const filename = `${project.code}-schedule-and-progress.xlsx`;
      const taskCount = response.headers.get("X-VAI-Task-Count") ?? "?";
      let outputArtifactId: string | undefined;
      try {
        const output = await saveArtifact(new File([blob], filename, { type: blob.type }), "AI_SCHEDULE_EXPORT", `Schedule generated from ${boq.name}`);
        outputArtifactId = output.id;
      } catch {
        setMessage("Schedule generated, but its saved copy could not be created. Download it now before leaving this page.");
      }
      setResult({ blob, filename, taskCount });
      if (outputArtifactId) setMessage("Schedule ready. Download the Excel workbook below, then review it before approval.");
      await refreshLibrary(workspace, project.id);
    } catch (cause) {
      const detail = cause instanceof Error ? cause.message : "Conversion failed";
      setMessage(boqWasSaved ? "The BOQ is safely stored in Project files. Schedule generation did not finish." : "");
      setError(detail === "Failed to fetch" ? "The scheduler connection was interrupted. The BOQ remains saved; try Generate schedule again." : detail);
    } finally {
      if (workspace && project) await refreshLibrary(workspace, project.id);
      setBusy(false);
    }
  }

  function jsonHeaders(): HeadersInit {
    return { "Content-Type": "application/json", "X-VAI-Actor-ID": workspace?.actorId ?? "", "X-VAI-Organization-ID": workspace?.organizationId ?? "" };
  }

  function authHeaders(active = workspace): HeadersInit {
    return { "X-VAI-Actor-ID": active?.actorId ?? "", "X-VAI-Organization-ID": active?.organizationId ?? "" };
  }

  async function saveArtifact(file: File, sourceType: string, sourceId: string): Promise<Artifact> {
    if (!project) throw new Error("Choose a project first.");
    const data = new FormData();
    data.set("upload", file);
    data.set("source_type", sourceType);
    data.set("source_id", sourceId);
    data.set("classification", "INTERNAL");
    const response = await fetch(`${API}/api/v1/projects/${project.id}/evidence/artifacts`, { method: "POST", headers: authHeaders(), body: data });
    if (!response.ok) throw new Error(await readError(response));
    return await response.json() as Artifact;
  }

  async function registerBoqSource(artifactId: string) {
    if (!project || !workspace) return;
    let priorId = sources[0]?.id ?? null;
    for (let attempt = 0; attempt < 2; attempt += 1) {
      const response = await fetch(`${API}/api/v1/projects/${project.id}/bootstrap/boq-sources`, {
        method: "POST",
        headers: { ...jsonHeaders(), "Idempotency-Key": `simple-boq-${artifactId}` },
        body: JSON.stringify({ artifact_id: artifactId, prior_source_version_id: priorId }),
      });
      if (response.ok) return;
      if (response.status !== 409 || attempt > 0) {
        throw new Error(`The BOQ was saved, but its project record could not be created: ${await readError(response)}`);
      }
      const latest = await fetch(`${API}/api/v1/projects/${project.id}/bootstrap/boq-sources`, { headers: authHeaders(workspace) });
      if (!latest.ok) throw new Error(await readError(latest));
      const current = await latest.json() as BoqSource[];
      priorId = current[0]?.id ?? null;
    }
  }

  async function refreshLibrary(active: Workspace, projectId: string) {
    try {
      const headers = { "X-VAI-Actor-ID": active.actorId, "X-VAI-Organization-ID": active.organizationId };
      const [artifactResponse, sourceResponse] = await Promise.all([
        fetch(`${API}/api/v1/projects/${projectId}/evidence/artifacts`, { headers }),
        fetch(`${API}/api/v1/projects/${projectId}/bootstrap/boq-sources`, { headers }),
      ]);
      if (!artifactResponse.ok) throw new Error(await readError(artifactResponse));
      if (!sourceResponse.ok) throw new Error(await readError(sourceResponse));
      setArtifacts(await artifactResponse.json() as Artifact[]);
      setSources(await sourceResponse.json() as BoqSource[]);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to load saved BOQs");
    }
  }

  async function downloadArtifact(artifact: Artifact) {
    if (!project) return;
    setError("");
    try {
      const response = await fetch(`${API}/api/v1/projects/${project.id}/evidence/artifacts/${artifact.id}/content`, { headers: authHeaders() });
      if (!response.ok) throw new Error(await readError(response));
      download(await response.blob(), artifact.original_filename);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to download the saved file");
    }
  }

  useEffect(() => {
    if (!workspace || !project) return;
    void refreshLibrary(workspace, project.id);
  }, [project, workspace]);

  return <main className="workbench-shell project-workspace">
    <header className="workbench-heading workspace-heading">
      <div>
        <span className="eyebrow">BOQ to schedule</span>
        <h1 className="workbench-title">Build a project plan.</h1>
      </div>
      <div className="workspace-intro">
        <p>Connect a project, upload its current BOQ, and receive a review-ready MS Project workbook.</p>
        <div className="workspace-header-links">
          <Link href="/bootstrap/schedule-assistant">Schedule assistant</Link>
          <Link href="/bootstrap/advanced">Governed workflow</Link>
        </div>
      </div>
    </header>

    <nav className="workspace-flow" aria-label="Schedule generation progress">
      <ol>
        <li className="active"><span>1</span><b>Project</b><small>Choose project</small></li>
        <li className={fileName ? "active" : ""}><span>2</span><b>Source</b><small>Save BOQ</small></li>
        <li className={busy ? "active" : ""}><span>3</span><b>Generate</b><small>Build proposal</small></li>
        <li className={result ? "active" : ""}><span>4</span><b>Download</b><small>Get workbook</small></li>
      </ol>
    </nav>

    <section className="workbench-card workspace-main" aria-busy={busy}>
      <section className="workspace-section" aria-labelledby="project-section-title">
        <div className="workspace-section-heading">
          <span className="workspace-step">1</span>
          <div>
            <h2 id="project-section-title">Choose your project</h2>
            <p>{workspace?.organizationName ? `Projects in ${workspace.organizationName}` : "Choose the project you want to schedule."}</p>
          </div>
          <Link className="secondary-action" href="/setup">Create a project</Link>
        </div>

        {!workspaceReady || busy ? <div className="project-empty-state"><span className="loading-dot" />Loading your projects…</div> : !workspace ? <div className="project-empty-state"><div><strong>No project workspace yet</strong><p>Create your first project and VAI will manage the internal workspace details automatically.</p></div><Link className="primary-action" href="/setup">Create first project</Link></div> : <label className="project-picker project-picker-ready">
          <span>Project</span>
          <select value={project?.id ?? ""} onChange={(event) => chooseProject(event.target.value)} disabled={!projects.length}>
            <option value="">{projects.length ? "Choose a project" : "No projects available"}</option>
            {projects.map((item) => <option key={item.id} value={item.id}>{item.code} · {item.name}</option>)}
          </select>
        </label>}

        {project ? <div className="autofill-grid" aria-label="Selected project details">
          <Auto label="Project code" value={project.code} />
          <Auto label="Timezone" value={project.timezone} />
          <Auto label="Currency" value={project.currency} />
          <Auto label="Delivery model" value={project.delivery_model.replaceAll("_", " ")} />
          <Auto label="Reporting" value={project.reporting_cadence} />
        </div> : null}
      </section>

      <section className="workspace-section source-section" aria-labelledby="source-section-title">
        <div className="workspace-section-heading">
          <span className="workspace-step">2</span>
          <div>
            <h2 id="source-section-title">Add the current BOQ</h2>
            <p>VAI applies the standard workbook structure automatically.</p>
          </div>
        </div>

        <form className="workspace-upload" onSubmit={submit}>
          <div className="source-input-grid">
            <label className={`file-drop ${fileName ? "has-file" : ""}`}>
              <UploadIcon />
              <span className="file-drop-copy">
                <strong>{fileName || "Choose the current BOQ"}</strong>
                <small>{fileName ? "Ready to generate" : "Text-native PDF · up to 20 MB"}</small>
              </span>
              <span className="file-button">Browse file</span>
              <input name="boq" type="file" accept=".pdf,application/pdf" onChange={chooseFile} required />
            </label>
            <div className="schedule-inputs">
              <label><span>Project start</span><input name="project_start" type="date" required /></label>
              <label><span>Required completion <small>Optional</small></span><input name="target_finish" type="date" /></label>
            </div>
          </div>

          <section className="output-contract" aria-labelledby="output-contract-title">
            <div className="output-contract-heading">
              <span className="section-kicker">Built-in output contract</span>
              <h3 id="output-contract-title">A clean six-column workbook, every time</h3>
              <p>Only your project data is required. VAI standardizes the schedule output on the server.</p>
            </div>
            <div className="boundary-list">
              <Boundary icon="1" title="ID & subdivision" text="Consolidated work packages, not paraphrased BOQ lines" />
              <Boundary icon="2" title="Duration & dates" text="Working-day duration with start and finish dates" />
              <Boundary icon="3" title="Dependency" text="Earlier predecessor IDs in MS Project import format" />
            </div>
          </section>

          <div className="generation-footer">
            <div>
              <span className="generation-label">Ready when you are</span>
              <p>{project ? `The proposal will be generated for ${project.code} and must be reviewed before approval.` : "Select a project, attach a BOQ, and set a start date to continue."}</p>
            </div>
            <button className="primary-action" disabled={busy || !project}>
              {busy ? "Building schedule (this can take several minutes)…" : "Generate schedule"}<span aria-hidden="true">→</span>
            </button>
          </div>
        </form>
      </section>

      {error ? <p className="form-message error" role="alert">{error}</p> : null}
      {message ? <p className="form-message success" role="status">{message}</p> : null}
      {result ? <section className="generation-result" aria-labelledby="generation-result-title">
        <span className="result-check" aria-hidden="true">✓</span>
        <div><span className="section-kicker">Schedule generated</span><h2 id="generation-result-title">Your Excel workbook is ready</h2><p>{result.taskCount} schedule activities were generated. The workbook is a proposal and must be reviewed before it becomes an approved schedule.</p></div>
        <button className="primary-action" type="button" onClick={() => download(result.blob, result.filename)}>Download Excel workbook <span aria-hidden="true">↓</span></button>
        <ol><li><strong>Download</strong><span>Save the XLSX workbook to your computer.</span></li><li><strong>Review</strong><span>Open it in Excel or import it into MS Project and check dates, durations, and dependencies.</span></li><li><strong>Continue</strong><span>Use the schedule assistant for reviewed changes; approval remains a separate governed step.</span></li></ol>
        <Link className="secondary-action" href="/bootstrap/schedule-assistant">Open schedule assistant →</Link>
      </section> : null}

      <section className="workspace-section boq-library" aria-labelledby="boq-library-title">
        <div className="workspace-section-heading"><span className="workspace-step">3</span><div><h2 id="boq-library-title">Project files</h2><p>Previously uploaded BOQs and generated workbooks remain available for this project.</p></div></div>
        {artifacts.filter((item) => item.source_type === "BOQ_UPLOAD" || item.source_type === "AI_SCHEDULE_EXPORT").length ? <div className="project-file-list">
          {artifacts.filter((item) => item.source_type === "BOQ_UPLOAD" || item.source_type === "AI_SCHEDULE_EXPORT").map((artifact) => {
            const source = sources.find((item) => item.artifact_id === artifact.id);
            return <article key={artifact.id}><div><span className="file-kind">{artifact.source_type === "BOQ_UPLOAD" ? "BOQ" : "Excel schedule"}</span><strong>{artifact.original_filename}</strong><small>{source ? `BOQ version ${source.version_number} · ${source.extracted_row_count ? `${source.extracted_row_count} extracted rows` : "saved for scheduling · detailed review pending"}` : `${formatBytes(artifact.size_bytes)} · saved ${new Date(artifact.received_at).toLocaleString()}`}</small></div><button type="button" className="secondary-action" onClick={() => void downloadArtifact(artifact)}>Download</button></article>;
          })}
        </div> : <div className="project-empty-state"><div><strong>No saved project files yet</strong><p>Upload a BOQ above. It and the generated workbook will appear here.</p></div></div>}
      </section>
    </section>
  </main>;
}

function Auto({ label, value }: { label: string; value: string }) {
  return <div><small>{label}</small><strong>{value}</strong></div>;
}

function Boundary({ icon, title, text }: { icon: string; title: string; text: string }) {
  return <div><i>{icon}</i><span><b>{title}</b><small>{text}</small></span></div>;
}

function UploadIcon() {
  return <svg className="upload-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M12 16V4m0 0L7.5 8.5M12 4l4.5 4.5" /><path d="M5 14v4a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-4" /></svg>;
}

async function readError(response: Response) {
  const payload = await response.json().catch(() => null) as { detail?: string } | null;
  return payload?.detail ?? `Request failed (${response.status})`;
}

function download(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function formatBytes(bytes: number) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
