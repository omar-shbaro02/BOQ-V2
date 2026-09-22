"use client";
import Link from "next/link";
import { useState, type FormEvent } from "react";

const API = process.env.NEXT_PUBLIC_VAI_API_URL ?? "http://localhost:8000";
type Project = { id:string; code:string; name:string; timezone:string; currency:string; delivery_model:string; reporting_cadence:string };

export default function BootstrapPage() {
  const [projects,setProjects]=useState<Project[]>([]);
  const [project,setProject]=useState<Project|null>(null);
  const [message,setMessage]=useState("");
  const [error,setError]=useState("");
  const [busy,setBusy]=useState(false);

  async function loadProjects(event:FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError("");
    const form=new FormData(event.currentTarget);
    const actorId=String(form.get("actorId")), organizationId=String(form.get("organizationId"));
    try {
      const response=await fetch(API+"/api/v1/organizations/"+organizationId+"/projects",{headers:{"X-VAI-Actor-ID":actorId,"X-VAI-Organization-ID":organizationId}});
      if(!response.ok) throw new Error(await readError(response));
      const items=await response.json() as Project[];
      setProjects(items);
      sessionStorage.setItem("vai-project-workspace",JSON.stringify({actorId,organizationId}));
      setMessage(items.length?"Projects loaded. Choose one to continue.":"No projects are available.");
    } catch(cause) { setError(cause instanceof Error?cause.message:"Unable to load projects"); }
    finally { setBusy(false); }
  }

  async function chooseProject(id:string) {
    const selected=projects.find(item=>item.id===id)??null;
    setProject(selected);
  }

  async function submit(event:FormEvent<HTMLFormElement>) {
    event.preventDefault(); if(!project)return; setBusy(true); setError(""); setMessage("");
    try {
      const form=new FormData(event.currentTarget);
      const response=await fetch(API+"/api/v1/ms-project/generate-ai",{method:"POST",body:form});
      if(!response.ok) throw new Error(await readError(response));
      download(await response.blob(),project.code+"-schedule-and-progress.xlsx");
      setMessage("OpenAI generated "+(response.headers.get("X-VAI-Task-Count")??"?")+" schedule subdivisions. Review the proposal before baseline approval.");
    } catch(cause) { setError(cause instanceof Error?cause.message:"Conversion failed"); }
    finally { setBusy(false); }
  }

  const saved=typeof window==="undefined"?null:JSON.parse(sessionStorage.getItem("vai-project-workspace")??"null") as {actorId?:string;organizationId?:string}|null;
  return <main className="workbench-shell project-workspace">
    <header className="workbench-heading"><div><span className="eyebrow">Single-input project workspace</span><h1 className="workbench-title">Plan the project once.</h1></div><p>Choose a project, supply its BOQ, and review the automated planning assumptions. The MS Project workbook format is built into VAI.</p></header>
    <section className="workspace-flow"><span className="active">1 <b>Project</b></span><span>2 <b>Sources</b></span><span>3 <b>Review</b></span><span>4 <b>Export</b></span></section>
    <div className="workspace-layout">
      <section className="workbench-card workspace-main">
        <div className="card-heading"><div><span className="step-number">01</span><h2>Select project</h2></div><Link className="quiet-link" href="/setup">Create project</Link></div>
        <form className="project-context-form" onSubmit={loadProjects}><label>Actor<input name="actorId" defaultValue={saved?.actorId??"local-admin"} required/></label><label>Organization UUID<input name="organizationId" defaultValue={saved?.organizationId} required/></label><button disabled={busy}>Load projects</button></form>
        <label className="project-picker">Project<select value={project?.id??""} onChange={event=>void chooseProject(event.target.value)}><option value="">Choose a project</option>{projects.map(item=><option key={item.id} value={item.id}>{item.code} · {item.name}</option>)}</select></label>
        {project?<div className="autofill-grid"><Auto label="Project code" value={project.code}/><Auto label="Timezone" value={project.timezone}/><Auto label="Currency" value={project.currency}/><Auto label="Delivery model" value={project.delivery_model.replaceAll("_"," ")}/><Auto label="Reporting" value={project.reporting_cadence}/></div>:null}
        <hr/><span className="step-number">02</span><h2>Project source</h2><p className="panel-note">Upload the current BOQ revision. VAI applies the standard MS Project Excel contract automatically.</p>
        <form className="workspace-upload" onSubmit={submit}>
          <label className="file-drop"><span>BOQ PDF</span><strong>Choose the current BOQ</strong><small>Text-native PDF · up to 20 MB</small><input name="boq" type="file" accept=".pdf,application/pdf" required/></label>
          <div className="schedule-inputs"><label>Project start<input name="project_start" type="date" required/></label><label>Required completion <small>Optional</small><input name="target_finish" type="date"/></label></div>
          <div className="automation-summary"><span>OpenAI schedule agent</span><ul><li>Consolidates BOQ lines into schedule subdivisions</li><li>Proposes realistic durations and project dates</li><li>Creates valid predecessor dependencies</li><li>Returns only the six requested Excel columns</li></ul></div>
          <button className="primary-action" disabled={busy||!project}>{busy?"OpenAI is building the schedule…":"Generate OpenAI time schedule"}</button>
        </form>
        {error?<p className="form-message error" role="alert">{error}</p>:null}{message?<p className="form-message success" role="status">{message}</p>:null}
      </section>
      <aside className="workbench-card workspace-side"><span className="section-kicker">Built-in output contract</span><h2>Exactly six columns</h2><p>VAI creates the standardized workbook on the server. Clients only provide their project data.</p><div className="boundary-list"><Boundary icon="1" title="ID & subdivision" text="Consolidated work packages, not paraphrased BOQ lines"/><Boundary icon="2" title="Duration & dates" text="Working-day duration with start and finish dates"/><Boundary icon="3" title="Dependency" text="Earlier predecessor IDs in MS Project import format"/></div><Link href="/bootstrap/advanced" className="quiet-link">Open governed review workflow →</Link></aside>
    </div>
  </main>;
}

function Auto({label,value}:{label:string;value:string}) { return <div><small>{label}</small><strong>{value}</strong></div>; }
function Boundary({icon,title,text}:{icon:string;title:string;text:string}) { return <span><i>{icon}</i><b>{title}</b><small>{text}</small></span>; }
async function readError(response:Response) { const payload=await response.json().catch(()=>null) as {detail?:string}|null;return payload?.detail??"Request failed ("+response.status+")"; }
function download(blob:Blob,filename:string) { const url=URL.createObjectURL(blob),link=document.createElement("a");link.href=url;link.download=filename;link.click();URL.revokeObjectURL(url); }
