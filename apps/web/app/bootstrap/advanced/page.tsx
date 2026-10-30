import Link from "next/link";
import { BootstrapWorkbench } from "../workbench";

export default function AdvancedBootstrapPage() {
  return <main className="workbench-shell planning-guide">
    <header className="workbench-heading"><div><span className="eyebrow">BOQ to approved schedule</span><h1>Review your project schedule</h1><p className="lede">Start with your BOQ. We’ll guide you through the inputs, checks and approval.</p></div><Link className="quiet-link" href="/bootstrap">Only need an Excel draft? →</Link></header>
    <BootstrapWorkbench />
  </main>;
}
