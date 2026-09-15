import Link from "next/link";
import { ImpactWorkbench } from "./impact-workbench";

export default function ImpactPage() {
  return <main className="workbench-shell">
    <Link className="back-link" href="/">← Decision Intelligence home</Link>
    <section className="workbench-heading"><div><div className="eyebrow">Phase 9 · management attention</div><h1 className="workbench-title">Consequence & Priority</h1></div><p>Assess consequence, confidence, decision clocks, and priority against a frozen case snapshot. Review limitations and ranking reasons before drawing conclusions.</p></section>
    <ImpactWorkbench />
  </main>;
}
