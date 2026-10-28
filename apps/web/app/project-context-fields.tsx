"use client";

import { useEffect, useState } from "react";
import { currentWorkspace } from "./workspace-session";

const API = process.env.NEXT_PUBLIC_VAI_API_URL ?? "http://localhost:8000";
const ACTIVE_PROJECT_KEY = "vai-active-project";

type Workspace = { actorId: string; organizationId: string };
type Project = { id: string; code: string; name: string };
type DecisionCase = { id: string; case_number: string; title: string; lifecycle: string };

export function ProjectContextFields({ includeCase = false }: { includeCase?: boolean }) {
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState("");
  const [cases, setCases] = useState<DecisionCase[]>([]);
  const [caseId, setCaseId] = useState("");
  const [message, setMessage] = useState("Loading projects…");

  useEffect(() => {
    async function initialize() {
      await Promise.resolve();
      let active: Workspace | null;
      try { active = await currentWorkspace(); }
      catch (error) { setMessage(error instanceof Error ? error.message : "Identity service is unavailable."); return; }
      if (!active) { setMessage("Create a project from the Projects tab first."); return; }
      setWorkspace(active);
      void fetch(`${API}/api/v1/organizations/${active.organizationId}/projects`, {
      headers: { "X-VAI-Actor-ID": active.actorId, "X-VAI-Organization-ID": active.organizationId },
    }).then(async (response) => {
      if (!response.ok) throw new Error("Unable to load projects");
      const items = await response.json() as Project[];
      setProjects(items);
      const stored = localStorage.getItem(ACTIVE_PROJECT_KEY);
      const selected = items.some((item) => item.id === stored) ? stored! : items[0]?.id ?? "";
      setProjectId(selected);
      setMessage(items.length ? "" : "No projects are available yet.");
      }).catch((error: unknown) => setMessage(error instanceof Error ? error.message : "Unable to load projects"));
    }
    void initialize();
  }, []);

  useEffect(() => {
    if (!workspace || !projectId || !includeCase) return;
    const controller = new AbortController();
    localStorage.setItem(ACTIVE_PROJECT_KEY, projectId);
    void fetch(`${API}/api/v1/projects/${projectId}/decision-cases`, {
      signal: controller.signal,
      headers: { "X-VAI-Actor-ID": workspace.actorId, "X-VAI-Organization-ID": workspace.organizationId },
    }).then(async (response) => {
      if (!response.ok) throw new Error("Unable to load decision cases");
      const items = await response.json() as DecisionCase[];
      setCases(items);
      setCaseId(items[0]?.id ?? "");
    }).catch((error: unknown) => { if (!controller.signal.aborted) setMessage(error instanceof Error ? error.message : "Unable to load decision cases"); });
    return () => controller.abort();
  }, [includeCase, projectId, workspace]);

  function selectProject(value: string) {
    setProjectId(value);
    setCaseId("");
    setCases([]);
    localStorage.setItem(ACTIVE_PROJECT_KEY, value);
  }

  return <>
    <input type="hidden" name="actorId" value={workspace?.actorId ?? ""} />
    <input type="hidden" name="organizationId" value={workspace?.organizationId ?? ""} />
    <label>Project<select name="projectId" value={projectId} onChange={(event) => selectProject(event.target.value)} required>
      <option value="">Choose a project</option>
      {projects.map((project) => <option key={project.id} value={project.id}>{project.code} · {project.name}</option>)}
    </select></label>
    {includeCase ? <label>Decision case<select name="caseId" value={caseId} onChange={(event) => setCaseId(event.target.value)} required>
      <option value="">{cases.length ? "Choose a decision case" : "No decision cases available"}</option>
      {cases.map((item) => <option key={item.id} value={item.id}>{item.case_number} · {item.title} ({item.lifecycle.toLowerCase()})</option>)}
    </select></label> : null}
    {message ? <span className="context-message" role="status">{message}</span> : null}
  </>;
}
