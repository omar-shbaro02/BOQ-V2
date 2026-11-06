"use client";

import Link from "next/link";
import { type FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { ProjectContextFields } from "../project-context-fields";

const API = process.env.NEXT_PUBLIC_VAI_API_URL ?? "http://localhost:8000";
type Connection = { actorId: string; organizationId: string; projectId: string };
type Policy = { policy_version: string; on_time_tolerance_days: string; maximum_schedule_age_days: number; rationale: string };
type Activity = { code: string; name: string; planned_start: string; planned_finish: string; calendar_id: string; total_float_days: string | null };
type Dependency = { predecessor_code: string; successor_code: string; relation_type: string; lag_days: string };
type Milestone = { code: string; name: string; planned_date: string; activity_code: string | null; material: boolean };
type Network = { context_id: string; version_number: number; effective_from: string; data_date: string; activity_count: number; dependency_count: number; milestone_count: number; calendar_count: number; activities: Activity[]; dependencies: Dependency[]; milestones: Milestone[] };
type Loaded = { key: string; network: Network | null; policies: Policy[]; missing: boolean; error: string; policyError: string };
const keyOf = (connection: Connection | null) => connection ? `${connection.organizationId}/${connection.actorId}/${connection.projectId}` : "";
const headers = (connection: Connection) => ({ "Content-Type": "application/json", "X-VAI-Actor-ID": connection.actorId, "X-VAI-Organization-ID": connection.organizationId });

export function ScheduleWorkbench() {
  const [connection, setConnection] = useState<Connection | null>(null);
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  const [revision, setRevision] = useState(0);
  const [search, setSearch] = useState("");
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState("");
  const [policyFailure, setPolicyFailure] = useState("");
  const currentKey = keyOf(connection);
  const selectedKey = useRef(currentKey);
  const changeProject = useCallback((next: Connection | null) => {
    selectedKey.current = keyOf(next);
    setConnection(next); setLoaded(null); setSearch(""); setNotice(""); setPolicyFailure("");
  }, []);

  useEffect(() => {
    if (!connection) return;
    const active = connection;
    const controller = new AbortController();
    const key = keyOf(active);
    async function load() {
      const next: Loaded = { key, network: null, policies: [], missing: false, error: "", policyError: "" };
      await Promise.all([
        (async () => {
          try {
            const response = await fetch(`${API}/api/v1/projects/${active.projectId}/schedule/network`, { headers: headers(active), signal: controller.signal });
            if (!response.ok) {
              const detail = await readError(response);
              if (response.status === 404 && detail === "Current authorized schedule not found") next.missing = true;
              else next.error = detail;
            } else next.network = await response.json() as Network;
          } catch (error) { next.error = errorMessage(error); }
        })(),
        (async () => {
          try {
            const response = await fetch(`${API}/api/v1/projects/${active.projectId}/schedule/policies`, { headers: headers(active), signal: controller.signal });
            if (!response.ok) throw new Error(await readError(response));
            next.policies = await response.json() as Policy[];
          } catch (error) { next.policyError = errorMessage(error); }
        })(),
      ]);
      if (!controller.signal.aborted && selectedKey.current === key) setLoaded(next);
    }
    void load();
    return () => controller.abort();
  }, [connection, revision]);

  const data = loaded?.key === currentKey ? loaded : null;
  const loading = Boolean(connection && !data);
  const network = data?.network;
  const query = search.trim().toLocaleLowerCase();
  const activities = network?.activities.filter(activity => `${activity.code} ${activity.name}`.toLocaleLowerCase().includes(query)) ?? [];
  const starts = network?.activities.map(activity => activity.planned_start).filter(Boolean).sort() ?? [];
  const finishes = [...(network?.activities.map(activity => activity.planned_finish) ?? []), ...(network?.milestones.map(milestone => milestone.planned_date) ?? [])].filter(Boolean).sort();
  const refresh = () => { setLoaded(null); setRevision(value => value + 1); };

  async function createPolicy(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!connection || saving) return;
    const form = event.currentTarget;
    const values = new FormData(form);
    const key = keyOf(connection);
    setSaving(true); setNotice(""); setPolicyFailure("");
    try {
      const response = await fetch(`${API}/api/v1/projects/${connection.projectId}/schedule/policies`, {
        method: "POST", headers: headers(connection),
        body: JSON.stringify({ policy_version: values.get("policyVersion"), on_time_tolerance_days: values.get("tolerance"), maximum_schedule_age_days: Number(values.get("maximumAge")), require_dependency_for_consequence: true, allow_calculated_float: true, rationale: values.get("rationale") }),
      });
      if (!response.ok) throw new Error(await readError(response));
      if (selectedKey.current !== key) return;
      form.reset(); setNotice("Policy version saved. The approved schedule has not changed."); refresh();
    } catch (error) { if (selectedKey.current === key) setPolicyFailure(errorMessage(error)); }
    finally { setSaving(false); }
  }

  return <div className="as-workspace">
    <section className="as-project-bar" aria-label="Project selection"><fieldset disabled={saving}><ProjectContextFields onConnectionChange={changeProject} /></fieldset><button type="button" className="secondary" disabled={!connection || loading || saving} onClick={refresh}>Refresh</button></section>
    {notice ? <p className="as-card" role="status">{notice}</p> : null}
    {!connection ? <section className="as-card"><h2>Choose a project to see its plan</h2><p>Select a project above. If you have not created one yet, start in <Link href="/setup">Projects</Link>.</p></section> : loading ? <p className="as-loading" role="status">Loading the approved schedule…</p> : null}
    {data?.error ? <section className="as-card as-warning" role="alert"><h2>Schedule unavailable</h2><p>{data.error}</p><p>Try Refresh or check your access to this project. An unavailable result does not mean there is no approved schedule.</p></section> : null}
    {data?.missing ? <section className="as-card as-empty"><span className="eyebrow">Approval needed</span><h2>No approved schedule yet</h2><p>A generated workbook is a proposal until it has been reviewed and approved. Approve the project plan before using it as the reference for progress.</p><Link className="primary-action" href="/bootstrap/advanced">Review and approve a schedule <span aria-hidden="true">→</span></Link></section> : null}
    {network ? <>
      <section className="as-card" aria-label="Approved plan summary"><div className="as-section-heading"><div><span className="as-approved">Approved version {network.version_number}</span><h2>The plan you are measuring against</h2><p>Schedule data date: {date(network.data_date)}</p></div><Link className="primary-action" href="/progress">Next: Update progress <span aria-hidden="true">→</span></Link></div><dl className="as-summary"><div><dt>Planned start</dt><dd>{date(starts[0])}</dd></div><div><dt>Planned finish</dt><dd>{date(finishes.at(-1))}</dd></div><div><dt>Tasks</dt><dd>{network.activity_count}</dd></div><div><dt>Milestones</dt><dd>{network.milestone_count}</dd></div></dl><p className="as-note">Dates summarize the approved tasks and milestones; they are not a forecast. Keep supporting files in <Link href="/evidence">Evidence</Link> when reporting progress.</p><details className="as-source"><summary>Schedule reference</summary><p>Context: {network.context_id}</p><p>Effective from: {network.effective_from}</p><p>{network.dependency_count} dependency links · {network.calendar_count} calendars</p></details></section>
      <section className="as-card" aria-labelledby="as-milestones"><div className="as-section-heading"><div><span className="eyebrow">Key dates</span><h2 id="as-milestones">Milestones</h2></div></div>{network.milestones.length ? <ul className="as-milestones">{[...network.milestones].sort((a,b) => a.planned_date.localeCompare(b.planned_date)).map(milestone => <li key={milestone.code}><div><strong>{milestone.name}</strong><small>{milestone.code}{milestone.material ? " · Material milestone" : ""} · {milestone.activity_code ? `Task ${milestone.activity_code}` : "No linked task"}</small></div><span>{date(milestone.planned_date)}</span></li>)}</ul> : <p>No milestones are recorded in this approved version.</p>}</section>
      <section className="as-card" aria-labelledby="as-tasks"><div className="as-section-heading"><div><span className="eyebrow">Task dates and logic</span><h2 id="as-tasks">Approved tasks</h2></div><label className="as-search">Find a task<input type="search" value={search} onChange={event => setSearch(event.target.value)} placeholder="Search task name or ID" /></label></div><p className="as-note" role="status">Showing {activities.length} of {network.activities.length} tasks</p><div className="as-table-scroll" role="region" aria-label="Approved task dates and dependencies" tabIndex={0}><table><thead><tr><th scope="col">Task</th><th scope="col">Planned start</th><th scope="col">Planned finish</th><th scope="col">Predecessors</th><th scope="col">Calendar / float</th></tr></thead><tbody>{activities.map(activity => { const predecessors = network.dependencies.filter(dependency => dependency.successor_code === activity.code); return <tr key={activity.code}><th scope="row"><strong>{activity.name}</strong><small>{activity.code}</small></th><td>{date(activity.planned_start)}</td><td>{date(activity.planned_finish)}</td><td>{predecessors.length ? predecessors.map(dependency => <div key={`${dependency.predecessor_code}/${dependency.relation_type}`}><strong>{dependency.predecessor_code}</strong> · {dependency.relation_type.toLowerCase().replaceAll("_", " ")} · lag {dependency.lag_days} days</div>) : "None recorded"}</td><td>{activity.calendar_id}<small>Float: {activity.total_float_days === null ? "Not provided" : `${activity.total_float_days} days`}</small></td></tr>; })}</tbody></table></div>{!activities.length ? <p>{query ? "No tasks match your search." : "No tasks are recorded in this approved version."}</p> : null}</section>
    </> : null}
    {connection && !loading ? <details className="as-card as-settings"><summary>Advanced settings: schedule analysis policy</summary><p>For project administrators. These rules control schedule analysis; they do not change the approved task dates.</p>{data?.policyError ? <p role="alert">Policy settings unavailable: {data.policyError}</p> : data?.policies.length ? <div className="as-policy-list">{data.policies.map(policy => <article key={policy.policy_version}><strong>{policy.policy_version}</strong><p>On-time tolerance: ±{policy.on_time_tolerance_days} days · Maximum schedule age: {policy.maximum_schedule_age_days} days</p><p>{policy.rationale}</p></article>)}</div> : <p>No analysis policy is recorded. An administrator must set one before policy-dependent analysis.</p>}<form onSubmit={createPolicy}><fieldset disabled={saving}><legend>Create an analysis policy version</legend><label>Version name<input name="policyVersion" required placeholder="e.g. Schedule policy v2" /></label><div className="as-form-pair"><label>On-time tolerance (days)<input name="tolerance" type="number" min="0" max="30" step="0.1" required aria-describedby="as-tolerance-help" /></label><label>Maximum schedule age (days)<input name="maximumAge" type="number" min="1" required aria-describedby="as-age-help" /></label></div><p id="as-tolerance-help" className="as-note">Allowed timing difference when assessing whether work is on time.</p><p id="as-age-help" className="as-note">How old the schedule data may be before analysis requires an update.</p><label>Reason for these rules<input name="rationale" required /></label><p className="as-note">Dependency evidence is required for consequences; calculated float is allowed. Saving creates a new immutable policy version and requires administrator access.</p><button type="submit">{saving ? "Saving policy…" : "Save new policy version"}</button></fieldset></form>{policyFailure ? <p role="alert">{policyFailure}</p> : null}</details> : null}
  </div>;
}

function date(value?: string): string {
  if (!value) return "Not recorded";
  // Calendar dates must not shift into the browser timezone.
  const parts = value.slice(0,10).split("-").map(Number);
  return parts.length === 3 && parts.every(Number.isFinite) ? new Intl.DateTimeFormat("en-GB", {day:"numeric", month:"short", year:"numeric", timeZone:"UTC"}).format(new Date(Date.UTC(parts[0],parts[1]-1,parts[2]))) : value;
}
function errorMessage(error: unknown) { return error instanceof Error ? error.message : "Schedule request failed"; }
async function readError(response: Response): Promise<string> { const payload = await response.json().catch(() => null) as {detail?: string | {msg?: string}[]} | null; return typeof payload?.detail === "string" ? payload.detail : Array.isArray(payload?.detail) ? payload.detail.map(item => item.msg).filter(Boolean).join("; ") : `Request failed (${response.status})`; }
