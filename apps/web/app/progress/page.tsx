import Link from "next/link";

import { ProgressWorkbench } from "./progress-workbench";

export default function ProgressPage() {
  return (
    <main className="workbench-shell">
      <Link className="back-link" href="/">
        ← Decision Intelligence home
      </Link>
      <section className="workbench-heading">
        <div>
          <div className="eyebrow">Phase 5 · progress truth</div>
          <h1 className="workbench-title">Progress Reconciliation</h1>
        </div>
        <p>
          Normalize evidence-backed progress without collapsing reported, executed, verified, or
          accepted gates. Comparisons require compatible bases and authorized plan lineage.
        </p>
      </section>
      <ProgressWorkbench />
    </main>
  );
}
