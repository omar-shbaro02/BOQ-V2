# Local accessibility and queue-performance verification

R10 technical prerequisite evidence supplements the Phase 12 operator protocol. It does not
authorize Phase 13 entry or a pilot. Real operators and deployment acceptance remain required.

## Accessibility scope and reproduction

```powershell
$env:PLAYWRIGHT_CHANNEL='chrome' # Optional installed-browser alternative on Windows.
npm.cmd run test:browser
```

The existing isolated API/browser harness now includes axe-core 4.14.0 checks tagged for WCAG
2 A/AA, 2.1 A/AA, and 2.2 AA. The dependency is development-only and adds no application bundle,
external service, or operator screen. To run just this matrix, append
`-- tests/browser/accessibility.spec.ts`; the complete command also checks populated progress
and health states inside the existing critical journeys. CI's browser-security job runs the
complete suite. CI configuration is not evidence of a remote CI run.

The matrix covers all fifteen application pages at 1280- and 320-pixel widths: command center,
setup, simple/advanced bootstrap, schedule-change assistant, Decision Center, evidence, signals,
cases, progress, schedule, cost, forecast, impact, and orchestration. Additional scans cover
expanded report history, a loaded queue, human-governance case detail, saved progress measurements,
populated project/package health, and the open mobile navigation. Mobile views test document
reflow; horizontal table scrolling stays inside a named, keyboard-focusable region.

Keyboard checks exercise the first-tab skip link and visible content focus, hidden mobile
navigation, modal focus wrapping, Escape/return to the opener, reduced motion, and horizontal
table scrolling. A delayed-project-response regression proves that form submission cannot
omit a still-loading required project. Required case choices also remain subject to native
validation, and switching projects cancels obsolete case-list requests.

Remediations include shared navigation/amber contrast, a brand name matching its visible label,
mobile focus and background isolation, minimum control target size, form reflow, report-history
form layout, named groups, valid progress-table cells/headers and empty states, non-overlapping
health dimensions, and wrapping the populated chart legend. No role/grant, recommendation,
truth label, or authorization behavior is relaxed by these presentation changes.

Full axe results, including **incomplete/manual-review findings**, are written to ignored
`.test-tmp/accessibility/` and attached to Playwright results. Current scans have width-prefixed
or named loaded-state files; older unprefixed baseline files may retain the original failures.
Selected screenshots support local visual inspection. Do not treat zero automated violations
as full WCAG conformance. Glyph contrast, pseudo-element backgrounds, partially clipped table
content, screen-reader announcements, magnification, and representative operator comprehension
still require review. No axe rules or elements are excluded to obtain a passing result.

## Queue-query growth regression

```powershell
.\.venv\Scripts\pytest.exe services/api/tests/integration/test_queue_performance.py --basetemp .test-tmp/queue-query -o cache_dir=.test-tmp/cache
```

The sparse synthetic workload has ten work packages and fifty cases (including five explicitly
administratively closed cases), plus a separate foreign-project fixture. It asserts complete
case counts, open-before-closed ordering, exact object counts, and Unknown recommendation,
human-decision, confidence, and score fields for unevaluated cases. The service read must use at
most twelve SQL statements. Its baseline issued **301** statements; the batched implementation
issues **7**, or one additional batch when signed decisions need their exact historical run.
This structural budget catches per-case query growth without a machine-dependent timing test.

Latest impact, orchestration, and human-decision rows are selected independently by per-case
version. A signed decision's linked recommendation is fetched separately from the latest run.
Counts and open-limitation deadlines are aggregated within project case scope. Existing rich
governance/report regressions verify historical recommendation linkage and output semantics.
No persisted record, schema, approval, or deterministic report contract is changed by batching.

## Opt-in PostgreSQL read-load probe

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/rehearse_remediation.ps1 -DowngradeTarget 0030_presentation_artifacts -RunLoadProbe
```

The optional switch adds `LOCAL-QUEUE-READ-1.0.0` after the existing isolated migration,
concurrent-approval, and recovery checks. Omitting it keeps that repeated load out of ordinary
database rehearsals. The switch/environment is restored on exit and the cluster is stopped.

The probe uses real migrated PostgreSQL with ASGI TestClient, ten work packages, fifty sparse
cases, four concurrent callers, and ninety-six requests split equally across queue, review
queues, and semantic CSV export. Warm-up payload hashes must match every response under load;
the whole database fingerprint must remain unchanged. Local engineering regression limits are
route p95 below three seconds and total measured load below sixty seconds. These are conservative
test guardrails, not an agreed production latency objective or capacity promise.

On this Windows/Python 3.13.5/PostgreSQL 18.1 checkout, the executed probe completed in 3.29 seconds
(29.18 requests/second). Observed p95 was 0.214 seconds for the queue, 0.162 for review queues,
and 0.231 for CSV, with identical payloads and no database mutation. Raw elapsed times, per-route
sample counts, p50/p95/max, environment, and guardrails are retained in `queue-read-load.json`
under the ignored PostgreSQL rehearsal test directory.

This profile does not measure network/TLS, production identity/storage/scanner latency,
sustained traffic, multiple API workers/replicas, large historical assessment density, or cloud
database/storage capacity. The deployment owner must define representative data volumes,
concurrency, latency/error/backlog objectives and run that staging load/soak profile. Preserve
tenant denial, exact authority, idempotent results, and immutable history while measuring it.

Staging disaster recovery is separately specified in [recovery verification](21-recovery-verification.md).
Representative keyboard/assistive-technology and semantic-boundary sessions remain governed by
the [Phase 12 protocol](15-operator-usability-protocol.md). Both remain open acceptance gates.
