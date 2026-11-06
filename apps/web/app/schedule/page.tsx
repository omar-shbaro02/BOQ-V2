import { ScheduleWorkbench } from "./schedule-workbench";

export default function SchedulePage() {
  return <main className="workbench-shell approved-schedule-page">
    <header className="as-heading"><span className="eyebrow">Your agreed project plan</span><h1>Approved schedule</h1><p>Check the approved dates and milestones, then report actual progress against this plan.</p></header>
    <ScheduleWorkbench />
  </main>;
}
