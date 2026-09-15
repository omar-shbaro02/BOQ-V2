import Link from "next/link";

import { DecisionCenter } from "./decision-center";

export default function DecisionCenterPage() {
  return (
    <main className="workbench-shell decision-center-shell">
      <Link className="back-link" href="/">
        ← Decision Intelligence home
      </Link>
      <section className="workbench-heading">
        <div>
          <div className="eyebrow">Phase 12 · governed management attention</div>
          <h1 className="workbench-title">Decision Center</h1>
        </div>
        <p>
          Review priority, urgency, readiness, authority, recommendation, human disposition, and
          the next governed action without collapsing their meanings.
        </p>
      </section>
      <DecisionCenter />
    </main>
  );
}
