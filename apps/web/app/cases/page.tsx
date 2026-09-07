import Link from "next/link";

import { CaseCenter } from "./case-center";

export default function CasesPage() {
  return (
    <main className="workbench-shell">
      <Link className="back-link" href="/">
        ← Decision Intelligence home
      </Link>
      <section className="workbench-heading">
        <div>
          <div className="eyebrow">Phase 4 · governed case assembly</div>
          <h1 className="workbench-title">Decision Cases</h1>
        </div>
        <p>
          Assemble evidence, freeze reproducible snapshots, expose exact limitations, and advance
          lifecycle only when readiness and human authority allow it.
        </p>
      </section>
      <CaseCenter />
    </main>
  );
}
