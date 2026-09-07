import Link from "next/link";

import { ScheduleWorkbench } from "./schedule-workbench";

export default function SchedulePage() {
  return (
    <main className="workbench-shell">
      <Link className="back-link" href="/">
        ← Decision Intelligence home
      </Link>
      <section className="workbench-heading">
        <div>
          <div className="eyebrow">Phase 6 · authorized network</div>
          <h1 className="workbench-title">Schedule Intelligence</h1>
        </div>
        <p>
          Inspect the current authorized activity network, calendars, constraints, dependencies,
          milestones, and visible schedule-quality policy before assessing a Decision Case.
        </p>
      </section>
      <ScheduleWorkbench />
    </main>
  );
}
