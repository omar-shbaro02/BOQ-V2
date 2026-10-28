"use client";

import { useState } from "react";
import { ProgressBasisValues, type ProgressBasis } from "../../src/generated/taxonomies";

export type ControlObject = { id: string; code: string; name: string; object_type: string; active: boolean };
type Point = { as_of: string; numerator: string; denominator: string; unit: string; measurement_basis: ProgressBasis };
export type ControlInput = { activity_code: string; controlled_object_id: string; measurement_basis: ProgressBasis; progress_plan: Point[]; source_reference: string };

export function ControlInputs({ activities, objects, inputs, onChange, disabled }: {
  activities: { activity_code: string; activity_name: string }[];
  objects: ControlObject[]; inputs: ControlInput[]; onChange: (inputs: ControlInput[]) => void; disabled: boolean;
}) {
  const [points, setPoints] = useState<Point[]>([]);
  const [basis, setBasis] = useState<ProgressBasis>("PHYSICAL_VERIFIED");
  const [message, setMessage] = useState("No quantities are inferred. Enter only sourced planned points; omitted plans remain unknown.");
  return <section aria-label="Planned progress control inputs" className="source-review">
    <h3>Planned progress control inputs</h3>
    <p>Map a calculated activity to an active project work package or activity. These are proposed inputs until separate human authorization. Planned quantities never verify actual progress.</p>
    <p role="status">{message}</p>
    <form className="stack-form compact" onSubmit={(event) => {
      event.preventDefault(); const form = new FormData(event.currentTarget);
      const point: Point = { as_of: String(form.get("asOf")), numerator: String(form.get("numerator")), denominator: String(form.get("denominator")), unit: String(form.get("unit")).trim(), measurement_basis: basis };
      if (Number(point.numerator) > Number(point.denominator)) { setMessage("Planned quantity cannot exceed its denominator."); return; }
      if (points.some((item) => item.as_of === point.as_of)) { setMessage("Each planned date must be unique."); return; }
      if (points.some((item) => item.unit !== point.unit || Number(item.denominator) !== Number(point.denominator))) { setMessage("Use one unit and denominator for this activity plan."); return; }
      setPoints([...points, point].sort((a, b) => a.as_of.localeCompare(b.as_of)));
      event.currentTarget.reset(); setMessage("Planned point staged locally. Stage the complete control input below to include it in review.");
    }}>
      <label>Plan measurement basis<select value={basis} disabled={disabled} onChange={(event) => { setBasis(event.target.value as ProgressBasis); setPoints([]); setMessage("Basis changed; enter the planned points for this basis."); }}>{ProgressBasisValues.map((value) => <option key={value}>{value}</option>)}</select></label>
      <label>Planned date<input name="asOf" type="date" required /></label>
      <div className="form-pair"><label>Planned quantity<input name="numerator" type="number" min="0" step="any" required /></label><label>Total planned quantity<input name="denominator" type="number" min="0.000000001" step="any" required /></label></div>
      <label>Plan unit<input name="unit" maxLength={30} required /></label>
      <button disabled={disabled} type="submit">Add planned point</button>
    </form>
    {points.length > 0 && <div className="mini-ledger">{points.map((point) => <div key={point.as_of}><span>{point.as_of} · {point.numerator}/{point.denominator} {point.unit} · {point.measurement_basis}</span><button disabled={disabled} type="button" onClick={() => setPoints(points.filter((item) => item.as_of !== point.as_of))}>Remove planned point {point.as_of}</button></div>)}</div>}
    <form className="stack-form compact" onSubmit={(event) => {
      event.preventDefault(); const form = new FormData(event.currentTarget);
      const activity_code = String(form.get("activity")); const controlled_object_id = String(form.get("object"));
      if (inputs.some((item) => item.activity_code !== activity_code && item.controlled_object_id === controlled_object_id)) { setMessage("This controlled object already has an activity plan. Remove that mapping before replacing it."); return; }
      onChange([...inputs.filter((item) => item.activity_code !== activity_code), { activity_code, controlled_object_id, measurement_basis: basis, progress_plan: points, source_reference: String(form.get("source")).trim() }]);
      setPoints([]); event.currentTarget.reset(); setMessage("Control input staged. Submit the planner review to preserve it, then obtain separate authorization.");
    }}>
      <label>Control activity<select name="activity" required><option value="">Select calculated activity</option>{activities.map((item) => <option key={item.activity_code} value={item.activity_code}>{item.activity_code} · {item.activity_name}</option>)}</select></label>
      <label>Controlled work package or activity<select name="object" required><option value="">Select controlled object</option>{objects.filter((item) => item.active && ["WORK_PACKAGE", "ACTIVITY"].includes(item.object_type)).map((item) => <option key={item.id} value={item.id}>{item.code} · {item.name}</option>)}</select></label>
      <label>Control plan source reference<input name="source" minLength={3} maxLength={300} required /></label>
      <p>{points.length} planned points staged for this input. An empty plan preserves an unknown planned quantity.</p>
      <button type="submit" disabled={disabled || activities.length === 0}>Stage control input</button>
    </form>
    {inputs.length > 0 && <div className="mini-ledger"><strong>{inputs.length} staged control inputs</strong>{inputs.map((item) => <div key={item.activity_code}><span>{item.activity_code} → {objects.find((object) => object.id === item.controlled_object_id)?.code} · {item.measurement_basis} · {item.source_reference}</span>{item.progress_plan.map((point) => <small key={point.as_of}>{point.as_of} · {point.numerator}/{point.denominator} {point.unit}</small>)}<button type="button" disabled={disabled} onClick={() => onChange(inputs.filter((input) => input.activity_code !== item.activity_code))}>Remove control input {item.activity_code}</button></div>)}</div>}
  </section>;
}
