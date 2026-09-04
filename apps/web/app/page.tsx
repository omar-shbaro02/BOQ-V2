import { DispositionValues, SCHEMA_VERSION } from "@/src/generated/taxonomies";
import Link from "next/link";

export default function Home() {
  return (
    <main>
      <section className="eyebrow">VAI · Project Control</section>
      <h1>Decision Intelligence, governed from evidence to action.</h1>
      <p className="lede">
        The Decision Center will reconcile execution evidence, authorized constraints, and
        credible forecasts without confusing a system recommendation with a human decision.
      </p>
      <section className="panel" aria-labelledby="phase-heading">
        <div>
          <span className="label">Current build</span>
          <h2 id="phase-heading">Phase 2 · Evidence workbench</h2>
        </div>
        <div className="panel-actions">
          <Link className="quiet-link" href="/setup">
            Configure project
          </Link>
          <Link className="status" href="/evidence">
            Open workbench →
          </Link>
        </div>
      </section>
      <section aria-labelledby="dispositions-heading">
        <h2 id="dispositions-heading">Allowed recommendations</h2>
        <ul className="dispositions">
          {DispositionValues.map((value) => (
            <li key={value}>{value.replaceAll("_", " ")}</li>
          ))}
        </ul>
      </section>
      <footer>Shared contract v{SCHEMA_VERSION} · Human authority remains explicit.</footer>
    </main>
  );
}
