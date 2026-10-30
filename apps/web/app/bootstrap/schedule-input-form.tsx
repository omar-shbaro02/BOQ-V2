"use client";

import { useState } from "react";

export function JsonAction({ idLabel, suggested, placeholder, button, disabled, validationOwner, onSubmit }: {
  idLabel: string; suggested?: string; placeholder: string; button: string; disabled: boolean;
  validationOwner: string; onSubmit: (id: string, body: unknown) => Promise<void>;
}) {
  const [advanced, setAdvanced] = useState(false);
  const [error, setError] = useState("");
  const calendar = button === "Create logic";
  return <form className="stack-form compact" aria-label={idLabel} onSubmit={event => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    try {
      let body: unknown;
      if (advanced) body = JSON.parse(String(form.get("json")));
      else if (calendar) {
        const weekdays = form.getAll("weekday").map(Number);
        if (!weekdays.length) throw new Error("Select at least one working day.");
        const holidays = String(form.get("holidays") ?? "").split(/[\n,]/).map(value => value.trim()).filter(Boolean);
        if (holidays.some(value => !/^\d{4}-\d{2}-\d{2}$/.test(value))) throw new Error("Enter holiday dates as YYYY-MM-DD, one per line.");
        body = { validation_owner: form.get("owner"), calendar: { calendar_id: "PROJECT", name: form.get("calendarName"), working_weekdays: weekdays, working_hours_per_day: Number(form.get("hours")), holidays, review_state: "ACCEPTED" }, dependencies: [], milestones: [], constraints: [], sequence_templates: [] };
      } else body = { validation_owner: form.get("owner"), duration_inputs: [], productivity_inputs: [] };
      setError("");
      if (suggested) void onSubmit(suggested, body);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Check the entered values."); }
  }}>
    <details className="planning-reference"><summary>Selected record · technical reference</summary><code>{suggested ?? "Complete the previous step first"}</code></details>
    <label className="planning-mode"><input type="checkbox" checked={advanced} onChange={event => { setAdvanced(event.target.checked); setError(""); }} />Advanced: edit structured inputs</label>
    {advanced ? <><label>Governed inputs JSON<textarea name="json" defaultValue={placeholder.replace("planner@example.com", validationOwner)} key={validationOwner} rows={7} required /></label><small className="planning-field-help">For experienced planners or integrations. All inputs still pass the same validation and review gates.</small></> : <>
      <label>Responsible planner<input name="owner" defaultValue={validationOwner} key={validationOwner} minLength={3} required aria-describedby={calendar ? "calendar-owner-help" : "draft-owner-help"} /></label>
      <small id={calendar ? "calendar-owner-help" : "draft-owner-help"} className="planning-field-help">The account responsible for checking these planning inputs. Your signed-in account is filled in; change it only to the accountable planner.</small>
      {calendar ? <>
        <label>Working calendar name<input name="calendarName" placeholder="e.g. Main site working calendar" minLength={2} required /></label>
        <fieldset className="planning-weekdays"><legend>Which days does the site work?</legend>{["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"].map((day, index) => <label key={day}><input type="checkbox" name="weekday" value={index} />{day}</label>)}</fieldset>
        <label>Working hours per day<input name="hours" type="number" min="0.01" max="24" step="any" placeholder="e.g. 8" required /></label>
        <label>Site holidays or closures (optional)<textarea name="holidays" placeholder="YYYY-MM-DD, one date per line" rows={3} /></label>
        <label className="planning-mode"><input type="checkbox" required />I have reviewed these working days, hours and closures.</label>
        <p className="planning-field-help">Task links are not inferred. Add dependencies and constraints in the planning corrections panel before approving the schedule, or enter them through advanced structured inputs.</p>
      </> : <p className="planning-field-help">This creates a task list, without inventing durations or productivity rates. Add supported planning inputs in the corrections panel, then calculate the dates.</p>}
    </>}
    <button disabled={disabled || !suggested}>{button}</button>
    {error ? <p role="alert">{error}</p> : null}
  </form>;
}
