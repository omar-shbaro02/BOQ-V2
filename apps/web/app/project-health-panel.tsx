import Link from "next/link";

type Dimension = {
  status: string; rule: string; value: string | null; thresholds: Record<string, unknown>;
  input_refs: string[]; data_date: string; confidence: string | null; limitations: string[];
  review_route: { url: string } | null;
};
export type ProjectHealth = {
  status?: string; policy?: { version: string; owner_actor_id: string; rationale: string } | null;
  semantic_notice?: string; limitations?: string[]; dimensions?: Record<string, Dimension>;
  packages?: { controlled_object_id: string; controlled_object_code: string; weight: string;
    status: string; dimensions: Record<string, Dimension> }[];
};

export function ProjectHealthPanel({ health, timezone = "UTC" }: { health?: ProjectHealth; timezone?: string }) {
  return <section className="dashboard-card" aria-labelledby="project-health-title">
    <div className="dashboard-card-head"><div><span className="section-kicker">Explainable project health</span><h2 id="project-health-title">Management attention: {health?.status ?? "UNKNOWN"}</h2></div><Link href="/signals">Review signals →</Link></div>
    <p>{health?.semantic_notice ?? "A project RAG policy and frozen source inputs are required. Missing information is Unknown."}</p>
    {health?.policy ? <p>Policy {health.policy.version} · owner {health.policy.owner_actor_id}. {health.policy.rationale}</p> : null}
    <div className="metric-grid">{Object.entries(health?.dimensions ?? {}).map(([name, result]) => <DimensionView key={name} name={name} result={result} timezone={timezone} />)}</div>
    {health?.packages?.map((item) => <details key={item.controlled_object_id}>
      <summary>{item.controlled_object_code} · {item.status} · weight {(Number(item.weight) * 100).toFixed(1)}%</summary>
      <div className="metric-grid">{Object.entries(item.dimensions).map(([name, result]) => <DimensionView key={name} name={name} result={result} timezone={timezone} />)}</div>
    </details>)}
    {health?.limitations?.map((limitation) => <p className="panel-note" key={limitation}>{limitation.replaceAll("_", " ")}</p>)}
  </section>;
}

function DimensionView({ name, result, timezone }: { name: string; result: Dimension; timezone: string }) {
  return <article className="metric-card health-dimension">
    <span>{name}</span><strong>{result.status}</strong>
    {result.review_route ? <Link href={result.review_route.url}>Review {name} evidence and decision route →</Link> : null}
    <details><summary>Rule and evidence basis</summary>
      <p>{result.rule.replaceAll("_", " ")}{result.value === null ? " · value Unknown" : ` · value ${result.value}`}</p>
      <p>Data date {new Date(result.data_date).toLocaleString(undefined, { timeZone: timezone })} {timezone} · confidence {result.confidence ?? "Unknown"}</p>
      {Object.entries(result.thresholds).map(([key, value]) => <p key={key}>{key.replaceAll("_", " ")}: {Array.isArray(value) ? value.join(", ") : String(value)}</p>)}
      {result.limitations.map((limitation) => <p key={limitation}>{limitation}</p>)}
      <p>Source references: {result.input_refs.length ? result.input_refs.join(", ") : "Unavailable"}</p>
    </details>
  </article>;
}
