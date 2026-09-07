import Link from "next/link";

import { CostWorkbench } from "./cost-workbench";

export default function CostPage() {
  return (
    <main className="workbench-shell">
      <Link className="back-link" href="/">← Decision Intelligence home</Link>
      <section className="workbench-heading">
        <div><div className="eyebrow">Phase 7 · commercial controls</div><h1 className="workbench-title">Cost Intelligence</h1></div>
        <p>Inspect the authorized budget, normalize immutable cost evidence, and review the visible alignment and forecast policy without treating commercial timing as liability.</p>
      </section>
      <CostWorkbench />
    </main>
  );
}
