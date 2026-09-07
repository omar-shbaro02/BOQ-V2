import Link from "next/link";

import { ForecastWorkbench } from "./forecast-workbench";

export default function ForecastPage() {
  return (
    <main className="workbench-shell">
      <Link className="back-link" href="/">← Decision Intelligence home</Link>
      <section className="workbench-heading">
        <div><div className="eyebrow">Phase 8 · bounded projections</div><h1 className="workbench-title">Forecast & Scenarios</h1></div>
        <p>Review immutable forecast history, horizon confidence, ranges, expiry, and recalculation state. Forecasts and hypothetical scenarios remain structurally separate from facts and authorized controls.</p>
      </section>
      <ForecastWorkbench />
    </main>
  );
}
