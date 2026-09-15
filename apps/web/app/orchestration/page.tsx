import Link from "next/link";
import { OrchestrationWorkbench } from "./orchestration-workbench";

export default function OrchestrationPage() {
  return <main className="workbench-shell">
    <Link className="back-link" href="/">← Decision Intelligence home</Link>
    <section className="workbench-heading"><div><div className="eyebrow">Phase 10 · bounded coordination</div><h1 className="workbench-title">Specialist Orchestration</h1></div><p>Assemble snapshot-bound specialist results into a deterministic recommendation brief. Review stops, contradictions, alternatives, and authority boundaries before human review.</p></section>
    <OrchestrationWorkbench />
  </main>;
}
