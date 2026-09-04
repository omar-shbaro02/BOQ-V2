import Link from "next/link";

import { EvidenceWorkbench } from "./workbench";

export default function EvidencePage() {
  return (
    <main className="workbench-shell">
      <Link className="back-link" href="/">
        ← Decision Intelligence home
      </Link>
      <section className="workbench-heading">
        <div>
          <div className="eyebrow">Phase 2 · governed intake</div>
          <h1 className="workbench-title">Evidence Workbench</h1>
        </div>
        <p>
          Capture source artifacts and typed assertions. Reported claims remain reported until a
          reviewer creates a separate, linked verification result.
        </p>
      </section>
      <EvidenceWorkbench />
    </main>
  );
}
