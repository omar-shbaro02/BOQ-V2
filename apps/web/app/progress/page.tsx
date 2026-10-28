import Link from "next/link";

import { ProgressWorkbench } from "./progress-workbench";
import { SnapshotComposer } from "./snapshot-composer";

export default function ProgressPage() {
  return (
    <main className="workbench-shell">
      <Link className="back-link" href="/">
        ← Decision Intelligence home
      </Link>
      <section className="workbench-heading">
        <div>
          <div className="eyebrow">Schedule reporting · progress truth</div>
          <h1 className="workbench-title">Project Progress</h1>
        </div>
        <p>
          Update the generated Excel workbook, upload it here, and see what is early, on time, late,
          or still missing. Deadline impact remains a visible planning scenario until reviewed.
        </p>
      </section>
      <ProgressWorkbench />
      <SnapshotComposer />
    </main>
  );
}
