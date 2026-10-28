"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { PlanningConfidenceValues, ProductivitySourceTypeValues, ScheduleConstraintTypeValues, ScheduleDependencyTypeValues } from "../../src/generated/taxonomies";

type Activity = { id: string; activity_code: string; activity_name: string; activity_type: string; work_package_id: string; duration_working_days: string | null; quantity: string | null; unit: string | null; boq_line_refs: string[]; responsible_role: string | null };
type Input = Record<string, unknown> & { work_package_id: string; activity_type?: string };
export type CorrectionDraft = {
  id: string; planning_structure_id: string; duration_inputs: Input[]; productivity_inputs: Input[];
  activities: Activity[]; assumptions: unknown[]; correction_history: Record<string, unknown> | null;
  source_version_id: string | null; source_version_number: number | null;
};
type Calendar = { calendar_id: string; name: string; working_weekdays: number[]; working_hours_per_day: string; holidays: string[]; review_state: string; source_reference?: string | null };
type Edge = { predecessor_activity_id: string; successor_activity_id: string; relation_type: string; lag_working_days: string; basis: string; source_reference: string; confidence: string; review_state: string; generated?: boolean };
type Milestone = { code: string; name: string; target_date: string; source_type: string; source_reference: string; feeds_from_activity_ids: string[]; material: boolean };
type Constraint = { activity_id: string; constraint_type: string; constraint_date: string; source_reference: string };
type Logic = { id: string; calendar: Calendar; dependencies: Edge[]; sequence_templates: Edge[]; milestones: Milestone[]; constraints: Constraint[]; assumptions: { source_basis?: string }[] };
type LogicInput = { calendar: Calendar | null; dependencies: Edge[]; sequence_templates: Edge[]; milestones: Milestone[]; constraints: Constraint[]; validation_owner: string };

