"use client";

import { useEffect, useRef, useState } from "react";

type Connection = { actorId: string; organizationId: string; projectId: string };
type Source = { id: string; version_number: number; extraction_status: string };
type Finding = { code?: string; message?: string; [key: string]: unknown };
type SourceRow = {
  id: string; sheet_name: string | null; page_number: number | null; row_number: number | null;
  original_text: string | null; raw_values: unknown[]; extraction_confidence: string;
  region: Record<string, unknown> | null; warnings: Finding[];
};
type SourceDetail = Source & {
  artifact_id: string; content_sha256: string; parser_name: string; parser_version: string;
  extraction_confidence: string; structure_manifest: Record<string, unknown>[]; warnings: Finding[];
  rows: SourceRow[];
};
type Line = {
  id: string; stable_line_id: string; source_row_id: string; item_number: string | null;
  description: string | null; item_name: string | null; quantity: string | null; unit: string | null;
  unit_price: string | null; total_price: string | null; currency: string | null;
  classification: string; classification_basis: string[]; schedule_relevant: boolean;
  confidence: string; review_state: string; warnings: Finding[]; unmapped_values: Record<string, unknown>;
};
type Normalization = {
  id: string; normalizer_version: string; total_rows: number; schedule_relevant_rows: number;
  review_required_rows: number; warnings: Finding[]; lines: Line[];
};
type StructureHistory = { id: string; version_number: number; created_by: string; reason: string; change_summary: { material_correction?: { generation_id: string; actor_id: string; recorded_at: string; reason: string; changes: unknown[] } } };
const PAGE_SIZE = 25;
const display = (value: unknown) => value === null || value === undefined || value === "" ? "Unknown" : typeof value === "object" ? JSON.stringify(value) : String(value);

