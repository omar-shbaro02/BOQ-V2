import Link from "next/link";
import { BootstrapWorkbench } from "../workbench";

export default function AdvancedBootstrapPage() {
  return <main className="workbench-shell">
    <header className="workbench-heading"><div><span className="eyebrow">Advanced planning workflow</span><h1>Schedule bootstrap</h1><p className="lede">Governed review, validation, and authorization.</p></div><Link className="quiet-link" href="/bootstrap">Simple Excel export</Link></header>
    <BootstrapWorkbench />
  </main>;
}