export function MaterialCorrection({ api, connection, draftId, disabled, onBusy, onSaved }: {
  api: string; connection: { actorId: string; organizationId: string; projectId: string };
  draftId?: string; disabled: boolean; onBusy: (busy: boolean) => void;
  onSaved: (draft: CorrectionDraft, logicId: string | null) => void;
}) {
  const [draft, setDraft] = useState<CorrectionDraft | null>(null);
  const [logic, setLogic] = useState<Logic | null>(null);
  const [logicInput, setLogicInput] = useState<LogicInput | null>(null);
  const [durations, setDurations] = useState<Input[]>([]);
  const [productivity, setProductivity] = useState<Input[]>([]);
  const [message, setMessage] = useState("Load a draft to inspect its existing basis before staging changes.");
  const [working, setWorking] = useState(false);
  const abort = useRef<AbortController | null>(null);
  useEffect(() => () => abort.current?.abort(), []);
  const base = `${api}/api/v1/projects/${connection.projectId}/bootstrap`;
  const blocked = working || disabled;
  function values(event: FormEvent<HTMLFormElement>) { event.preventDefault(); return new FormData(event.currentTarget); }
  async function request(path: string, signal: AbortSignal, body?: unknown) {
    const response = await fetch(`${base}${path}`, { signal, method: body === undefined ? "GET" : "POST", headers: {
      "Content-Type": "application/json", "X-VAI-Actor-ID": connection.actorId, "X-VAI-Organization-ID": connection.organizationId,
      ...(body === undefined ? {} : { "Idempotency-Key": crypto.randomUUID() }),
    }, body: body === undefined ? undefined : JSON.stringify(body) });
    if (!response.ok) {
      const payload = await response.json().catch(() => null);
      throw new Error(typeof payload?.detail === "string" ? payload.detail : `Planning inputs could not be loaded or saved (${response.status}).`);
    }
    return response.json();
  }
  async function run(action: (signal: AbortSignal) => Promise<void>) {
    if (blocked) return;
    abort.current?.abort(); const controller = new AbortController(); abort.current = controller;
    setWorking(true); onBusy(true);
    try { await action(controller.signal); }
    catch (error) { if (!controller.signal.aborted) setMessage(error instanceof Error ? error.message : "Correction failed."); }
    finally { onBusy(false); if (!controller.signal.aborted) setWorking(false); }
  }
  function originalLogic(owner: string): LogicInput | null {
    if (!logic) return null;
    return { calendar: logic.assumptions.some((item) => item.source_basis === "VISIBLE_DEFAULT_ASSUMPTION") ? null : logic.calendar,
      dependencies: logic.dependencies.filter((edge) => !edge.generated), sequence_templates: logic.sequence_templates,
      milestones: logic.milestones, constraints: logic.constraints, validation_owner: owner };
  }
  const editable = [
    ...(logicInput?.dependencies ?? logic?.dependencies.filter((edge) => !edge.generated) ?? []).map((edge, index) => ({ edge, index, kind: "dependencies" as const })),
    ...(logicInput?.sequence_templates ?? logic?.sequence_templates ?? []).map((edge, index) => ({ edge, index, kind: "sequence_templates" as const })),
  ];
  const activityName = (id: string) => draft?.activities.find((item) => item.id === id)?.activity_name ?? id;
  return <section className="workbench-card full-width source-review" aria-label="Material planning corrections">
    <h2>Correct duration, productivity, calendar or logic</h2>
    <p>Changes create a new immutable draft with original/revised inputs, actor and reason. Recalculate CPM, review the new calculation, and obtain separate authority before replacing a controlling schedule.</p>
    <form className="stack-form compact" onSubmit={(event) => {
      const form = values(event); void run(async (signal) => {
        setDraft(null); setLogic(null); setLogicInput(null); setDurations([]); setProductivity([]);
        const id = String(form.get("draftId"));
        const detail = await request(`/schedule-drafts/${id}`, signal) as CorrectionDraft;
        const response = await fetch(`${base}/schedule-drafts/${id}/logic`, { signal, headers: { "X-VAI-Actor-ID": connection.actorId, "X-VAI-Organization-ID": connection.organizationId } });
        if (!response.ok && response.status !== 404) throw new Error("Stored logic could not be loaded. Retry before correcting.");
        const storedLogic = response.ok ? await response.json() as Logic : null;
        if (signal.aborted) return;
        setDraft(detail); setLogic(storedLogic); setDurations(detail.duration_inputs); setProductivity(detail.productivity_inputs);
        setMessage("Stored planning inputs loaded. Stage each correction and supply its basis.");
      });
    }}><label>Draft to correct<input name="draftId" defaultValue={draftId} key={draftId} required /></label>
      <button disabled={blocked}>Load correction inputs</button></form>
    <p role="status">{working ? "Working…" : message}</p>
    {draft && <>
      <p>Loaded draft <code>{draft.id}</code> · BOQ version {draft.source_version_number ?? "Unknown"}. {draft.activities.length} activities. {logic ? "Existing logic will be copied with new activity references." : "No logic exists; supply it after creating the corrected draft."}</p>
      <div className="mini-ledger">{draft.activities.map((activity) => <div key={activity.id}><strong>{activity.activity_code} · {activity.activity_name}</strong>
        <span>Original duration {activity.duration_working_days ?? "Unknown"} working days · quantity {activity.quantity ?? "Unknown"} {activity.unit ?? "unit unknown"}</span></div>)}</div>
      <form className="stack-form compact" onSubmit={(event) => {
        const form = values(event); const activity = draft.activities.find((item) => item.id === form.get("activity"));
        if (!activity) return;
        const input = { work_package_id: activity.work_package_id, activity_type: activity.activity_type,
          duration_working_days: String(form.get("days")), basis: "EXPLICIT_PROJECT_DURATION", source_reference: String(form.get("basis")), confidence: String(form.get("confidence")) };
        setDurations((current) => [...current.filter((item) => item.work_package_id !== activity.work_package_id || item.activity_type !== activity.activity_type), input]);
        setMessage(`Staged explicit duration for ${activity.activity_code}. Save a successor to retain the correction.`);
      }}>
        <h3>Explicit duration correction</h3>
        <label>Duration activity<select name="activity" required><option value="">Choose activity</option>{draft.activities.map((item) => <option key={item.id} value={item.id}>{item.activity_code} · {item.activity_name}</option>)}</select></label>
        <label>Working-day duration<input name="days" type="number" min="0.000001" step="any" required /></label>
        <label>Duration source or basis<input name="basis" minLength={3} maxLength={300} required /></label>
        <Confidence name="confidence" label="Duration confidence" />
        <button disabled={blocked}>Stage duration correction</button>
      </form>
      <form className="stack-form compact" onSubmit={(event) => {
        const form = values(event); const activity = draft.activities.find((item) => item.id === form.get("activity"));
        if (!activity || !activity.unit) return;
        setProductivity((current) => [...current.filter((item) => item.work_package_id !== activity.work_package_id), {
          work_package_id: activity.work_package_id, rate_per_working_day: String(form.get("rate")), quantity_unit: activity.unit,
          source_type: String(form.get("sourceType")), source_reference: String(form.get("basis")), source_version: String(form.get("version")), confidence: String(form.get("confidence")), review_state: "REVISED",
        }]);
        setDurations((current) => current.filter((item) => item.work_package_id !== activity.work_package_id || item.activity_type !== "EXECUTION"));
        setMessage(`Staged productivity for ${activity.activity_code}; its explicit execution-duration override was removed.`);
      }}>
        <h3>Productivity correction</h3><p>A supplied rate uses the stored compatible quantity/unit. Staging a rate removes this execution activity’s explicit duration override.</p>
        <label>Productivity activity<select name="activity" required><option value="">Choose execution activity</option>{draft.activities.filter((item) => item.activity_type === "EXECUTION" && item.quantity !== null && item.unit).map((item) => <option key={item.id} value={item.id}>{item.activity_code} · {item.quantity} {item.unit}</option>)}</select></label>
        <label>Quantity per working day<input name="rate" type="number" min="0.000001" step="any" required /></label>
        <label>Productivity source type<select name="sourceType" required><option value="">Choose basis</option>{ProductivitySourceTypeValues.map((value) => <option key={value}>{value}</option>)}</select></label>
        <label>Productivity source reference<input name="basis" minLength={3} maxLength={300} required /></label>
        <label>Productivity source version<input name="version" maxLength={80} required /></label>
        <Confidence name="confidence" label="Productivity confidence" />
        <button disabled={blocked}>Stage productivity correction</button>
      </form>
      {logic && <>
        <form className="stack-form compact" onSubmit={(event) => {
          const form = values(event); const current = logicInput ?? originalLogic(connection.actorId)!;
          setLogicInput({ ...current, calendar: { calendar_id: logic.calendar.calendar_id, name: String(form.get("calendarName")),
            working_weekdays: form.getAll("weekday").map(Number), working_hours_per_day: String(form.get("hours")),
            holidays: String(form.get("holidays")).split(",").map((value) => value.trim()).filter(Boolean), review_state: "REVISED", source_reference: String(form.get("basis")),
          } });
          setMessage("Calendar correction staged with an explicit human-reviewed source. All working dates require recalculation.");
        }}>
          <h3>Calendar correction</h3><label>Calendar name<input name="calendarName" defaultValue={logic.calendar.name} required /></label>
          <fieldset><legend>Working weekdays</legend>{["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"].map((day, index) => <label key={day}><input name="weekday" type="checkbox" value={index} defaultChecked={logic.calendar.working_weekdays.includes(index)} />{day}</label>)}</fieldset>
          <label>Hours per working day<input name="hours" type="number" min="0.000001" max="24" step="any" defaultValue={logic.calendar.working_hours_per_day} required /></label>
          <label>Holiday dates (YYYY-MM-DD, comma separated)<input name="holidays" defaultValue={logic.calendar.holidays.join(", ")} /></label>
          <label>Reviewed calendar source<input name="basis" minLength={3} maxLength={300} required /></label>
          <button disabled={blocked}>Stage calendar correction</button>
        </form>
        {editable.length > 0 && <form className="stack-form compact" onSubmit={(event) => {
          const form = values(event); const selected = editable[Number(form.get("edge"))]; if (!selected) return;
          const current = logicInput ?? originalLogic(connection.actorId)!;
          const edges = [...current[selected.kind]];
          edges[selected.index] = { ...selected.edge, relation_type: String(form.get("relation")), lag_working_days: String(form.get("lag")), source_reference: String(form.get("basis")), confidence: String(form.get("confidence")), review_state: "REVISED" };
          setLogicInput({ ...current, [selected.kind]: edges }); setMessage("Dependency correction staged. Cycle, prerequisite and CPM validation still apply.");
        }}>
          <h3>Dependency correction</h3><label>Dependency to correct<select name="edge" required><option value="">Choose relationship</option>{editable.map(({ edge }, index) => <option key={index} value={index}>{activityName(edge.predecessor_activity_id)} → {activityName(edge.successor_activity_id)} · {edge.relation_type} · lag {edge.lag_working_days}</option>)}</select></label>
          <label>Corrected relationship<select name="relation" required><option value="">Choose relationship</option>{ScheduleDependencyTypeValues.map((value) => <option key={value}>{value}</option>)}</select></label>
          <label>Corrected lag (working days)<input name="lag" type="number" step="any" required /></label>
          <label>Dependency correction basis<input name="basis" minLength={3} maxLength={300} required /></label>
          <Confidence name="confidence" label="Dependency confidence" />
          <button disabled={blocked}>Stage dependency correction</button>
        </form>}
        {logic.milestones.length > 0 && <form className="stack-form compact" onSubmit={(event) => {
          const form = values(event); const current = logicInput ?? originalLogic(connection.actorId)!;
          const milestones = [...current.milestones]; const index = Number(form.get("milestone"));
          if (!milestones[index]) return;
          milestones[index] = { ...milestones[index], target_date: String(form.get("date")), source_reference: String(form.get("basis")) };
          setLogicInput({ ...current, milestones }); setMessage("Milestone date correction staged as a proposal. Feeder and deadline validation remain required.");
        }}>
          <h3>Milestone date correction</h3><p>Changing a proposed date does not establish contractual authority or entitlement.</p>
          <label>Milestone to correct<select name="milestone" required><option value="">Choose milestone</option>{(logicInput?.milestones ?? logic.milestones).map((item, index) => <option key={item.code} value={index}>{item.code} · {item.name} · {item.target_date} · {item.source_type}</option>)}</select></label>
          <label>Corrected milestone target<input name="date" type="date" required /></label>
          <label>Milestone correction source<input name="basis" minLength={3} maxLength={300} required /></label>
          <button disabled={blocked}>Stage milestone date correction</button>
        </form>}
        {logic.constraints.length > 0 && <form className="stack-form compact" onSubmit={(event) => {
          const form = values(event); const current = logicInput ?? originalLogic(connection.actorId)!;
          const constraints = [...current.constraints]; const index = Number(form.get("constraint"));
          if (!constraints[index]) return;
          constraints[index] = { ...constraints[index], constraint_type: String(form.get("type")), constraint_date: String(form.get("date")), source_reference: String(form.get("basis")) };
          setLogicInput({ ...current, constraints }); setMessage("Constraint correction staged as a proposal. CPM must validate its effect before review.");
        }}>
          <h3>Constraint correction</h3><label>Constraint to correct<select name="constraint" required><option value="">Choose constraint</option>{(logicInput?.constraints ?? logic.constraints).map((item, index) => <option key={index} value={index}>{activityName(item.activity_id)} · {item.constraint_type} · {item.constraint_date}</option>)}</select></label>
          <label>Corrected constraint type<select name="type" required><option value="">Choose constraint type</option>{ScheduleConstraintTypeValues.map((value) => <option key={value}>{value}</option>)}</select></label>
          <label>Corrected constraint date<input name="date" type="date" required /></label>
          <label>Constraint correction source<input name="basis" minLength={3} maxLength={300} required /></label>
          <button disabled={blocked}>Stage constraint correction</button>
        </form>}
      </>}
      <details><summary>Review complete proposed correction inputs</summary><pre>{JSON.stringify({ duration_inputs: durations, productivity_inputs: productivity, logic_inputs: logicInput ?? "Preserve existing logic and assumptions" }, null, 2)}</pre></details>
      <form className="stack-form compact" onSubmit={(event) => {
        const form = values(event); void run(async (signal) => {
          const owner = String(form.get("owner"));
          const result = await request(`/schedule-drafts/${draft.id}/corrections`, signal, {
            expected_structure_version_id: draft.planning_structure_id, expected_logic_proposal_id: logic?.id ?? null,
            reason: form.get("reason"), draft_inputs: { validation_owner: owner, duration_inputs: durations, productivity_inputs: productivity },
            logic_inputs: logicInput ? { ...logicInput, validation_owner: owner } : null,
          });
          const detail = await request(`/schedule-drafts/${result.id}`, signal) as CorrectionDraft;
          const response = await fetch(`${base}/schedule-drafts/${result.id}/logic`, { signal, headers: { "X-VAI-Actor-ID": connection.actorId, "X-VAI-Organization-ID": connection.organizationId } });
          if (!response.ok && response.status !== 404) throw new Error("Correction was saved; reload the returned draft before continuing.");
          const storedLogic = response.ok ? await response.json() as Logic : null;
          if (!signal.aborted) onSaved(detail, storedLogic?.id ?? null);
        });
      }}><label>Correction validation owner<input name="owner" defaultValue={connection.actorId} minLength={3} required /></label>
        <label>Reason for material correction<input name="reason" minLength={10} maxLength={2000} required /></label>
        <button disabled={blocked}>Save corrected draft for recalculation</button></form>
    </>}
  </section>;
}

function Confidence({ name, label }: { name: string; label: string }) {
  return <label>{label}<select name={name} required><option value="">Choose confidence</option>{PlanningConfidenceValues.map((value) => <option key={value}>{value}</option>)}</select></label>;
}
