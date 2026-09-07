import Link from "next/link";

import { SignalInbox } from "./signal-inbox";

export default function SignalsPage() {
  return (
    <main className="workbench-shell">
      <Link className="back-link" href="/">
        ← Decision Intelligence home
      </Link>
      <section className="workbench-heading">
        <div>
          <div className="eyebrow">Phase 3 · attention routing</div>
          <h1 className="workbench-title">Signal Inbox</h1>
        </div>
        <p>
          Screen deterministic observations before they consume management attention. A signal is
          not a decision case, and a correlation suggestion does nothing until a person reviews it.
        </p>
      </section>
      <SignalInbox />
    </main>
  );
}