export function SourceReview({ api, connection, sources, artifacts, disabled }: {
  api: string; connection: Connection; sources: Source[];
  artifacts: { id: string; original_filename: string }[]; disabled: boolean;
}) {
  const [selected, setSelected] = useState("");
  const sourceId = sources.some((item) => item.id === selected) ? selected : sources[0]?.id ?? "";
  const [source, setSource] = useState<SourceDetail | null>(null);
  const [normalization, setNormalization] = useState<Normalization | null>(null);
  const [history, setHistory] = useState<StructureHistory[]>([]);
  const [message, setMessage] = useState("Choose a stored source and inspect it before planner review.");
  const [loading, setLoading] = useState(false);
  const [query, setQuery] = useState("");
  const [scope, setScope] = useState("ALL");
  const [page, setPage] = useState(0);
  const abort = useRef<AbortController | null>(null);
  useEffect(() => () => abort.current?.abort(), []);
  const headers = { "X-VAI-Actor-ID": connection.actorId, "X-VAI-Organization-ID": connection.organizationId };
  const base = `${api}/api/v1/projects/${connection.projectId}`;

  function clear() {
    abort.current?.abort(); setSource(null); setNormalization(null); setHistory([]); setLoading(false);
    setQuery(""); setScope("ALL"); setPage(0);
    setMessage("Choose a stored source and inspect it before planner review.");
  }
  async function inspect() {
    abort.current?.abort();
    const controller = new AbortController(); abort.current = controller;
    setSource(null); setNormalization(null); setHistory([]); setPage(0); setLoading(true); setMessage("Loading stored source…");
    try {
      const responses = await Promise.all([
        fetch(`${base}/bootstrap/boq-sources/${sourceId}`, { headers, signal: controller.signal }),
        fetch(`${base}/bootstrap/boq-sources/${sourceId}/normalization`, { headers, signal: controller.signal }),
        fetch(`${base}/bootstrap/boq-sources/${sourceId}/planning-structures`, { headers, signal: controller.signal }),
      ]);
      if (!responses[0].ok) throw new Error("Source could not be loaded. Check project access and retry.");
      if (!responses[1].ok && responses[1].status !== 404) throw new Error("Normalization could not be loaded. Retry before reviewing.");
      if (!responses[2].ok && responses[2].status !== 404) throw new Error("Planning correction history could not be loaded. Retry before reviewing.");
      const detail = await responses[0].json() as SourceDetail;
      const normalized = responses[1].ok ? await responses[1].json() as Normalization : null;
      const versions = responses[2].ok ? await responses[2].json() as StructureHistory[] : [];
      if (controller.signal.aborted) return;
      setSource(detail); setNormalization(normalized); setHistory(versions);
      setMessage(normalized ? "Stored source and normalization loaded. Review warnings and compare with the original." : "Stored source loaded. No normalization exists for this version.");
    } catch (error) {
      if (!controller.signal.aborted) setMessage(error instanceof Error ? error.message : "Source could not be loaded.");
    } finally { if (!controller.signal.aborted) setLoading(false); }
  }
  async function download() {
    if (!source) return;
    setLoading(true);
    const controller = new AbortController(); abort.current = controller;
    try {
      const response = await fetch(`${base}/evidence/artifacts/${source.artifact_id}/content`, { headers, signal: controller.signal });
      if (!response.ok) throw new Error("Original artifact could not be downloaded.");
      const blob = await response.blob();
      if (controller.signal.aborted) return;
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a"); link.href = url;
      const disposition = response.headers.get("content-disposition") ?? "";
      link.download = artifacts.find((item) => item.id === source.artifact_id)?.original_filename
        ?? disposition.match(/filename="([^"]+)"/)?.[1] ?? `boq-source-${source.version_number}`;
      link.click(); URL.revokeObjectURL(url);
      setMessage("Original source downloaded for comparison. Extraction is not verification.");
    } catch (error) { if (!controller.signal.aborted) setMessage(error instanceof Error ? error.message : "Download failed."); }
    finally { if (!controller.signal.aborted) setLoading(false); }
  }
  const byRow = new Map(normalization?.lines.map((line) => [line.source_row_id, line]) ?? []);
  const rows = source?.rows.filter((row) => {
    const line = byRow.get(row.id);
    if (scope === "EXCLUDED" && line?.schedule_relevant !== false) return false;
    if (scope === "REVIEW" && !row.warnings.length && !line?.warnings.length && line?.review_state !== "REVIEW_REQUIRED") return false;
    return !query || JSON.stringify([row.original_text, row.raw_values, line]).toLowerCase().includes(query.toLowerCase());
  }) ?? [];
  const lastPage = Math.max(0, Math.ceil(rows.length / PAGE_SIZE) - 1);
  const currentPage = Math.min(page, lastPage);
  const visible = rows.slice(currentPage * PAGE_SIZE, (currentPage + 1) * PAGE_SIZE);
  return <section className="workbench-card full-width source-review" aria-label="BOQ source review">
    <h2>Review source and classification</h2>
    <p>Compare preserved source rows with the proposed normalization. Excluded rows remain in history. This inspection does not verify quantities, accept assumptions, or authorize a schedule.</p>
    <div className="stack-form compact">
      <label>Stored BOQ source<select value={sourceId} disabled={disabled || loading || !sources.length} onChange={(event) => { clear(); setSelected(event.target.value); }}>
        {!sources.length && <option value="">No stored sources</option>}
        {sources.map((item) => <option key={item.id} value={item.id}>BOQ v{item.version_number} · {item.extraction_status}</option>)}
      </select></label>
      <button type="button" disabled={disabled || loading || !sourceId} onClick={() => void inspect()}>Inspect stored source</button>
    </div>
    <p role="status">{message}</p>
    {source && <>
      <p><strong>BOQ v{source.version_number} · {source.extraction_status}</strong> · {source.rows.length} retained rows · extraction confidence {source.extraction_confidence}</p>
      <p>Parser {source.parser_name} {source.parser_version}. Source hash <code>{source.content_sha256}</code>.</p>
      <button type="button" disabled={disabled || loading} onClick={() => void download()}>Download original BOQ</button>
      <Findings findings={source.warnings} label="Source warnings" />
      <details><summary>Source manifest and exact references</summary><pre>{JSON.stringify({ source_id: source.id, artifact_id: source.artifact_id, manifest: source.structure_manifest }, null, 2)}</pre></details>
      {normalization && <>
        <p><strong>Normalization {normalization.normalizer_version}</strong> · {normalization.schedule_relevant_rows} schedule-relevant rows · {normalization.review_required_rows} rows require review</p>
        <Findings findings={normalization.warnings} label="Normalization warnings" />
      </>}
      {history.some((item) => item.change_summary.material_correction) && <details><summary>Stored material correction history</summary>
        <p>Use the recorded draft reference in Load correction inputs to resume after a refresh. A recorded correction remains a planning proposal.</p>
        {history.filter((item) => item.change_summary.material_correction).map((item) => {
          const correction = item.change_summary.material_correction!;
          return <div key={item.id}><strong>Planning version {item.version_number} · {correction.actor_id}</strong>
            <p>Draft reference <code>{correction.generation_id}</code></p><p>{correction.reason} · {correction.recorded_at}</p>
            <details><summary>Original and revised inputs</summary><pre>{JSON.stringify(correction.changes, null, 2)}</pre></details>
          </div>;
        })}
      </details>}
      <div className="stack-form compact">
        <label>Search source rows<input value={query} onChange={(event) => { setQuery(event.target.value); setPage(0); }} /></label>
        <label>Source row filter<select value={scope} onChange={(event) => { setScope(event.target.value); setPage(0); }}>
          <option value="ALL">All retained rows</option><option value="EXCLUDED">Excluded from direct scheduling</option><option value="REVIEW">Warnings or review required</option>
        </select></label>
      </div>
      <p>{rows.length} matching rows · page {currentPage + 1} of {lastPage + 1}</p>
      <div className="queue-table-wrap" role="region" aria-label="Preserved BOQ rows and proposed classifications" tabIndex={0}>
        <table className="decision-queue-table"><caption>Raw source and proposed normalization</caption><thead><tr>
          <th scope="col">Source location and original values</th><th scope="col">Proposed normalized values</th><th scope="col">Classification and limitations</th>
        </tr></thead><tbody>
          {!visible.length && <tr><td colSpan={3}>No rows match this filter.</td></tr>}
          {visible.map((row) => {
            const line = byRow.get(row.id);
            return <tr key={row.id}>
              <td><strong>{row.page_number ? `Page ${row.page_number}` : row.sheet_name ?? "Sheet unknown"} · row {display(row.row_number)}</strong>
                <span>{row.original_text ?? row.raw_values.map(display).join(" | ")}</span>
                <small>Extraction confidence {row.extraction_confidence}</small>
                <details><summary>Raw cells and exact region</summary><pre>{JSON.stringify({ source_row_id: row.id, raw_values: row.raw_values, region: row.region }, null, 2)}</pre></details>
                <Findings findings={row.warnings} label="Extraction warnings" />
              </td>
              <td>{line ? <><strong>{line.item_number ?? "Reference unknown"} · {line.description ?? line.item_name ?? "Description unknown"}</strong>
                <span>Quantity {display(line.quantity)} · unit {display(line.unit)}</span>
                <span>Unit rate {display(line.unit_price)} · amount {display(line.total_price)} · currency {display(line.currency)}</span>
                <details><summary>Line references and unmapped values</summary><pre>{JSON.stringify({ line_id: line.id, stable_line_id: line.stable_line_id, unmapped_values: line.unmapped_values }, null, 2)}</pre></details>
              </> : "Not normalized"}</td>
              <td>{line ? <><strong>{line.classification}</strong><span>{line.schedule_relevant ? "Schedule-relevant proposal" : "Excluded from direct scheduling"}</span>
                <span>{line.review_state} · confidence {line.confidence}</span><small>Basis: {line.classification_basis.join(", ")}</small>
                <Findings findings={line.warnings} label="Line warnings" />
              </> : "No classification recorded"}</td>
            </tr>;
          })}
        </tbody></table>
      </div>
      <div className="form-pair"><button type="button" disabled={!currentPage} onClick={() => setPage(currentPage - 1)}>Previous source rows</button>
        <button type="button" disabled={currentPage >= lastPage} onClick={() => setPage(currentPage + 1)}>Next source rows</button></div>
    </>}
  </section>;
}

function Findings({ findings, label }: { findings: Finding[]; label: string }) {
  if (!findings.length) return null;
  return <details><summary>{label} ({findings.length})</summary><ul>{findings.map((finding, index) => <li key={index}>
    <strong>{finding.code ?? "REVIEW_REQUIRED"}</strong>{finding.message ? ` · ${finding.message}` : ""}
    <pre>{JSON.stringify(finding, null, 2)}</pre>
  </li>)}</ul></details>;
}
