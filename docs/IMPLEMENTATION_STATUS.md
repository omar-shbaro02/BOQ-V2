# Implementation Status

Last updated: 2026-10-27

## Phase 12 operator controls and five-package acceptance preparation (2026-10-27)

Continued in phase order. Phase 12 now exposes the existing governed project-context commands in
the browser: create/select the active project, define controlled objects and containment, version
the charter, separately review/approve it with matching authority, register stakeholders/report
recipients, record evidence-linked reported daily updates, and save/authorize separate budget and
progress-weighting proposals. Project creation now persists its actual returned active-project ID.
Project changes clear loaded context and staged authority; commands remain disabled until reload.
Authorization inputs reset for each selected proposal. API identity/authority/version checks remain
authoritative; no grant is created automatically and operational claims are not verified by approval.

The Progress page now has an explicit snapshot composer: select authorized weights/schedule,
exact planned and verified/accepted measurements per weighted work package, optional case-bound
cost/schedule assessments, a reporting cutoff and explicitly entered health policy. No numeric
thresholds are inferred. It preserves the backend's matching observation-time, reporting-day,
basis/unit/denominator and source-version gates. Measurement choices show project-timezone dates;
cutoff inputs explicitly use browser time. Reports and the command center consume the issued
immutable snapshot rather than recalculating a mutable view.

The connected 17-step public-API exercise now runs both one-package and five-package variants.
The latter preserves ten distinct primary BOQ allocations, four reviewed finish-to-start links,
five explicit control mappings and weights, and separately verified measurements. Exact schedule/
baseline contexts, scoped cost and delay analyses, report/presentation approvals and later-update
isolation all pass. Only the first package has the selected cost/schedule assessments; unsupported
positions for other packages remain unknown, not an invented project-wide financial total.
Both variants run on enforcing PostgreSQL and enter logical database/artifact recovery. Generated
original/revised BOQs and the per-step manifests support an actual operator session.

Two new browser regressions cover five work packages, charter authority denial/approval, recipient
and daily-update persistence, separate weight/budget authorization, snapshot creation and the
command-center handoff, plus project-switch isolation. Loaded setup/composer controls pass axe and
reflow at desktop/320px. The browser snapshot test declares its API-seeded schedule/measurement
preconditions; it does not claim a complete 17-step UI-only creation journey or a human session.

Current full local verification passes: generated contracts, credential scan, 324 Python tests plus
four subtests (only live AI and the separately exercised PostgreSQL profile skipped), Ruff lint/
format, Python compilation, web lint/types/build, all 47 standard browser checks, synthetic HTTPS
identity, and PostgreSQL 0032 → 0031 → 0032 with both connected variants, authority/correction races,
immutable guards, logical recovery and the 96-read probe. The temporary cluster stopped.
Evidence: `.test-tmp/r10-20261027T174555Z-10a46174/report.md` and `report.json`; five-package
materials are under its `postgres/pytest/test_project_context_postgres_0/five-package/` directory.
The first full attempt correctly retained NOT RUN for occupied test ports; only the verified owned
manual test services were stopped before the clean rerun. No schema migration was added.

Separate current npm and pinned-requirement Python advisory audits report zero known findings;
JSON evidence is `.test-tmp/phase12-npm-audit.json` and `.test-tmp/phase12-python-audit.json`.
pip-audit 2.10.1 ran from an isolated ignored tooling venv, without changing application dependencies.
These separate audit results are not automatically merged into the default R10 report. Live AI,
actual cloud/provider deployment, remote CI and deployed load/soak/disaster recovery were not run.

Next: conduct and record representative independent PM/planner and manual-accessibility sessions
using `docs/26-phase12-operator-session-kit.md` and the corrected advanced-bootstrap protocol.
The user delegated suitable choices; a non-confidential concrete fixture and qualified participant
role profiles were selected, without inventing actual people, a live project or a staging URL.
Phase 13 formally begins only after Phase 12 acceptance; Phase 14 additionally needs release/pilot
approval, an actual active project and observed reporting cycles. One R10 remediation workstream
and Phases 12–14 remain. No roadmap phase or real pilot is marked complete from these local tests.

## Automated R10 evidence runner (2026-10-27)

Added `scripts/verify_r10.py`, `make verify-r10` and `npm run verify:r10`. One invocation records
PASS/FAIL/NOT RUN for the existing local engineering checks and retains command logs, JUnit,
browser JSON/traces, connected-scenario/recovery/load manifests and file hashes. Reports include
the commit and dirty candidate-tree digest captured at run start. Selected automated success is
separate from R10 acceptance: staging/provider, human/operator/manual accessibility and pilot
requirements remain NOT RUN. Optional online audits and potentially paid live AI require explicit
flags; missing selected prerequisites cannot produce a passing selected-check result.

Thirteen runner regressions cover empty/skipped/failed evidence, unexpected optional skips,
missing artifacts despite exit zero, browser failures/flakiness/skips, redaction, process timeout,
and preservation of the incomplete release gate after local success. `--require-complete` returns
nonzero while overall R10 acceptance is incomplete. No external attestation is automatically
accepted as human or production approval. See `docs/25-r10-verification-runner.md` for scope,
exit codes, prerequisite handling and reproducible commands.

The first complete run correctly failed for an API/web readiness race and absolute PostgreSQL
runtime-path handling. The harness now waits for both disposable services, accepts absolute or
relative PostgreSQL paths, records database JUnit in its evidence directory, and closes owned
process trees. A timed-out/interrupted database wrapper also receives an exact-cluster stop attempt.
No application semantic contract or persistent schema changed.

The corrected default run passes every selected local check: generated contracts, credential scan,
323 Python tests plus four subtests, Ruff lint/format, Python compilation, web lint/types/build,
45 browser/accessibility journeys, one synthetic HTTPS identity/proxy journey, and the isolated
PostgreSQL migration/authority/correction/connected-scenario/recovery/load rehearsal. The ordinary
suite skips only live AI and the separately exercised PostgreSQL profile. PostgreSQL passes
0032 → 0031 → 0032 and the 96-read probe; its temporary cluster stopped successfully.
Current evidence: `.test-tmp/r10-20261027T125516Z-1f47a907/report.md` and `report.json`.
Online dependency audits, live AI, actual providers, remote CI, human sessions, staging load/soak
and deployed disaster recovery were not run by this default invocation and remain explicit gaps.

Next: use the runner to reproduce local evidence, then collect representative planner/PM and
manual-accessibility observations and actual provider/deployment/staging acceptance. The report
does not replace the multi-package or full 17-step browser expansions discussed as follow-up work.
One remediation workstream (R10) and Phases 12–14 remain; no release or pilot acceptance is inferred.

## Connected 17-step technical acceptance and restored validation gate (2026-10-27)

Document 19's entire connected public-API scenario now passes in one synthetic project, both on
SQLite and migrated PostgreSQL. The existing connected exercise was audited and strengthened to
assert distinct baseline/current contexts, reconciled BOQ allocations, separately verified progress,
independent earned/physical cost bases, verified delay assessment and exact snapshot-bound health.
Combining cost value bases fails closed; the earned-value EAC remains a forecast and the separate
physical-value EAC stays unknown. Report and presentation approvals remain separate, the recipient
version and report approval linkage are exact, and approved deck download is denied before approval.

The test verifies 100% planned versus 40% verified completion, USD 2,000 budget/1,200 commitment/
900 actual/100 accrual, earned-value EAC 2,500, and 8-day supported schedule exposure under the
explicit synthetic policies. Dashboard API, report, presentation and assistant facts agree. Later
reported progress/daily updates leave the earlier snapshot, report, assistant hash and approved deck
bytes unchanged. Per-step record references, command statuses, hashes, exact JSON projections and
HTML slides are generated for review; see `docs/24-connected-acceptance-evidence.md`.

Three additional regressions reject mismatched progress observation timestamps, the previous
project-local reporting day despite a matching UTC date, and observations after the snapshot cut-off.
The existing runtime gate is unchanged. Its overlong error string and connected test formatting
were corrected, restoring the full lint gate while preserving existing behavior and schema contracts.

Current full gate passes: generated contracts; credential scan (293 repository files); 308 Python
tests plus four subtests, with four gated profiles skipped; Ruff lint/format; Python compilation;
web ESLint/TypeScript; production build. The separate PostgreSQL rehearsal passes 0032 → 0031 →
0032, concurrent approval/correction and immutable guards, the connected scenario, and full logical
database/artifact recovery. The cluster stopped successfully. Docker's daemon was unavailable;
the documented portable runtime required elevated execution outside the Windows sandbox.
Manifests: `.test-tmp/pg-remediation-a11f3b6e8aa340dd8a0ab2506af98e5e/pytest/test_project_context_postgres_0/`.
Ordinary scenario artifacts: `.test-tmp/connected-full/test_document_19_connected_gov0/`.
Browser checks, live AI, HTTPS identity, dependency audits, remote CI and the optional load probe
were not rerun in this slice. No schema migration was added; head remains 0032.

Next: collect representative planner/PM sessions and manual accessibility results against the
updated navigation; complete actual provider/deployment, staging load/soak and disaster-recovery
acceptance. The technical API demonstration is now evidenced; human and production acceptance
remain open. One remediation workstream (R10) and Phases 12–14 remain. Phase 12 completion,
Phase 13 entry and pilot approval are not inferred from automated synthetic evidence.

## Guided frontend navigation and page handoffs (2026-10-27)

The shared sidebar now follows the operator working order: Projects → BOQ to schedule →
Schedule → Evidence → Progress → Cost control → Signals → Decision cases → Forecasts →
Impact & priority → Orchestration → Decision queue. Four numbered stage groups separate plan
setup, control updates, investigation and human review. Command center remains an overview;
the top bar provides direct access to the decision queue for returning operators.

Every main page, including both bootstrap branches, now has a responsive orientation card,
step position, preparation guidance and prominent Next link. A matching bottom handoff explains
the destination and provides a previous-page link. Planning handoffs expose advanced review/
authorization and schedule-change tools. The queue returns to cases for signed decisions,
response observations and outcomes. Navigation does not assert completion, sufficiency or
authorization; operators are reminded to save before leaving. Inert search/notification controls
were replaced with the working queue shortcut. Existing working-tree work was preserved.

Current verification: generated contracts, web ESLint, strict TypeScript and production build
pass; Python suite: 305 passed, four skipped and four subtests passed. The desktop/320px guided
journeys, planning branches, 30 route accessibility checks and existing keyboard/mobile/loaded
governance checks pass (38 browser checks). Desktop and mobile setup screenshots were visually
reviewed. The Windows managed-server test runner stalled during teardown after all assertions
passed; rerun using the same isolated API/web services started separately avoids that teardown.
Python compilation passes. The broader Ruff gate remains blocked by existing long lines in
`services/api/app/services/project_control.py` and
`services/api/tests/integration/test_connected_acceptance.py`, plus formatting in the latter;
those unrelated files were not edited. No database schema change or migration was required.

Next: conduct representative operator sessions against the guided workflow and continue the
connected 17-step acceptance scenario below. One remediation workstream and Phases 12–14 remain;
automated navigation/accessibility evidence does not complete Phase 12 human acceptance or
authorize Phase 13 entry or a pilot.

## Connected acceptance prerequisites: planned controls and baseline history (2026-10-26)

The 17-step scenario audit found that a bootstrap schedule could not supply exact authorized
planned progress, and baseline approval did not persist a distinct baseline context. Review now
accepts sourced same-project activity/control-object mappings and explicit planned quantities,
dates, basis, unit and denominator. The advanced review UI stages these typed inputs; omitted
plans remain unknown and no interpolation or actual-progress verification occurs. Invalid/foreign
mapping, duplicate activity/object, incoherent points and conflicting basis edits fail closed.
Approval rechecks the stored object identity. Existing empty-input review hashes remain compatible.

Baseline approval creates separate BASELINE/current contexts; subsequent current approval creates
a proposed source and preserves the formally approved baseline. An unapproved BASELINE source
cannot replace it. Server-owned context metadata retains calculation/review/control/authorization
lineage. Approval now deep-copies its typed projection so original BOQ references survive export.
The API regression records a planned measurement only when its complete point matches the
authorized schedule, rejecting a different denominator.

Migration head is now `0032_context_history_guard`. SQL UPDATE/DELETE/TRUNCATE of context history
is denied; only CURRENT_AUTHORIZED → SUPERSEDED with a valid timestamp and all other fields
unchanged is allowed. Real PostgreSQL rehearsal passes 0032 → 0031 → 0032, baseline preservation,
legitimate supersession, immutable payload/actor denial, exact planned measurements, existing
approval/correction races, and full logical database/artifact recovery. The cluster stopped.
Synthetic manifests: `.test-tmp/pg-remediation-768e153eb8ba43159bb8399a5e68d1ad/pytest/`.

Current Python gate: 306 passed plus four subtests; live-AI and isolated-PostgreSQL profiles skipped
in the ordinary suite (PostgreSQL was separately exercised above). Generated contracts, credential
scan (289 repository files), Ruff lint/format, Python compilation/pip consistency, ESLint and
TypeScript and the production build pass. All 42 standard browser journeys pass using installed
Chrome and bundled Poppler. The three advanced XLSX/PDF/procurement journeys now stage explicit
control points and mappings, check desktop/320px accessibility, and verify stored review inputs;
the procurement journey also authorizes a distinct baseline. These automated results do not
supply representative human acceptance. Remote CI, live AI, HTTPS identity and the optional load
probe were not rerun in this slice.

Next: demonstrate the entire 17-step scenario in one governed project through public commands,
including charter/WBS/BOQ allocations, daily update and separately verified evidence, costs,
snapshot health, assistant, approved report and stakeholder presentation consistency. The new
regression closes prerequisites for steps 7–8, not that full scenario. Representative operator/
manual accessibility and actual provider/deployment/load/soak/disaster-recovery acceptance remain
open; the docs contain protocols and outstanding gates, not a completed session or staging URL.
One remediation workstream and Phases 12–14 remain. The pressure-test goal remains active.

## Advanced source review and immutable material corrections (2026-10-26)

Added the advanced BOQ source/normalization inspector: original artifact download; raw text/cells
beside normalized quantities/values, classification/rules, confidence, review state and exclusions;
source parser/hash, page/sheet/row/word-region references, unmapped data, warnings, search/filter
and 25-row pages. Stored correction history exposes successor draft references after reload.
Draft detail also returns its exact BOQ source version. Reconnecting clears prior project working
drafts, calculations, staged edits and reference defaults; requests in the inspector abort on unmount.

Typed forms stage explicit durations, sourced productivity, reviewed calendars/holidays,
explicit/template dependency type/lag, milestone target and constraint date/type corrections.
The human-only `/bootstrap/schedule-drafts/{id}/corrections` command atomically creates an
immutable reviewed-structure successor and new proposed generation, copying/remapping logic to
new activity IDs. Original/revised input fields, previous durations/bases, exact source/previous/new
generation lineage, actor, UTC time and reason are retained in existing append-only structure
metadata and an audit event. No persistent schema change or taxonomy edit was needed; head remains
0031_audit_append_only. Empty rationale, extra command fields, stale structure/logic, semantic
no-op/reordered duration inputs, foreign activity references, service/read-only/tenant denial and
payload/key mismatch fail closed. Unreviewed assumed calendars retain their open assumption.

Corrections never calculate CPM, publish a release or alter an authorized context. The UI clears
prior calculation/review defaults and requires new CPM and human review. A superseded planning
version cannot obtain a fresh review or approve an earlier pending release, even with a valid
grant. Immutable historical approvals/replays and the existing controlling schedule are preserved.
Milestone/constraint corrections remain proposed; no contractual authority or entitlement is inferred.

Real PostgreSQL rehearsal exposed an older source-row foreign-key insertion failure masked by
SQLite. Finalized source, normalization and generation parents now flush before dependent rows,
without later UPDATEs to their append-only records. The rehearsal runs the full XLSX source-to-
publication path, preserves approval through a later correction, exercises a two-writer correction
race (one 201, one stale 409), denies correction-history UPDATE/DELETE, rehearses 0031 → 0030 → 0031,
and restores the full database/artifact inventory. The isolated cluster stopped successfully;
current raw manifests are under `.test-tmp/pg-remediation-4b3f3e791eee48bd86e3fd76d039e0ad/pytest/`.
The optional read-load probe and separate HTTPS identity journey were not rerun in this slice.

Current full verification passes: generated contracts; credential scan (285 repository files);
305 Python tests plus four subtests, with only live-AI and isolated-PostgreSQL profiles skipped in
the ordinary suite; Ruff lint/format, Python compilation and pip consistency; ESLint/TypeScript;
production build; all 42 standard browser journeys. Three advanced journeys cover XLSX, PDF and
procurement scope through source review, typed corrections, recalculation, exact authorization,
export, revision isolation and stored correction history after reload. Loaded source/correction
controls pass automated accessibility/reflow at desktop/320px; screenshots were inspected and
calendar weekday labels were corrected to wrap as complete labels. Automated results do not supply
representative human acceptance or complete WCAG conformance. The tenant matrix now verifies 945
denials across 158 scoped operations; human-reserved commands include the new correction route.
No live AI call or production resource was used; CI was not remotely executed.

Next: audit the complete 17-step acceptance scenario in document 19 against one connected governed
project, preserving creation/verification/authorization boundaries rather than relying on unrelated
seeded fixtures. Then obtain representative operator/manual accessibility sessions, live provider/
deployment acceptance, staging load/soak and disaster-recovery evidence. One remediation workstream
and Phases 12–14 remain. B0.6–B0.8/Phase 12 acceptance, Phase 13 entry and pilot authorization are
not inferred from local automation; the full pressure-test goal remains active.

## Governed text-native PDF intake prerequisite (2026-10-26)

Closed the text-native PDF extraction gap recorded by the BS audit for supported tabular layouts.
The advanced bootstrap now uses bounded Poppler bbox extraction and the existing immutable source,
row and normalization records. Each retained row includes original text, page/row, proposed cells,
PDF-point word geometry, confidence and visible review warnings; source hash and parser version
remain explicit. Empty cells do not shift the following columns. Each page needs an unambiguous
supported English description/quantity header with at least three distinct recognized columns.
Normalizing the proposals never verifies quantities, issues authority or replaces a schedule.

Scanned/blank/mixed pages, unmapped headers and multiple different layouts on one page preserve
their source/available rows but remain VERIFICATION_REQUIRED. Missing/failed Poppler, timeout,
malformed XML/geometry, entities and resource-limit failures also fail closed. Input/output/time,
page and word bounds, child termination/wait and temporary-file cleanup have focused regressions.
Polling sizes is not an OS process sandbox; maintained Poppler and deployment resource isolation
remain required. Arbitrary/multiline table reconstruction, non-English headers and OCR remain
unsupported. All successfully extracted PDF rows retain visual completeness-review warnings.

The parser is VAI_BOQ_PDF_TEXT 1.0.0; normalizer 1.2.0 preserves original PDF row text and caps
classification confidence at MEDIUM for the 0.75-confidence PDF proposals. Existing immutable
sources, normalizations and authorized releases remain unchanged. No schema migration was needed;
head remains 0031_audit_append_only. UI guidance, README and documents 17/23 describe the boundary.
API and browser CI jobs now install Poppler; remote CI was not executed. The API container and
portable Windows runtime already contain it. Real-engine Python tests skip explicitly without
pdftotext on PATH; the PDF browser journey requires it.

Twenty-three focused PDF unit/API cases pass, including real two-page extraction, tenant denial,
replay, mixed-page normalization denial, process cleanup and no automatic authorization. Both
fixture pages were rendered and visually inspected. The advanced browser journey now runs for
both XLSX and PDF, including blocked-draft correction/recalculation, exact grant denial/approval,
export and revision isolation. A fixture initially repeated item references across pages and was
correctly rejected as duplicate BOQ scope; distinct fixture items now exercise successful intake.
Reload verification explicitly waits for required project loading before pressing Connect.

Current full verification passes: generated contracts; credential scan (281 repository files);
301 Python tests plus four subtests, with only the live-AI and isolated-PostgreSQL profiles skipped;
Ruff lint/format; Python compilation and pip consistency; ESLint/TypeScript; production build;
all 41 standard browser journeys. Poppler from the bundled Windows runtime was on PATH. No live
AI call or production resource was used. The PostgreSQL migration/recovery/load rehearsal from
the preceding slice and the earlier HTTPS identity rehearsal remain historical evidence, not
reruns in this slice.

Next: improve the advanced source/normalization review surface and richer material-edit workflow
needed by the operator protocol, preserving immutable correction/recalculation and exact authority.
Then conduct representative operator/manual accessibility sessions and obtain the documented live
adapter/deployment, staging load/soak and disaster-recovery evidence. Unsupported PDF layouts remain
explicit limitations. One remediation workstream and Phases 12–14 remain; no human acceptance,
Phase 13 entry or pilot authorization is inferred. The full pressure-test goal remains active.

## R10 BOQ conformity evidence audit and CPM corrections (2026-10-26)

Resumed the pressure-test goal from document 19 and audited BS-001–BS-010 against executable
evidence. Document 23 now maps each gate to named tests, current commands and the remaining
representative-human boundaries. The 37-case evidence/bootstrap module passes. Added explicit
coverage for all four dependency types, constrained late dates, supplied holidays/weekends,
pre-start milestone float, missing duration/calendar/trace/feeder, empty/duplicate schedules and
the working-day horizon. Validation fixtures no longer accidentally duplicate packages except
when that condition or a within-package prerequisite is deliberately under test.

The audit found and corrected CPM defects: the backward pass ignored fixed-start/fixed-finish/
finish-no-later-than constraints; all pre-start milestone deadlines collapsed to working index -1;
and an SF relationship could expose free float exceeding total available float. New calculations
use version 1.1.0 and bind that version in their input hash. Existing immutable calculations,
releases, authority history and authorized contexts remain unchanged. No schema migration was added;
head remains 0031_audit_append_only.

An advanced browser journey now uploads a real XLSX, observes a blocked missing-duration draft,
creates a corrected reviewed version, supplies productivity, recalculates against a holiday,
stages an attributed planner edit and records separate review. Missing-grant authorization fails;
an explicit exact grant permits the synthetic human approval. JSON export preserves the name and
authorization linkage. Added BOQ scope produces a delta without changing the authorized schedule,
and source/release history survives reload. The disposable fixture uses a separate organization
and project, with no live AI call or production resource.

Current verification: generated contracts and credential checks; 278 Python tests plus four
subtests (two explicitly gated checks skipped); Ruff lint/format; Python compilation and pip
dependency consistency; ESLint and TypeScript; production build; all 40 browser journeys.
The isolated real-PostgreSQL rehearsal also passes upgrade to 0031, downgrade to 0030 and re-upgrade,
concurrent approval, append-only denial, logical database/artifact restoration and the opt-in
96-read load probe. Its cluster stopped successfully. Raw synthetic recovery/load manifests are
under ignored `.test-tmp/pg-remediation-ed8c6cebad0c48fb9c19ee99c56b52cb/pytest/`.
The separate HTTPS identity journey and dependency advisory audits were not rerun in this slice;
their earlier results below remain historical evidence. CI was not remotely run.

Resume with representative operator/manual accessibility sessions and live adapter/deployment,
staging load/soak and disaster-recovery acceptance. A search of docs found protocols and explicit
outstanding gates, not completed participant sessions or an actual staging application URL.
Document 23 also records the advanced PDF extraction and richer material-edit boundaries;
simple PDF/AI scheduling does not satisfy governed canonical PDF extraction. The automated BS
audit is complete as technical evidence, but no BS release acceptance, B0.6–B0.8 completion,
Phase 12 completion, Phase 13 entry or pilot authorization is inferred. One remediation workstream
and Phases 12–14 remain; the pressure-test goal remains active.

## R10 accessibility and queue-performance prerequisites (2026-10-26)

Added development-only axe-core 4.14.0 browser verification across all fifteen application pages
at desktop and 320-pixel widths, plus loaded queue/report history, case governance, progress, and
project/package health. Fixed shared contrast/name failures, mobile focus isolation/wrapping and
Escape return, a first-tab skip link, reduced motion, keyboard table scrolling, small control
targets, form reflow, valid table/group semantics, report-history form layout, overlapping health
dimensions, and a populated chart-legend overflow. Desktop/mobile screenshots were inspected.
All 39 browser journeys pass; axe results preserve incomplete/manual-review findings and do not
constitute complete WCAG or representative-operator acceptance.

The combined journey exposed a project-loading race: a disabled required selector was omitted
from form data, permitting a request for project null. Shared selectors now retain native required
validation while loading. A deliberately delayed project response proves early submission cannot
issue the invalid request; stale case-list requests are cancelled when the selected project changes.

The 50-case queue issued 301 SQL statements before batching and now uses seven, with one additional
batch for exact signed-decision recommendation linkage when present. Reads independently preserve
latest impact, latest recommendation, latest human decision, and that decision's historical run.
Counts/deadlines stay project-scoped; unknown assessments remain Unknown. A query-growth regression
also seeds a foreign project and checks ordering and object counts. No schema or history changes
were required; migration head remains 0031_audit_append_only.

The opt-in PostgreSQL profile exercises ten work packages, fifty sparse cases and 96 reads with
four concurrent callers. Queue/review/CSV payloads remain identical and the whole database remains
unchanged. Observed duration was 3.29 seconds, with p95 0.214/0.162/0.231 seconds respectively.
This is a local ASGI/real-PostgreSQL result, not deployed network/TLS capacity or a production SLO.
The optional -RunLoadProbe switch keeps the load profile out of ordinary migration rehearsals.
Migration/rollback, concurrent approval, and backup/restore checks also passed on that cluster.

Current full verification passes: generated contracts; credential scan (277 repository files);
264 Python tests plus four subtests (two explicitly gated checks skipped); Ruff lint/format;
Python compilation and pip consistency; ESLint/TypeScript; all 39 standard browser journeys;
the separate HTTPS production-identity journey; and the production build. The current npm audit
remains at zero findings after adding the development-only accessibility dependency. Existing
Python pins retain the previously verified clean advisory result. CI is configured, not remotely run.

See docs/22-nonfunctional-verification.md for reproduction, exact scope, observed results and limits.
Resume R10 with the BS-001–BS-010 evidence audit, remaining manual accessibility/operator sessions,
live adapter/deployment acceptance, representative staging load/soak, and staging disaster recovery.
The combined hardening checkbox stays open because those requirements are broader than local
automation. One remediation workstream and Phases 12–14 remain; pilot approval is still explicit.

## R10 tenant, human-authority, and recovery enforcement (2026-10-26)

Completed the route-wide denial matrix: 157 scoped API operations and 939 production-token
tenant/membership denials, with unchanged database row counts and unreachable storage/scanner
adapters. All 31 human-reserved commands also reject three service/unknown identity variants
(93 denials), even with admin roles and actor-owned grants. Four local preview operations are
disabled in production. Taxonomy 1.10.0 adds SYSTEM_SERVICE. Trusted principal-type claims and
client-credentials classification distinguish human identity from service access; interactive
browser identity requires verified ID-token/nonce binding. Audit actor type now records that
classification. Reported ingestion remains available without granting service principals human
verification or approval powers. Mixed reported/verified imports fail atomically without the
required human verification role.

Closed direct context-activation authorization bypasses. Activation now requires an exact active,
actor-owned, project-wide context approval grant, Idempotency-Key, and exact expected predecessor.
Frozen grant scope/validity and request identity are retained in immutable audit history; revoked
or superseded replays return their original record without reactivation. CHANGE_APPROVAL cannot
bypass governed change review. Case/response grants bounded to one package must cover the entire
case scope. Planner reviews freeze their schedule predecessor and stale approval requires fresh
review. Subsequent review/approval versions append without collisions. Existing approvals are
not backfilled with invented authority. The stricter activation inputs are documented in the API
contract. ORM metadata now mirrors the already-existing PostgreSQL single-current constraint.

Real PostgreSQL concurrent initial approvals produce exactly one approval and one 409; the winner
replays with its exact original ID. Migration 0031_audit_append_only corrects missing database
protection on audit events: UPDATE, DELETE, and TRUNCATE are rejected. Upgrade/downgrade/re-upgrade,
including a populated rollback to 0030, preserves audit history. Existing health/presentation
rollback guards and immutable records remain verified. Docker remains unavailable; the isolated
bundled PostgreSQL rehearsal is the executed alternative and stops its cluster on exit.

Added logical backup/restore verification using pg_dump/pg_restore into a distinct disposable
database plus separate object backup/restoration. All 79 public tables (84 synthetic rows), index
definitions, and trigger/function definitions match. Both artifact objects match stored hashes.
Missing bytes return 503, damaged bytes 409, exact recovered presentation bytes 200, and foreign
tenant access 403. Restored immutable guards remain active; the successful download appends its
own correctly attributed access audit while original audit history remains exact. The source
database remains unchanged. Recovery manifests and timings are retained under ignored test
scratch directories. This is quiescent local logical recovery, not live-write consistency,
WAL/PITR, cloud object-version recovery, regional failover, or an accepted production RPO/RTO.
`docs/21-recovery-verification.md` records reproduction and staging acceptance requirements.

The pinned dependency audit found affected certifi/pytest versions. Updated pins to certifi
2026.10.23 and pytest 9.0.3 and adjusted the dev range. Repeat pip-audit reports zero known
vulnerabilities across all 46 Python pins; the public-registry npm audit also reports zero findings.
A separate dependency-audit CI job is configured, not remotely executed.

Current verification passes: generated contracts, credential scan (272 repository files),
263 Python tests plus four subtests (two explicitly gated checks skipped), Ruff lint/format,
Python compilation, pip dependency consistency, ESLint, TypeScript, production build, all four
standard browser journeys, and the separate HTTPS production-identity journey. The isolated
PostgreSQL migration/concurrency/recovery profile also passes. No live paid adapter calls or
production resources were used. Migration head is 0031_audit_append_only.

Resume R10 with broader concurrency/performance/accessibility, remaining BS-001–BS-010 evidence,
live adapter/deployment verification, and staging disaster recovery. The route-wide matrix is
complete; focused concurrency and local restoration do not close the broader hardening checkbox.
Representative Phase 12 human sessions and explicit pilot approval remain required. One remediation
workstream and Phases 12–14 remain.

## R10 browser identity and HTTP hardening (2026-10-26)

Implemented the production browser sign-in flow in the existing API: authorization code with
S256 PKCE, encrypted state/nonce transaction, exact access/client-ID token binding, short-lived
encrypted Secure/HttpOnly/SameSite host cookies, key rotation, current-identity discovery, and
same-origin sign-out. The web's project context uses verified identity and cannot fall back to a
saved development actor in production. Token roles still cannot supply membership or authority.
Only the existing account control changes; no additional identity gateway or vendor UI is needed.

Added declared/streamed request-body caps, bounded per-peer/process rate limits, Origin checks
for cookie-authenticated mutations, response security headers, restricted web CSP, and callback
query redaction. Production API documentation routes are disabled. Added a redacted credential
check to Make/CI and a CI browser-security job. Deployment must still supply trusted TLS/client-IP
forwarding, coordinated edge limits for replicas, secret-manager values, and provider policy.
Stateless cookie sign-out clears the browser; copied credentials remain bounded by token/session
expiry rather than server-side revocation. Static Next hydration currently requires inline
scripts/styles, so CSP is not claimed as nonce-based XSS prevention.

The HTTPS rehearsal uses a real production Next build/API and a disposable synthetic issuer,
temporary CA, JWKS, one-use code exchange, PKCE validation, and signature verification. It proves
HttpOnly cookie handling, verified identity despite forged local workspace fields, cross-origin
command denial, sign-out, and mobile layout without page overflow. A 12 MiB upload traverses the
full proxy without truncation. This exposed/fixed Next's default 10 MiB proxy buffer, which could
stall otherwise valid uploads. A grid min-width correction confines queue scrolling to its
container. Desktop/mobile previews were inspected. It does not prove live Auth0/S3/ClamAV service
configuration or representative human acceptance.

Full verification passes: generated contracts, credential scan (261 candidate/tracked files),
254 tests (two explicitly gated checks skipped), Ruff lint/format, Python compilation, ESLint,
TypeScript, production build, four existing browser journeys, and the separate HTTPS production
identity journey. Twenty-three identity/HTTP cases, five credential-check cases, and four narrative
fidelity cases are included. CI was configured, not remotely executed. No schema change was needed.

The full gate caught a latent numeric-fidelity defect: UUID/date/free-text digits could authorize
unsupported narrative numbers. Validator `CASE-BRIEF-FIDELITY-1.1.0` now separates exact citations
and dates from typed numerical facts, excludes reported limitations from numerical authority,
normalizes supported decimal/scientific values, and rejects foreign record references. Existing
orchestration API and new deterministic regressions pass; no immutable historical run is rewritten.

Continue R10 with the route-wide tenant/authority denial matrix, concurrency/performance/
accessibility, backup/restore/disaster recovery, BS-001–BS-010, and live deployment checks.
Representative Phase 12 human sessions and explicit pilot approval remain required. One remediation
workstream and Phases 12–14 remain; none is closed by the synthetic browser/provider evidence.

## R10 backend adapters and workbook resource gates (2026-10-23)

R10 is in progress. Selected Auth0-compatible standard OIDC/JWKS verification, Amazon S3, and
private daemon ClamAV, following the user's preference for low UI and checking overhead. The API
now validates exact issuer/audience, RS256 signatures, required claims, time windows, stable
subject, and organization scope. Signed identity never replaces database memberships/authority;
development actor/role headers cannot impersonate a production user. JWKS caching has a finite
TTL and unknown-key refresh cooldown. Missing configuration and outages remain fail-closed.

S3 writes are encrypted and conditional, replay requires exact bytes, and bounded reads validate
length and SHA-256 metadata. Credentials use the AWS workload credential chain, not application
configuration or browser storage. ClamAV checks database freshness and streams exact bytes under
one deadline; infection, incomplete scanning, resource errors, stale signatures, and outages
cannot produce CLEAN. Scanning/storage work is offloaded from the upload event loop.

All six workbook readers and XLSX/XLSM uploads share bounded ZIP expansion and safe XML preflight.
Unsafe/duplicate names, DTD/entities, encrypted/multipart/ZIP64 archives, excessive entries, cells,
XML elements, rows, columns, sheets, or compression expansion fail visibly. Alternate worksheet
paths/extensions do not bypass dimension limits. No imports are silently truncated. New runtime
dependencies are declared and pinned in the managed lockfile; `pip check` passes. Default test
isolation now also denies urllib and botocore network transports.

Thirty focused adapter/archive cases pass in under one second on this checkout, including real
loopback scanner-protocol and cryptographic signature checks. The full Python suite passes
222 tests with live-adapter/isolated-PostgreSQL checks gated. Generated contracts, Python lint/
format/compilation, ESLint, TypeScript, and the 17-route production build pass. All four real
browser journeys also pass after the archive/scanner changes. The public npm registry's full audit returns
zero findings across production and development dependencies; the earlier five dev-only findings
are historical evidence, not current findings. No persistent schema change was needed after the
verified R9 migration 0030.

Continue R10 with gateway/browser-session and current-identity integration, live adapter checks,
request/rate/header and secret handling, route-wide tenant/authority denial, concurrency/performance/
accessibility, backup/restore/disaster recovery, BS-001–BS-010, and representative human sessions.
`docs/20-production-hardening.md` describes exact configuration and deployment gaps. No production
accounts/resources were provisioned. One remediation workstream and Phases 12–14 remain;
Phase 12 human acceptance, Phase 13 acceptance, and explicit pilot authorization are still open.

## R9 report-derived presentations and shared facts (2026-10-23)

Completed R9 with immutable self-contained HTML stakeholder slide decks generated exclusively
from approved report snapshots. The Decision Center has a collapsed history panel to freeze,
review, and approve reports, select exact recipient versions frozen in their control context,
generate slides, and separately review/approve the resulting artifact. Approved downloads are
gated by active actor-owned project-wide `REPORT_APPROVAL` authority and exact lifecycle version.
No communications are sent and neither approval authorizes execution.

The dashboard, new reports, assistant completion, and presentations consume the same deterministic
`CONTROL-METRICS-1.0.0` projection. Decimal percentage rounding, source dates, Unknowns, assessment-
scoped financial values, and semantic notices are preserved. The dashboard no longer labels the
first bound cost assessment as a project-wide EAC. Decks embed the complete frozen source and
recipient records; stored SHA-256 hashes, source approval linkage, generator versions, immutable
events, and audit downloads make their provenance inspectable. Report text is escaped and the
offline deck restricts scripts/styles with content hashes.

Nine focused API cases verify cross-artifact equality, exact bytes/hash, approval separation,
replay/mismatch, stale versions, tenant/actor denial, recipient eligibility, authority validity and
scope, tampered bytes, and altered visible metrics. The full gate passes: generated contracts,
192 tests (two gated checks skipped), Ruff lint/format, Python compilation, ESLint, strict
TypeScript, and the 17-route production build. All four browser journeys pass, including actual
report/presentation human actions, approved download, source equality, and ten-slide layout
checks. Every generated slide was visually inspected; previews remain local ignored QA artifacts.

Migration `0030_presentation_artifacts` passed PostgreSQL upgrade/downgrade/re-upgrade, migrated
API behavior with real foreign keys, twelve append-only UPDATE/DELETE denials across R5–R9
records, and rejection of populated-history rollback. The isolated cluster was stopped. This
rehearsal exposed and fixed parent-before-lifecycle insertion ordering for report creation,
which SQLite without foreign keys had masked. The Windows rehearsal launcher now waits for
`pg_ctl` itself instead of its persistent descendants. Docker remains unavailable; the bundled
PostgreSQL runtime supplied the isolated database.

Resume at **R10 production/pilot hardening**. One remediation workstream remains. The user has
delegated adapter selection with a preference for low UI and checking overhead: use standard
backend OIDC/JWKS, S3-compatible object storage, and daemon ClamAV with bounded calls and cached
identity keys. Integration and deployment verification remain open. Representative Phase 12
human sessions, Phase 13 acceptance, and explicit pilot authorization remain unsatisfied;
automated checks do not replace them. Phases 12–14 remain.

## R8 grounded snapshot assistant and advisory (2026-10-23)

Completed R8 with a read-only deterministic query over one selected immutable project-control
snapshot. The command center now contains a compact expandable question/topic panel for completion,
schedule, cost, forecast, RAG, risk/issue/change context, evidence, and recorded review deadlines.
It uses no model calls, current-state lookups, write tools, or execution/communication adapters.
Answers preserve source dates, reported/derived/forecast distinctions, unknowns, exact record-ID
citations, and separate management considerations for human review. Cost results remain scoped
to their bound assessments; insufficient conclusions withhold intermediate totals rather than
asserting zero. Project-timezone dates are explicit in the new health/assistant panels.

The frozen fact catalog and citation allowlist reject altered numeric values, foreign citations,
and fabricated authority/advisory text. Injection text in stored records is displayed only as
reported data. Action requests cannot mutate records or claim approval. Later project context
does not affect a response to an issued snapshot, and deterministic answer hashes support replay.

Eighteen focused API/fidelity regressions pass. The real browser health journey also queries the
assistant, verifies the completion value and truth label, then confirms an injected execution
approval request returns `ACTION_NOT_PERMITTED` with no facts. The full gate passes: generated
contracts, 183 tests, Ruff lint/format, Python compilation, ESLint, strict TypeScript, and the
17-route production build. Only live-adapter and isolated-PostgreSQL checks are gated; PostgreSQL was verified in the R7
rehearsal. No persistent schema change was needed for this read-only slice.

Resume at **R9 report-derived stakeholder presentations**, then R10 hardening and external/human
acceptance. Two remediation workstreams remain. Phase 12 human sessions, Phase 13 entry, and
explicit pilot authorization remain open and cannot be replaced by automated test results.

## R7 explainable package and project health (2026-10-23)

Completed R7 with snapshot-bound, deterministic RAG for progress, supported network completion
exposure, EAC/budget alignment, evidence confidence, and historical governance. Policies require
explicit project-admin ownership, rationale, version/effective date, thresholds, freshness, and
material weight; no operational thresholds are invented. Package results precede weighted project
aggregation. Small Red packages remain visible as project Yellow below material Red weight.
Missing, stale, ambiguous, and restricted sources remain Unknown, and snapshot contradictions
restrict the progress conclusion. Every adverse dimension has a signal/case review route.

The command center displays textual project/package/dimension statuses with policy, rule,
threshold, confidence, source references, cut-off, and limitations. Reports reuse exactly the same
frozen health. Supporting context now freezes schedule assessments, historical audit governance,
and cut-off-valid charter/stakeholder/daily/risk/issue/change records for the next assistant slice.
New case audit events retain governance/readiness/lifecycle state; legacy events without that
information remain Unknown. Existing snapshot retries preserve the prior request-hash contract.

Migration `0029_snapshot_health` passed fresh PostgreSQL upgrade, downgrade to `0028`, and re-upgrade.
The migrated API and eight append-only update/delete checks passed. A further rollback attempt
with populated health correctly failed without losing its snapshot. The R1 fixture was corrected
to include real evidence rows, valid verified measurement bases, and exact authorized plan points
after PostgreSQL exposed its inherited synthetic foreign-key gap.

R7 adds 20 focused rule/API tests, and its browser test creates authorized contexts and normalized
measurements through real APIs before checking visible RAG, policy, unknowns, and review links.
Ruff, TypeScript/ESLint, and the production build pass; the complete suite contains 165 passing
tests plus the two explicitly gated tests, with PostgreSQL exercised separately. Three prior
browser paths passed and the corrected health browser path passed separately.

Resume at **R8 grounded snapshot assistant**, followed by R9 and R10. Three remediation workstreams
remain. Phases 12–14 and representative human/pilot authorization remain open. For R10, the user
delegated provider choice and requested minimal app clutter and low checking latency; the selected
backend direction is OIDC/JWKS, S3-compatible storage, and daemon-based ClamAV scanning, with cached
identity keys and bounded external-call timeouts. Production adapter implementation/verification
is not yet claimed.

## R6 governed progress workbook ingestion (2026-10-23)

Completed remediation R6. `/progress` now saves the uploaded workbook through project-scoped
evidence storage and maps every task to the exact current-authorized activity/object and schedule
version. Immutable imports freeze source hashes, cut-offs, mappings, the network and explicit
authorized calendar, derived working-day counts, reported evidence/measurement IDs, formula version,
and limitations. Exact authorized plan points supply planned completion; missing points stay
unknown. Reported completion creates only `REPORTED` / `REPORTED_CLAIM` records, with separate
verification/acceptance gates. Deadline exposure remains unknown until adequately supported by the
existing governed schedule assessment; the calendar-day/max-task calculation is confined to a
clearly labeled, local-only, unpersisted preview.

Regression coverage checks persisted retrieval, replay/payload mismatch, duplicate source imports,
stale context, tenant denial, formula/percentage/fractional-ID rejection, exact dates and scope,
calendar holidays, and unknown-versus-zero preservation. A third browser test completes a real
upload/mapping/save/reload/history journey and proves the saved claim remains reported.

Migration `0028_progress_workbook_imports` passed fresh PostgreSQL upgrade through head, rollback
through `0026`, and re-upgrade. The migrated-database test exercised charter and workbook APIs and
rejected all six update/delete attempts on the three immutable R5/R6 tables. The isolated bundled
PostgreSQL cluster was stopped afterward; Docker Desktop remained unavailable.

Current full gate: generated contracts, **145 passing tests**, Ruff lint/format, Python compilation,
ESLint, strict TypeScript, and the 17-route Next.js production build pass. The two opt-in tests
remain skipped in the default suite; the PostgreSQL test passed separately. All **three browser
tests** passed using installed Chrome. Existing deprecation and development-dependency security
findings remain documented above/below and have not been declared fixed.

Resume at **R7 explainable project/package RAG**, then R8, R9, and R10. Four remediation workstreams
remain. Roadmap Phases 12–14 remain open and require representative human acceptance before Phase 13.

## Remediation resume: R0 verification and R5 governed context (2026-10-23)

Verified the inherited R1–R4 implementation in this checkout before continuing. Completed R0's
remaining technical items: an explicitly opted-in `live_adapter` pytest profile, default external
HTTP transport denial, Next.js/ESLint configuration pinned to 16.4.2, and browser regression checks
against a disposable real API/database. Browser coverage proves BOQ persistence, download, and
versioned retry when the scheduler is unavailable, plus Decision Center unknown/authority semantics,
filtering, and CSV export. The paid live profile was deliberately not executed. Production npm
audit reports zero vulnerabilities; five development-only ESLint/glob-chain findings remain open
for R10 and prevent pilot security acceptance.

Completed R5 from the inherited partial schemas/models. Added immutable versioned project charter,
stakeholder/report-recipient registry, evidence-linked daily updates, risks, issues, and change
requests under `/api/v1/projects/{id}/project-context`. A singleton charter stream, exact predecessor
references, idempotency payload hashes, project locking, optimistic lifecycle versions, role denial,
and audit events preserve governance. Daily cut-offs use project-local dates and reject later
evidence. Review never verifies reported claims. Charter/change approval requires the actor's exact
active project-wide authority; approved changes reject stale controlling context, create a separate
authorized version, and retain source payloads and immutable authorization linkage. These APIs do
not send communications or authorize execution.

Migration `0027_project_context_records` passed fresh PostgreSQL 18.1 upgrade through head,
downgrade to `0026_boq_activity_allocations`, and re-upgrade. A real migrated API write/read test and
four direct SQL update/delete attempts prove both new tables are append-only. Docker Desktop's
daemon was unavailable; the rehearsal used the bundled runtime and an isolated cluster, then
stopped it. `scripts/rehearse_remediation.ps1` reproduces that rehearsal.

Current checkout gate: generated contracts, **136 passing tests**, Ruff lint/format, Python
compilation, ESLint, strict TypeScript, and the 17-route Next.js 16.4.2 production build pass.
The default suite skips the opted-in live test and isolated PostgreSQL test; the PostgreSQL test
passed separately during rehearsal. Both browser tests pass using installed Chrome. Existing
Starlette/httpx deprecation warnings remain visible. No representative human acceptance or pilot
approval has been claimed.

Resume remediation at **R6 governed progress workbook ingestion**, followed by R7, R8, R9, and R10.
Five remediation workstreams remain (R6–R10). Roadmap Phases 12–14 remain open; Phase 13 may not
begin until representative Phase 12 operator evidence passes.

## BOQ commercial integrity and allocation lineage (2026-10-23)

Completed remediation workstream R4. BOQ normalization version 1.1.0 now uses exact Decimal
arithmetic to compare quantity multiplied by unit rate against stated amount with a caller-recorded
currency-unit tolerance. It detects negative quantity/rate/amount values, repeated stable
commercial lines, currency divergence from project context, and inconsistent grand totals while
preserving every original value and warning. Project currency supplies the deterministic currency
context when a valued source line omits an explicit currency; a conflicting explicit currency is
review-required rather than silently converted.

Every versioned BOQ-to-work-package mapping now stores allocated quantity, percentage, value,
unit, currency, allocation basis, and a primary-counting marker. Generated schedule activities
carry the same line-level allocation lineage with exactly one primary-counting activity and any
additional procurement or workflow activities marked `TRACE_ONLY_NON_COUNTING`. CPM validation
requires each mapped BOQ line to have exactly one 100% primary allocation, preventing quantity,
percentage, or value duplication across one-to-many schedule traces. All commercial-integrity and
allocation defects produce blocking findings before planner review or schedule approval.

Migration `0026_boq_activity_allocations` passed PostgreSQL upgrade, downgrade, and re-upgrade and
the non-null JSONB allocation column was verified at head. Regression coverage proves arithmetic,
sign, currency, duplicate, grand-total, approval-blocker, and deliberate over-allocation failures,
plus primary-versus-trace-only behavior across multi-activity mappings.

## Data-backed command center (2026-10-23)

Completed remediation workstream R3. Removed every illustrative project metric, synthetic signal,
fixed chart, and fabricated health score from the root command center. The page now requires the
operator's explicit active project and loads the latest immutable project-control snapshot, live
governed Decision Queue, and stored project signals. It displays authorized planned versus
verified actual completion, variance/status, package contribution lineage, open and material case
counts, EAC, forecast finish, evidence confidence, and snapshot limitations. Missing snapshot,
cost, forecast, or project context is rendered as `Unknown` or an actionable empty state, never as
zero. The persisted-report integration test proves the report and dashboard source projection use
the same frozen actual-completion value. ESLint and strict TypeScript pass for the replacement.
The full repository gate passes in the current checkout: generated contracts, all **120 tests**,
Ruff lint/format, Python compilation, ESLint, strict TypeScript, and the 17-route Next.js production
build. The build still warns that Next.js 16.4.0 has a known security vulnerability; R0 therefore
remains open until the dedicated security upgrade is applied and verified.

## Persisted snapshot-correct governed reports (2026-10-23)

Completed remediation workstream R2. Governed reports are now stored as immutable snapshots bound
to one immutable project-control snapshot. Each record separates report date from source data date
and freezes its payload, exact schedule/weighting/evidence/case references, policy versions,
generator version, semantic notice, canonical SHA-256 content hash, and fidelity manifest. Report
creation has no caller-supplied historical `as_of`; it captures the state visible at issue time and
then serves that frozen payload, so later mutable case state cannot alter or leak into an issued
report. Weekly, monthly/executive, exception, on-demand status, case dossier, pilot KPI, and
governance-conformity types all pass through this single persistence service.

Added append-only report lifecycle events for `DRAFT` to `REVIEWED` to `APPROVED`. The externally
issuable read path rejects non-approved reports, and approval requires the same actor to hold a
currently active, project-wide `REPORT_APPROVAL` authority grant. Creation and review routes also
enforce project roles, with audit events for creation and transitions. Idempotent retries return
the original frozen report and payload mismatches fail closed.

Migration `0025_report_snapshots` passed PostgreSQL upgrade, downgrade, and re-upgrade; both report
and lifecycle append-only triggers were present at head. Integration coverage verifies stable hash
and payload retrieval, idempotent replay, approval denial without authority, reviewed/approved
transitions, external-use gating, and cross-tenant denial. R3 command-center replacement is next.

## Immutable weighted project-control snapshots (2026-10-23)

Completed remediation workstream R1. Added immutable, idempotent project-control snapshots that
calculate overall planned and actual completion from exact authorized work-package weights and
exact package-level progress measurements. Inputs must cover the complete weighting set and use
the selected current-authorized schedule, one measurement basis, matching units and denominators,
the exact snapshot data date, and verified or accepted/released actual truth. Reported-only,
partial, cross-project, future-dated, stale-context, incompatible, and weak-truth inputs fail
closed. The derived snapshot records package contributions, an explicit empty exclusion set,
planned/actual/variance ratios, threshold-based status, minimum confidence, evidence IDs, context
versions, policy/formula lineage, and visible limitations.

Snapshots can bind exact cost assessments and non-hypothetical, unexpired forecast projections.
Those projections retain their source IDs, case/object scope, dates, result ranges, truth,
confidence, evidence, policies, formulas, and limitations. Missing cost or forecast inputs are
stored as explicit `COST_POSITION_UNKNOWN` and `FORECAST_POSITION_UNKNOWN` limitations rather than
zero values. Read APIs provide immutable list/detail projections, while creation is restricted to
analysis roles and records an audit event.

Added migration `0024_project_control_snapshots`, including the previously missing PostgreSQL
constraint expansion for `PROGRESS_WEIGHTING` and an append-only trigger. A fresh portable
PostgreSQL cluster was upgraded through head, downgraded to `0023_bootstrap_revision_delta`, and
re-upgraded to head. The final head, both new status/policy columns, the trigger, and preserved
weighting history were queried successfully. A direct SQL update against a persisted snapshot was
rejected by the append-only trigger. The downgrade deliberately retains the widened context-type
constraint so governed weighting history is not destroyed to restore an older schema.

Focused integration tests cover exact weighted arithmetic, lineage, unknown-domain limitations,
list/detail reads, audit creation, idempotent replay and payload mismatch, incomplete package sets,
superseded schedule context, reported-only actuals, and cross-tenant denial. The ordinary suite now
passes **120 tests**. R2 snapshot-correct persisted reporting is the next remediation workstream.

## Pressure-test remediation and deterministic test isolation (2026-10-23)

Recorded the repository-wide implementation audit and ordered remediation workstreams in
`docs/19-pressure-test-remediation-plan.md`. The plan keeps Phase 12 open and prioritizes an
authoritative project-control snapshot, snapshot-correct reporting, a data-backed command center,
BOQ commercial reconciliation, governed operational context, explainable RAG, and cross-artifact
fidelity without weakening the existing Decision Case or human-authority boundaries.

The pressure test found that a developer `.env` containing an OpenAI key caused the default
integration suite to invoke live specialist agents, making one deterministic orchestration test
return `STOPPED` instead of its expected deterministic `LIMITED` result. Added an autouse test
boundary that forces the test environment, clears the external key, disables optional agents, and
resets cached settings around every test. A regression assertion now proves that default tests do
not inherit external AI credentials. Live-adapter testing remains an explicit future opt-in path.

Started the authoritative project-completion foundation by adding a generated
`PROGRESS_WEIGHTING` authorized-context contract with BOQ-value, cost-value, quantity, and explicit
manual-authorized bases. A weighting version must contain unique active project work packages,
strictly positive weights totaling exactly one, one compatible progress measurement basis, and a
source reference. Invalid totals, duplicates, unknown/cross-project codes, and non-work-package
objects fail before the context can be recorded. The existing reviewed activation path preserves
proposal-versus-current-authorized history. Weighted completion calculation and immutable
project-control snapshots were completed in the subsequent R1 slice above.

Current verification for this slice: generated contracts, all **118 tests** using the ordinary
test command with the developer `.env` still present, Ruff lint/format, Python compilation,
ESLint, strict TypeScript, and the 17-route Next.js production build pass. Next.js 16.4.0 emitted
a current security-upgrade warning during the build; dependency remediation is recorded as an open
R0 item and this warning is not being treated as resolved by the successful retry.

## BOQ workspace usability refresh (2026-10-12)

Reworked the simple `/bootstrap` workflow into one balanced, responsive surface instead of an
uneven main-card/sidebar layout. Project connection, BOQ upload, dates, the fixed output contract,
and the generation action now follow one clear sequence with consistent control sizing, improved
disabled guidance, selected-file feedback, and compact links to the assistant and governed flow.
Project creation is now a dedicated `Projects` navigation destination. In local-evaluation mode,
the UI manages the development actor and organization UUID internally after first-project setup;
operators see workspace and project names rather than technical identifiers. The BOQ workspace
loads the saved project context automatically and routes an empty installation to project creation.
Desktop and narrow-width rendered-page checks passed. The full repository gate also passed:
generated contracts, all Python/API tests, Ruff lint/format, Python compilation, ESLint, strict
TypeScript, and the Next.js production build. This remains technical usability evidence and does
not replace the outstanding representative Phase 12 operator sessions.

## Zero-prerequisite portable Windows QA package (2026-10-12)

Added a 64-bit Windows portable distribution that embeds the compiled standalone web application,
Node.js runtime, Python runtime with locked API dependencies, PostgreSQL server and migrations, and
Poppler PDF tools. QA can extract the archive and use `Start VAI.cmd` / `Stop VAI.cmd`; Docker,
Python, Node.js, PostgreSQL, npm, administrator installation, and system services are not required.
Database, evidence, process state, and logs remain within the extracted directory.

An extracted-package smoke test initialized a new bundled PostgreSQL cluster, migrated it through
`0023_bootstrap_revision_delta`, returned HTTP 200 from the API and standalone web application,
verified the bundled `pdftotext` runtime, stopped cleanly, restarted against preserved data, and
stopped cleanly again. This remains a trusted local evaluation package rather than a production
deployment, and it does not replace the outstanding Phase 12 representative human sessions.

## Windows evaluation release readiness (2026-10-12)

Added a native PowerShell packaging path for Windows checkouts, with reproducible Windows and
Linux evaluation archives plus SHA-256 checksums. The web runtime now uses the traced Next.js
standalone server, and production web dependencies were updated to Next.js 16.4.0 with no known
production npm audit findings. GitHub Actions now installs Python dependencies into an isolated
environment instead of the runner's protected system Python and performs a full installer Compose
smoke test after the API and web gates pass.

Fresh Windows verification passed generated-contract checks, Ruff lint/format, Python compilation,
all **106 tests**, ESLint, strict TypeScript, the Next.js production build, and native HTTP smoke
checks for the API health endpoint and built standalone web server. Both installer archives and
their checksum manifest were generated and inspected. Docker Desktop was not installed on this
workstation; the Linux CI installer smoke job built both images, migrated a fresh PostgreSQL
database, received successful API and web responses, built both distribution archives, and checked
their hashes. This release-readiness work is
automated technical evidence only and does not complete the outstanding Phase 12 human operator
protocol.

## AI schedule-change assistant guardrail hardening (2026-10-02)

Prompt contract `1.1.0` now treats both the uploaded workbook and user message as untrusted data,
requires a structured feasibility outcome (`FEASIBLE`, `CONDITIONAL`, or
`NOT_FEASIBLE_WITH_GIVEN_EVIDENCE`), and requires explicit evidence gaps. It prohibits fabricated
crews, productivity, access, permits, calendars, approvals, funding, entitlement, or scope, and
instructs the model to preserve facts when it cannot support a change. The generated report and
manifest record prompt version and source-workbook SHA-256. A simplified operator/product guide is
available at `docs/18-schedule-change-assistant.md`.

## AI schedule-change proposal assistant (2026-10-02)

Added `/bootstrap/schedule-assistant` as the BOQ-to-Schedule sub-navigation for a server-only
GPT-5.6 Sol schedule-change assistant. An operator uploads a VAI six-column MS Project import XLSX
and describes a desired delay, deadline compression, resequencing, duration, or dependency change.
The assistant returns a ZIP containing a proposed re-import XLSX, an actionable Word report, and a
JSON manifest. The report identifies the changed tasks, construction strategy, assumptions, risks,
constraints, and planner actions before re-import and recalculation in Microsoft Project.

The model receives a strict full-schedule JSON contract and is prompted as a construction planner
across work fronts, trade sequence, procurement, approvals, inspections, cure times, testing,
commissioning, and practical parallelization. Server validation preserves every original task ID
and name, restricts edits to duration/dates/predecessors, rejects invalid dates, unknown/self
dependencies, and dependency cycles. The output is deliberately a proposal only: it cannot approve,
baseline, or change an existing authorized schedule. Configuration is server-only through
`VAI_OPENAI_API_KEY` and `VAI_OPENAI_SCHEDULE_ASSISTANT_MODEL` (default `gpt-5.6-sol`).

Focused service tests passed (**3 tests**) for the import contract, task-identity preservation,
cycle rejection, and valid Word-package generation. Python compilation and whitespace checks also
passed. Ruff and the web TypeScript/build checks remain unavailable because the current local dev
toolchain is incomplete; this and representative planner verification remain required before
acceptance.

## Bootstrap planner-review usability continuation (2026-10-02)

The governed `/bootstrap/advanced` planner-review stage no longer requires an operator to author
raw edit JSON for normal material corrections. It now lets a planner stage, inspect, replace, and
remove multiple activity-name or responsible-owner edits before submitting the immutable review.
Each staged edit retains the current displayed original value, required reason, and API-approved
field path; duration and logic remain deliberately routed through a new reviewed draft and CPM
calculation. The server still performs its authoritative original-value check and records actor and
timestamp in append-only release history.

Focused CPM/release integration coverage passed (**2 tests**) on 2026-10-02. Web typecheck, lint,
and build could not run in this checkout because its Node dependency installation is incomplete
(`node_modules/.bin/tsc` is absent); an attempted `npm ci --ignore-scripts` did not finish within
the local command window. This is verification debt, not evidence of a completed operator-acceptance
gate.

## OpenAI specialist-agent automation continuation (2026-09-21)

The five Phase 10 specialist boundaries now have separate versioned JSON prompt contracts: Evidence & Progress, Schedule & Dependency, Cost & Commercial Control, Forecast & Scenario, and Impact & Priority. A shared Responses API adapter requests strict JSON-schema output, minimizes input to the selected immutable result and snapshot, rejects evidence references outside the supplied allowlist, records model/prompt/response lineage, and caps AI confidence at the deterministic upstream confidence. When an API key is configured, agent findings enrich the immutable `SpecialistRun`; the deterministic orchestrator continues to own contradictions, readiness, disposition, and governance routing. Without a key it retains the prior deterministic fallback. An agent exception remains visible as a failed specialist and invokes the existing critical/noncritical failure gates. The full repository gate passed with **102 tests**, generated-contract freshness, Ruff lint/format, Python compilation, ESLint, strict TypeScript, and the Next.js production build. A configured-key live OpenAI run remains the next verification step.

The customer BOQ-to-schedule request no longer accepts an OpenAI key or Excel template. Credentials are read only from server configuration, with a generic unavailable response when the administrator has not configured AI. VAI now constructs the standard six-column MS Project workbook internally for every tenant. Browser IndexedDB template storage and its upload UI were removed; future credential rotation belongs in a separately authorized administrator surface. The resulting request contract contains only `boq`, `project_start`, and optional `target_finish`. The full repository gate passed with **103 tests**, generated-contract freshness, Ruff, ESLint, strict TypeScript, Python compilation, and the production web build; tests explicitly ran with the API key disabled to prevent external requests.

Live server-only generation was verified on 2026-09-21 against the representative `BOQ 2.pdf` using the configured `gpt-5` schedule model and a 2026-10-01 project start. The API returned HTTP 200 and a built-in workbook containing one `Tasks` sheet, the exact six headers, 30 consolidated activities, sequential IDs, and no invalid predecessor references. The proposal's latest finish was 2028-04-30; no target finish was supplied, and this generated programme remains subject to planner review. The Orchestration UI now exposes each specialist's `OPENAI_AGENT` or deterministic-fallback execution mode, model, prompt version, response ID, validated findings/calculations, limitations, contradictions, evidence requests, and recorded failure class. Frontend lint, strict TypeScript, and production build passed after this display change.

## Accepted product amendment — BOQ-to-Schedule Bootstrap

Status: **in progress; B0.1–B0.5 complete; B0.6–B0.8 under verification**.

The BOQ-to-Schedule Bootstrap Amendment v1.0, implementation brief, and frozen 19-stage canonical record supplied on 2026-09-15 were reviewed as product-definition input. The duplicate amendment files were byte-for-byte identical.

The review confirmed a material operational gap: the application can preserve generic evidence, validate manually supplied BOQ/schedule contexts, authorize a supplied schedule, and analyze an authorized schedule, but it cannot yet transform an Excel/PDF BOQ into a traceable, validated, human-reviewable schedule draft.

The repository plan is recorded in `docs/17-boq-to-schedule-bootstrap.md`. It adds eight corrective slices covering source preservation, extraction/normalization, classification, WBS/work packages, activities and duration bases, dependencies/milestones/calendars, deterministic CPM/validation, planner review, authority approval, export, and revision deltas. All BS-001 through BS-010 gates are mandatory.

Existing Phase 0–11 implementation remains reusable downstream. Phase 12 stays open, and its representative human sessions must exercise the BOQ-first workflow after the bootstrap UI exists. Do not begin Phase 13 until this corrective track and the amended Phase 12 acceptance are complete.

### B0.1 — Bootstrap contracts and immutable BOQ source preservation

Status: **complete**.

Delivered:

- Added shared extraction status, BOQ row class, activity archetype, planning confidence, assumption status, schedule-draft state, and planning-review state taxonomies in schema version `1.2.0`.
- Added immutable project-scoped BOQ source versions linked to existing governed evidence artifacts, exact SHA-256 content digests, parser/version, predecessor, sequential version number, extraction status/confidence, structure manifest, warnings, actor, and idempotent request hash.
- Added immutable raw BOQ source rows with sheet/page/row/region provenance, exact raw values, original-text slot, extraction confidence, and warnings.
- Added deterministic XLSX/XLSM extraction across all worksheets. It retains every non-empty raw row, preserves formulas without evaluating them, and records merged ranges, hidden sheets/rows/columns, workbook dimensions, and formula warnings.
- Added fail-closed PDF intake: the artifact and source version are preserved, but extraction remains `VERIFICATION_REQUIRED` at zero confidence until a governed text/OCR adapter is selected.
- Added revision-lineage gates requiring the latest prior BOQ source and an evidence artifact that explicitly supersedes the prior artifact. Re-import never mutates a prior source or authorized schedule.
- Added role-scoped create/list/detail APIs, audit provenance, idempotent replay and mismatch handling, migration `0016_boq_source_versions`, and append-only PostgreSQL triggers for both source versions and raw rows.

Verification evidence:

- Full Python/API suite passed: **85 tests**, including multi-sheet extraction, raw formula preservation, merged/hidden structure warnings, content-hash lineage, idempotent replay/mismatch, sequential revisions, and fail-closed PDF intake.
- Generated-contract freshness, Ruff lint/format, Python compilation, ESLint, strict TypeScript, and the Next.js production build passed.
- Live PostgreSQL `0015_learning_records → 0016_boq_source_versions → 0015_learning_records → 0016_boq_source_versions` migration rehearsal passed.
- Both append-only triggers were present after re-upgrade. Direct update probes against a source version and raw source row were rejected, and rollback left no probe records.
- Alembic offline PostgreSQL SQL generation passed through `0016_boq_source_versions`.

Boundary: this slice preserves and extracts raw source structure; it does not normalize commercial fields, classify schedule relevance, generate WBS/work packages or activities, calculate a schedule, or authorize any planning state. Those begin in B0.2.

### B0.2 — BOQ normalization and row classification

Status: **complete**.

Delivered:

- Added immutable normalization runs linked to one exact B0.1 source version, with normalizer version, detected/explicit header rows, canonical column mappings, warnings, counts, actor, and idempotent request hash.
- Added immutable canonical BOQ lines for every extracted raw row, preserving stable line identity, exact source location/row, original row text, normalized values, unmapped values, and raw-source lineage.
- Normalized item number, division, source WBS, item name, description, unit, quantity, unit/total price, currency, location, trade, package, notes, and parent section without modifying raw source values.
- Added deterministic header detection using controlled aliases plus explicit one-based per-sheet mapping overrides for irregular spreadsheets. Unknown mappings and all unmapped cells remain visible.
- Implemented all ten BOQ row classes with stored classification basis, planning confidence, review state, validation warnings, and an explicit schedule-relevance flag.
- Enforced the BS-001 boundary: title/section headers, repeated headers, subtotals/totals, provisional allowances, material-only lines, and unknown rows are preserved but cannot be treated as direct schedulable scope.
- Numeric formulas are never evaluated as authoritative values; invalid/formula quantities or prices remain null with visible verification warnings. Ambiguous rows remain `UNKNOWN_REVIEW_REQUIRED` and `REVIEW_REQUIRED`.
- Added role-scoped normalization create/detail APIs, audit provenance, idempotent replay/mismatch rejection, migration `0017_boq_normalization`, and append-only PostgreSQL protection for normalization runs and canonical lines.

Verification evidence:

- Focused BOQ API coverage passed across all ten row classes, multi-sheet header detection, canonical fields, formula warnings, stable raw lineage, unmapped preservation, schedule-relevance gates, idempotent replay, and mismatch rejection.
- Full repository gate passed: generated contracts, **85 Python/API tests**, Ruff lint/format, ESLint, Python compilation, strict TypeScript, and the Next.js production build.
- Live PostgreSQL `0016_boq_source_versions → 0017_boq_normalization → 0016_boq_source_versions → 0017_boq_normalization` migration rehearsal passed.
- Both B0.2 append-only triggers were present after re-upgrade. Direct update probes against a normalization run and canonical line were rejected, and rollback left no probe records.
- Alembic offline PostgreSQL SQL generation passed through `0017_boq_normalization`.

Boundary: B0.2 classifies proposed planning scope but does not create a WBS, work package, activity, duration, dependency, schedule calculation, or authorized planning state. B0.3 begins proposed WBS/work-package formation.

### B0.3 — Proposed WBS and work-package formation

Status: **complete**.

Delivered:

- Added deterministic proposed planning structures with project-root WBS nodes, preserved source-WBS codes, controlled grouping dimensions, work packages, exact BOQ-line mappings, visibly unmapped rows, assumptions, warnings, and change summaries.
- Every schedule-relevant normalized line maps to exactly one proposed work package in the initial version. Non-schedulable and unknown classes remain present with explicit unmapped reasons rather than disappearing or becoming activities.
- Missing WBS dimensions fall back to the project node only through a visible low-confidence review assumption; the engine does not fabricate location, trade, crew, responsibility, or construction-system data.
- Added immutable successor versions for planner package split, package merge, line remap, proposal acceptance, and proposal rejection. Each stores actor, reason, action, exact predecessor, affected IDs, and idempotent request hash.
- Added latest-version enforcement so stale planning structures cannot be revised. Planner acceptance produces `REVIEWED`, never an authorized schedule or baseline.
- Added schema version `1.3.0` planning-structure status/action taxonomies, role-scoped create/list/revision APIs, audit provenance, migration `0018_boq_planning_structure`, and append-only PostgreSQL protection.

Verification evidence:

- Focused API coverage passed for generated mapping/unmapped completeness, non-authorization, idempotent replay, two-way split, stale-version denial, merge, line remap, acceptance, rejection, and complete immutable version history.
- Full repository gate passed: generated contracts, **85 Python/API tests**, Ruff lint/format, ESLint, Python compilation, strict TypeScript, and the Next.js production build.
- Live PostgreSQL `0017_boq_normalization → 0018_boq_planning_structure → 0017_boq_normalization → 0018_boq_planning_structure` migration rehearsal passed.
- The planning-structure append-only trigger was present after re-upgrade. A direct update was rejected and the rollback-safe probe left no record.
- Alembic offline PostgreSQL SQL generation passed through `0018_boq_planning_structure`.

Boundary: B0.3 creates reviewable planning structure only. It does not generate schedule activities, durations, productivity assumptions, dependencies, CPM results, or any authorized schedule state. B0.4 begins activity and duration generation.

### B0.4 — Activity, duration, productivity, and assumptions

Status: **complete**.

Delivered:

- Added immutable schedule-draft generations bound to the exact latest planner-reviewed B0.3 structure. Proposed or stale structure versions fail closed.
- Generated activities by work package and required archetype, not by BOQ row. Direct execution creates `EXECUTION`; procurement scope creates `SUBMITTAL`, `PROCUREMENT`, and `DELIVERY`; testing, approval, and preliminaries use their bounded archetypes.
- Preserved every activity's WBS/work-package and one-or-many BOQ-line references. Empty packages are skipped with warnings rather than producing untraceable tasks.
- Implemented the duration hierarchy available in this slice: explicit reviewed project duration first, compatible quantity plus supplied productivity second, otherwise unresolved. Calculations retain exact unrounded duration and deterministic ceiling to whole working days.
- Stored full productivity provenance including rate/unit, source type/reference/date/version, applicability, confidence, and review state. Company benchmarks, controlled libraries, and explicit assumptions create visible first-class planning assumptions rather than project facts.
- Added first-class assumptions with proposition, reason, affected activities, source basis, confidence, consequence if wrong, validation owner, status, and resolution slot.
- Mixed/missing quantity units never aggregate silently. No crew count, shift factor, efficiency factor, overtime, duration, calendar, or date is invented.
- Added duration/productivity taxonomies in schema version `1.4.0`, role-scoped generate/detail APIs, audit provenance, migration `0019_schedule_draft_generation`, and append-only protection for generations, activities, and assumptions.

Verification evidence:

- BS-002 coverage proves two concrete BOQ rows become one traceable execution activity: 200 m³ divided by an explicit project rate of 50 m³/working day retains an unrounded four-day calculation and deterministic four-day duration.
- BS-005 coverage proves five unsupported activity durations remain null/`VERIFICATION_REQUIRED` with five open validation assumptions; no high-confidence duration is fabricated.
- Focused coverage also verifies procurement archetypes, skipped empty packages, exact BOQ references, reviewed/latest structure gates, idempotent replay, and draft-level verification state.
- Full repository gate passed: generated contracts, **85 Python/API tests**, Ruff lint/format, ESLint, Python compilation, strict TypeScript, and the Next.js production build.
- Live PostgreSQL `0018_boq_planning_structure → 0019_schedule_draft_generation → 0018_boq_planning_structure → 0019_schedule_draft_generation` migration rehearsal passed.
- All three B0.4 append-only triggers were present after re-upgrade. Direct update probes for a generation, activity, and assumption were rejected; rollback left no probe data.
- Alembic offline PostgreSQL SQL generation passed through `0019_schedule_draft_generation`.

Boundary: B0.4 creates proposed activities and duration evidence only. It does not generate dependencies, calendars, milestones, dates, float, CPM results, or an authorized schedule. B0.5 begins dependency, milestone, constraint, and calendar proposals.

### B0.5 — Dependencies, milestones, calendars, and constraints

Status: **complete**.

Delivered:

- Added one immutable schedule-logic proposal per exact B0.4 draft generation, retaining typed dependencies, signed lag, derivation basis, confidence, review state, milestones, constraints, calendar, sequence templates, assumptions, warnings, actor, and idempotent request hash.
- Added deterministic procurement prerequisites from `SUBMITTAL` to `PROCUREMENT` to `DELIVERY`, plus explicit imported relationships and configurable validated sequence templates. Duplicate, self-referential, and unknown-activity relationships fail closed.
- Added proposed milestones with source provenance and proposed constraints with affected activities. Contract evidence remains evidence only: all milestones and constraints are explicitly `PROPOSED` and unauthorized.
- Required either a supplied reviewed working calendar or a visible low-confidence Monday–Friday/eight-hour assumption requiring planner review. No dates are calculated in this slice.
- Added dependency-basis and milestone-source taxonomies in schema version `1.5.0`, role-scoped create/detail APIs, audit provenance, migration `0020_schedule_logic`, and append-only PostgreSQL protection.

Verification evidence:

- Focused API coverage passed for reviewed six-day calendars, explicit approval-release prerequisites, validated sequence templates, deterministic procurement chains, proposed contract milestones and constraints, idempotent replay, and exact retrieval.
- Full repository gate passed: generated contracts, **85 Python/API tests**, Ruff lint/format, ESLint, Python compilation, strict TypeScript, and the Next.js production build.
- Live PostgreSQL `0019_schedule_draft_generation → 0020_schedule_logic → 0019_schedule_draft_generation → 0020_schedule_logic` migration rehearsal passed.
- The B0.5 append-only trigger was present after re-upgrade.
- Alembic offline PostgreSQL SQL generation passed through `0020_schedule_logic`.

Boundary: B0.5 creates proposed schedule logic and calendar evidence only. It does not calculate dates, float, criticality, deadline variance, or an authorized schedule. B0.6 begins deterministic CPM and validation.

### B0.6 — Deterministic CPM and validation continuation

Status: **technical path verified; operator acceptance pending**.

Migration `0021_bootstrap_cpm` stores immutable input-bound calculations. CPM calculates relationship-specific float and negative float; rejects empty schedules, fractional lags/durations, excessive horizons, incomplete BOQ coverage, duplicate scheduling, missing procurement prerequisites, weak critical inputs, material milestone feeder omissions, and conflicting date constraints. Planner review is blocked when material validation findings remain. Focused cycle, constraint, finish-to-start, start-to-start, negative-float, fractional-lag/duration, weak-input, and missing-prerequisite tests passed.

### B0.7 — Planner review and governed publication continuation

Status: **technical path verified; operator acceptance pending**.

Migration `0022_bootstrap_release` stores immutable planner review and separate authorized release versions. Repeat authorization of one reviewed release is rejected, and approval requires the exact active human grant. JSON/CSV/XLSX exports distinguish proposal from authority and retain BOQ/activity traceability. The `/bootstrap` page exposes the twelve BOQ-first stages, uploads BOQ files directly, carries created IDs forward, displays package/activity/assumption and validation details, provides simple planner name/owner edits and a separate admin grant form, and downloads authenticated exports. It still requires technical JSON input for durations and logic; representative human usability acceptance remains outstanding.

### B0.8 — Revision delta and conformity continuation

Status: **technical path verified; operator acceptance pending**.

Migration `0023_bootstrap_revision_delta` stores immutable scope/mapping/activity comparisons and proposed CPM finish deltas when both versions have calculations. Duplicate BOQ line occurrences remain distinct. Missing downstream drafts are explicitly `PENDING_REGENERATION`. A supplied prior release must be authorized and derive from the predecessor BOQ; the existing current-authorized context is untouched until a separate reviewed revision is approved. A realistic XLSX integration test passed upload through normalization, two-to-one BOQ/activity mapping, project-productivity duration, reviewed calendar, CPM, planner review, active-grant authorization, and revision isolation.

Combined verification on 2026-09-16: the full repository gate passed—generated contracts, **95 Python/API tests**, Ruff lint/format, ESLint, Python compilation, strict TypeScript, and production build. Live PostgreSQL `0020 → 0023 → 0020 → 0023` migration rehearsal passed, and all three append-only triggers were present after re-upgrade. The local API and web server started successfully after correcting the `make api` target to use the locked Uvicorn dependency; `/health` and `/bootstrap` returned successful responses.

Remaining acceptance: run the BS-001–BS-010 conformity checkpoint and representative human operator sessions in the actual browser, including technical-input usability and revision schedule-effect interpretation. Do not mark B0.6–B0.8 or Phase 12 complete from API automation alone.

## Completed phases

### Phase 0 — Bootstrap and frozen contracts

Status: **complete**.

Delivered:

- Git worktree, repository structure, local environment template, Make targets, and CI workflow.
- Accepted modular-monolith architecture decision.
- Canonical versioned taxonomy source and generated Python/TypeScript contracts.
- Deterministic semantic guards for analytical write boundaries, truth derivation, and human decisions.
- FastAPI skeleton with health and taxonomy metadata endpoints.
- Next.js Decision Center shell consuming the shared generated contract.
- PostgreSQL compose service and reversible Alembic bootstrap migration.
- Locked Node and Python dependency sets.
- Unit/API tests and lint, type, build, migration, and generated-file checks.

Verification evidence:

- 15 Python/API tests passed.
- Ruff passed.
- ESLint and TypeScript passed.
- Next.js production build passed.
- Generated-contract freshness check passed.
- Alembic offline SQL generation passed.
- Live PostgreSQL upgrade → downgrade → upgrade rehearsal passed; expected three bootstrap tables were restored.

Non-blocking observation: the current FastAPI/Starlette test client emits upstream deprecation warnings on Python 3.14. Tests pass; dependency updates should be evaluated in the normal maintenance cycle.

### Phase 1 — Identity, project, and control context

Status: **complete with an explicit external-integration limitation**.

Delivered:

- Organization/project tenancy and organization-bound access checks.
- Database-backed organization/project roles and scoped authority grants with escalation level/target.
- Development identity adapter that fails closed outside development/test.
- Project timezone, currency, delivery model, reporting cadence, and working calendar.
- Extensible controlled-object graph, ownership, and typed relations.
- Typed schedule, budget, and BOQ source payloads with semantic validation.
- Immutable `BASELINE`/`PROPOSED` sources and approval-backed `CURRENT_AUTHORIZED` copies.
- Partial unique database constraint preventing multiple current authorized contexts per type/project.
- Superseded authorized-context history and activation audit records.
- Project activation gate requiring a current authorized schedule.
- Read APIs for projects, members, objects, relations, grants, context versions/current context, and project audit ledger.
- Browser-based development setup flow for the initial organization and project.

Verification evidence:

- 23 API/domain/integration tests passed, including tenant denial, analyst activation denial, typed schedule validation, project activation gate, and production identity fail-closed behavior.
- Live PostgreSQL migration upgrade → downgrade → upgrade passed at revision `0002_control_context`.
- Live PostgreSQL API smoke passed from organization creation through active authorized schedule and audit ledger.
- Python formatting/lint, generated contracts, ESLint, TypeScript, and Next.js production build passed.

Limitation: the production OIDC provider, issuer, audience, and claims mapping have not been selected. Production identity therefore returns `503` instead of trusting development headers. This preserves the governance boundary until the external identity decision is made.

### Phase 2 — Evidence model and intake

Status: **complete with explicit production-adapter limitations**.

Delivered:

- Immutable evidence artifact registry with raw-content storage, SHA-256 digest, source/provider/timestamp/classification provenance, version links, size limits, file-content checks, and recorded malware-scan metadata.
- Typed evidence assertions preserving numeric zero, distinguishing `UNKNOWN` from null misuse, requiring a basis for progress, supporting expiry/staleness, and retaining supersession/derivation lineage.
- Separate verification events: a verified result creates a new `VERIFIED_FACT` linked to its unchanged source claim, preventing silent truth inflation.
- Append-only PostgreSQL protections for artifacts, verification events, and source-reliability assessments, plus immutable assertion fields while permitting explicit status supersession.
- Supporting, contradicting, and derived-from evidence relations with query APIs.
- Material contradiction records and explicit resolution policy/reason/selected evidence without deleting either assertion.
- Evidence requests with object/field matching and traceable satisfaction.
- Versioned source-reliability history.
- Artifact upload/download and project-scoped evidence, relation, verification, reliability, contradiction, request, and import APIs with role enforcement and audit events.
- CSV/XLSX import preview, explicit header mapping, controlled-object resolution, row-level validation reports, rejected-batch gates, and idempotent commit.
- Browser Evidence Workbench for artifact intake, manual typed claims, evidence-ledger review, and explicit human verification.
- Shared Python/TypeScript evidence taxonomies and locked spreadsheet/multipart dependencies.

Verification evidence:

- 33 API/domain/integration tests passed, including artifact integrity and rejection gates, CSV/XLSX intake, invalid-row reporting, idempotent preview/commit, zero/unknown semantics, progress-basis enforcement, verification lineage, contradictions, requests, reliability history, supersession, and role denial.
- Live PostgreSQL `0002_control_context → 0003_evidence → 0002_control_context → 0003_evidence` migration rehearsal passed.
- Live PostgreSQL API smoke passed for artifact intake, numeric-zero reported evidence, separate verified fact, derived relation, verification event, and evidence audit records.
- A direct PostgreSQL attempt to mutate an evidence assertion was rejected by the database trigger.
- Ruff, generated-contract freshness, ESLint, strict TypeScript, and the Next.js production build passed.

Limitations: production object storage and a maintained production malware-scanning engine have not been selected. The local object store and deterministic EICAR gate are development/test adapters only; both dependencies fail closed with `503` outside development/test. File extension/content validation and upload-size enforcement remain active at the application boundary.

### Phase 3 — Signals, screening, and case correlation

Status: **complete**.

Delivered:

- Five deterministic, versioned candidate-detector families for progress variance, schedule variance, cost variance, unresolved evidence conflict, and milestone exposure.
- Explicit detector thresholds, source evidence/contradiction lineage, controlled-object scope, observed values/times, expiry, and initial materiality candidates.
- Stable project-scoped fingerprints and evidence links that deduplicate repeated observations without losing occurrence/source lineage.
- Idempotent detection runs with request-payload hashing and mismatch rejection.
- Signal lifecycle distinct from Decision Cases: `CANDIDATE`, `SCREENED`, `DEFERRED`, `DISMISSED`, `CORRELATED`, and `EXPIRED`.
- Reason-coded relevance, defer, and dismissal screening with append-only decision history and optimistic workflow-version checks.
- Explicit due-signal expiry command and stale-version protection.
- Deterministic case-correlation suggestions for `OPEN_NEW`, `LINK_EXISTING`, and `CROSS_CUTTING_PARENT_CHILD`, including visible rationale and confidence.
- Human-reviewed correlation acceptance/rejection; suggestions never open/link/merge cases autonomously.
- Minimal Phase 3 Decision Case shells and signal/object links needed for reviewed correlation. Full lifecycle, snapshots, sufficiency, and case ledger remain Phase 4 work.
- Independent-object protection: an unrelated signal receives `OPEN_NEW` even when another project case exists, preventing project-wide forced merging.
- Reviewed cross-cutting parent creation requiring at least two explicit child cases.
- Transactional outbox records for `SignalRaised`, `SignalScreened`, `CaseOpened`, and `SignalLinked`, alongside project audit events.
- Filterable/paginated signal APIs, screening history, correlation review, case-shell query, and outbox query projections.
- Browser Signal Inbox for detector execution, status filtering, screening, correlation explanation, and explicit accept/reject actions.
- Shared Python/TypeScript signal, screening, materiality, and correlation taxonomies.

Verification evidence:

- 38 API/domain/integration tests passed, including all five detectors, fingerprint/run idempotency, idempotency mismatch, occurrence preservation, stale-version rejection, defer reason/deadline, expiry, correlation rejection, reviewed new/existing/cross-cutting outcomes, independent-signal non-merging, tenant membership denial, and transactional outbox creation.
- Live PostgreSQL `0003_evidence → 0004_signals → 0003_evidence → 0004_signals` migration rehearsal passed.
- Seven Phase 3 tables and four append-only triggers were verified after re-upgrade.
- Live PostgreSQL API smoke passed from evidence assertion through signal detection, screening, reviewed case opening, signal linkage, audit, and four outbox events.
- A direct PostgreSQL attempt to mutate a screening decision was rejected by the append-only trigger.
- Ruff, generated-contract freshness, ESLint, strict TypeScript, and the Next.js production build passed with the `/signals` route.

Phase boundary: detector thresholds are explicit deterministic defaults in detector version `1.0.0`. Project/delivery-model policy versioning and replay impact belong to the later policy/evaluation phases. The `decision_case` record is intentionally a correlation shell; it does not yet imply readiness, recommendation, human disposition, or execution authority.

### Phase 4 — Decision Case lifecycle and sufficiency

Status: **complete**.

Delivered:

- Expanded Decision Case aggregate with optimistic versions, explicit ownership, separate lifecycle/readiness/governance/autonomy state, governed forward transitions, and block/resume/close/reopen rules.
- Immutable, idempotent case snapshots capturing exact case version, data date, controlled objects, signals, attached evidence, unresolved contradictions, effective authorized context, active responses, policy version, and deterministic content hash.
- Append-only baseline and conclusion-specific sufficiency assessments with visible policy `PHASE4-SUFFICIENCY-1.0.0`.
- Exact missing, stale, weak, contradictory, unauthorized-context, baseline-validity, and active-response limitations; materiality, owner, deadline, and linked evidence-request records are retained.
- Readiness outcomes `DECISION_READY`, `DECISION_READY_WITH_LIMITATIONS`, `VERIFICATION_REQUIRED`, and `INSUFFICIENT`, including maximum-supported-conclusion projection and lifecycle stop gates.
- Baseline challenge and historical effective-context selection without rewriting the frozen snapshot.
- Authorized active-response references and response-aware snapshot/sufficiency behavior.
- Chronological append-only case ledger, project audit entries, and transactional `CaseClosed`/`CaseReopened` outbox events.
- Closure requiring an outcome reference or admin-authorized rationale; reopening requiring a material trigger, with referenced new evidence and failed-response validation where applicable.
- Browser Decision Case Center for evidence assembly, snapshots, sufficiency, limitations, active responses, lifecycle movement, blocking/resuming, baseline challenges, closure, reopening, and ledger inspection.
- Shared Python/TypeScript conclusion, baseline, limitation, response, ledger, and reopen-trigger taxonomies.

Verification evidence:

- 43 API/domain/integration tests passed, including snapshot idempotency/hash persistence, conclusion-specific exact gaps, missing-context and weak-truth stops, disputed baselines, material contradictions, active-response limitations, lifecycle gates, stale versions, block/resume, closure basis, material-evidence reopening, failed-response reopening rejection, tenant isolation, and unsupported-policy rejection.
- Live PostgreSQL `0004_signals → 0005_decision_cases → 0004_signals → 0005_decision_cases` migration rehearsal passed.
- Seven Phase 4 tables, seven protection triggers, and three aggregate taxonomy constraints were verified after re-upgrade.
- Live PostgreSQL API smoke passed through case opening, verified evidence attachment, authorized schedule and active response, immutable snapshot, schedule-intervention sufficiency, governed limitation resolution, closure, and material-evidence reopening.
- Direct PostgreSQL attempts to mutate a frozen snapshot or the immutable fields of a limitation were rejected by database triggers.
- Ruff, generated-contract freshness, ESLint, strict TypeScript, and the Next.js production build passed with the `/cases` route.

Phase boundary: Phase 4 evaluates whether evidence supports a named conclusion; it does not yet calculate progress reconciliation, persistent trends, schedule consequence paths, cost forecasts, recommendation dispositions, or a human management decision. Those remain intentionally downstream.

### Phase 5 — Progress truth and deviation intelligence

Status: **complete**.

Delivered:

- Evidence-backed immutable progress measurements that keep `PLANNED_AUTHORIZED`, `REPORTED`, `EXECUTED`, `VERIFIED`, and `ACCEPTED_RELEASED` gates separate.
- Explicit progress bases, numerator, denominator, unit, completion ratio, as-of time, semantic state, truth type, confidence, controlled object, and source-evidence lineage.
- Authorized schedule progress curves tied to controlled-object codes; planned measurements must exactly match a point in the schedule version authorized at their as-of time.
- Compatible-basis, compatible-unit, and compatible-denominator gates that reject false percentage comparisons.
- Snapshot-bound, idempotent progress evaluations with deterministic request hashing and optimistic Decision Case version checks.
- Reconciled gate projection, planned-versus-actual variance direction and magnitude, visible threshold crossing, duration, trend direction, and persistence.
- A visible default threshold policy plus immutable project policy versions. Policy changes affect explicitly selected future evaluations without rewriting prior results.
- Persistence requiring three consistent threshold-crossing observations across seven days by default; a single observation remains `TRANSIENT`.
- Planned and actual productivity from paired cumulative observations, including exact prior/current input lineage and formula version.
- Derived truth propagation: ordinary calculations remain `DERIVED_METRIC`; unresolved source contradictions produce `CONTRADICTED` output and `VERIFICATION_REQUIRED` reconciliation instead of a stronger assertion.
- Confidence capped at the weakest selected input and explicit limitations for weak actual truth, unresolved contradictions, and undefined zero-plan productivity.
- Append-only progress policies, measurements, and evaluations, with the latest evaluation referenced by—but not merged into—the Decision Case aggregate.
- Browser Progress Reconciliation workbench and Decision Case progress panel showing separated gates, measurement bases, truth labels, deviation, productivity, trend, and persistence.
- Shared Python/TypeScript progress-kind, reconciliation, deviation, trend, and persistence taxonomies.

Verification evidence:

- 46 API/domain/integration tests passed, including separated progress gates, exact authorized-plan lineage, normalization idempotency, incompatible-basis rejection, snapshot containment, derived truth preservation, contradiction propagation, custom threshold selection, three-observation/seven-day persistence, productivity calculation, policy immutability, and tenant/case controls inherited from prior phases.
- Live PostgreSQL `0005_decision_cases → 0006_progress_intelligence → 0005_decision_cases → 0006_progress_intelligence` migration rehearsal passed.
- Three Phase 5 tables and three append-only triggers were verified after re-upgrade.
- Live PostgreSQL API smoke passed through authorized time-phased plan creation, verified progress normalization, case snapshot, and a `BEHIND` transient derived deviation.
- Direct PostgreSQL mutation attempts against a threshold policy, normalized measurement, and progress evaluation were rejected by database triggers.
- Generated-contract freshness, Ruff, Python formatting/compilation, ESLint, strict TypeScript, and the Next.js production build passed with the `/progress` and enhanced `/cases` routes.

Phase boundary: Phase 5 establishes current progress truth and deviation persistence. It does not infer schedule dependency consequences, forecast completion, diagnose root cause, recommend a disposition, or record a human decision.

### Phase 6 — Schedule and dependency intelligence

Status: **complete**.

Delivered:

- Typed schedule calendars, activity calendar references, constraints, four dependency relation types, milestones, controlled-object mappings, network-completeness declaration, and optional supplied total float.
- Schedule source validation for unique activities/calendars/milestones, known references, acyclic dependency graphs, valid constraints, valid dates, and valid custom working calendars before authorization.
- Current and historical authorized schedule-network projection; baseline or proposed sources are never presented as authorized.
- Snapshot-bound schedule assessment resolving the exact schedule version effective at the case data date.
- Evidence-backed activity delay with controlled-object scope, day units, observed/verified semantic-state gates, source truth/confidence lineage, and snapshot containment.
- Deterministic calendar-aware logic slack and float calculation where supplied float is unavailable and policy permits calculation.
- Explicit downstream activity paths, residual delay after available slack, affected activities, material milestone exposure, and project-completion exposure.
- Timing direction, exposure level, schedule quality, assessment status, and maximum supported schedule conclusion stored separately.
- Visible default schedule-quality policy plus immutable project policy versions for timing tolerance, schedule freshness, dependency requirement, and calculated-float permission.
- Exact limitations for stale/future schedule data dates, unconfirmed network completeness, activity/object mapping gaps, logic/date inconsistency, unavailable float, weak delay evidence, and unresolved contradiction.
- `INSUFFICIENT` or `VERIFICATION_REQUIRED` assessments restrict the maximum conclusion to local timing variance rather than implying unsupported downstream consequence.
- Append-only, idempotent schedule assessments with request hashing, formula version, optimistic case versioning, audit/ledger records, and the latest assessment pointer on the Decision Case.
- Browser Schedule Intelligence network/policy workbench and Decision Case schedule panel with path, float, milestone, quality, truth, confidence, and limitation visibility.
- Shared Python/TypeScript schedule relationship, constraint, quality, assessment, timing, float, exposure, and conclusion taxonomies.

Verification evidence:

- 51 API/domain/integration tests passed, including cyclic-network and constraint rejection, custom calendars, schedule network projection, large-delay float absorption, smaller-delay milestone exposure, explicit path lineage, weak/stale/incomplete schedule restrictions, custom policy replay, idempotency, and approved-change comparison against the newly effective authorized version.
- Live PostgreSQL `0006_progress_intelligence → 0007_schedule_intelligence → 0006_progress_intelligence → 0007_schedule_intelligence` migration rehearsal passed.
- Two Phase 6 tables and two append-only triggers were verified after re-upgrade.
- Live PostgreSQL API smoke passed from a validated authorized network and verified delay through a three-day material-milestone exposure with the exact `A-SOURCE → B-MILESTONE` path.
- Direct PostgreSQL attempts to mutate a schedule policy or assessment were rejected by database triggers.
- Generated-contract freshness, Ruff, Python formatting/compilation, ESLint, strict TypeScript, and the Next.js production build passed with the `/schedule` and enhanced `/cases` routes.

Phase boundary: Phase 6 calculates deterministic exposure through authorized schedule logic. It does not forecast future production, assert root cause or contractual liability, recommend a management disposition, or alter the schedule.

### Phase 7 — Cost and commercial intelligence

Status: **complete**.

Delivered:

- Expanded authorized-budget contracts with data date, reporting period, controlled-object scope, measurement basis, approved budget, authorized changes, and derived current authorized budget while retaining backward compatibility.
- Immutable evidence-backed cost records for approved budget, authorized change, commitment, actual, accrual, BOQ value, earned value, and physical value with exact amount, currency, scope, period, basis, semantic state, truth, confidence, evidence, and authorization lineage.
- Current and historical authorized-budget projection; baseline, proposed, or unactivated budget sources are never presented as authorized.
- Snapshot-bound, idempotent cost assessments using the budget version effective at the case data date and optimistic Decision Case version checks.
- Strict compatibility gates for currency, controlled-object scope, reporting period, measurement basis, snapshot containment, and budget authorization version.
- Separate commitments, actuals, accruals, recognized cost, earned/physical value, cost-consumption ratio, progress-value ratio, alignment variance, and unexplained variance.
- Deterministic forecast-to-complete and EAC only after the minimum earned threshold and only from sufficiently strong recognized-cost and earned-value evidence.
- Forecast suppression when commercial timing effects remain unadjusted, preventing prepayment or mobilization timing from becoming a naive overrun forecast.
- Evidence-backed timing, procurement, prepayment, retention, and mobilization explanations with a stored non-liability boundary on every effect.
- `COST_AHEAD`, `COST_BEHIND`, `ALIGNED`, `NOT_COMPARABLE`, and `VERIFICATION_REQUIRED` outcomes that do not imply intervention merely from unlike percentages.
- Exact limitations for zero budget, missing progress/value basis, unsupported physical ratio, multiple value bases, weak evidence, unresolved contradiction, and unsupported forecast inputs.
- Visible default cost policy plus immutable project policy versions for alignment tolerance, minimum earned ratio, and accrual recognition.
- Append-only cost policies, records, and assessments, with case ledger/audit records and the latest cost assessment referenced by—but not merged into—the Decision Case.
- Browser Cost Intelligence workbench and Decision Case cost panel showing authorization, lineage, alignment, explained effects, EAC/FTC, truth, confidence, and limitations.
- Shared Python/TypeScript cost-record, commercial-effect, alignment, assessment, forecast, and conclusion taxonomies.

Verification evidence:

- 55 API/domain/integration tests passed, including cost-only insufficiency, exact authorized-budget projection, authorized BOQ revision/value lineage, misleading prepayment divergence, EAC/FTC calculation, policy versioning, idempotency, and incompatible-currency rejection.
- Live PostgreSQL `0007_schedule_intelligence → 0008_cost_commercial → 0007_schedule_intelligence → 0008_cost_commercial` migration rehearsal passed.
- Three Phase 7 tables and three append-only triggers were verified after re-upgrade.
- A direct PostgreSQL attempt to mutate a cost policy was rejected by the append-only trigger and the smoke-test transaction left no record behind.
- Generated-contract freshness, Ruff, Python formatting/compilation, ESLint, and strict TypeScript passed with the `/cost` and enhanced `/cases` routes.

Phase boundary: Phase 7 provides current cost/commercial alignment and a bounded deterministic EAC where evidence supports it. It does not produce multi-domain future scenarios, assert root cause or contractual liability, recommend a management disposition, approve spend/change, or record a human decision.

### Phase 8 — Forecast and scenarios

Status: **complete**.

Delivered:

- One immutable snapshot-bound forecast contract for production completion, schedule completion, and estimate at completion.
- Deterministic linear production-rate, schedule-delay propagation, and cost-performance-index methods with explicit formula versions and exact upstream specialist-result lineage.
- Point, lower, and upper results with target-specific units; rate ranges use visible low/high productivity factors and cost ranges use visible low/high cost factors.
- Explicit data date, horizon end, horizon duration, assumptions, scenario parameters, limitations, source evidence, and recalculation triggers on every projection.
- Strictly separated `CONTINUED_PERFORMANCE`, `ACTIVE_RESPONSE`, and `HYPOTHETICAL` branches.
- Active-response projections require an authorized active response frozen into the same case snapshot and use only the target-specific quantitative parameter from its recorded details.
- Hypothetical projections require an explicit assumption and the single target-compatible parameter; they are stored as `SCENARIO`, never `FORECAST` or authorized state.
- Continued-performance and active-response projections are stored as `FORECAST`; every projected result is truth-labelled `SCENARIO_ESTIMATE`, never fact, baseline, actual, or authorization.
- Confidence capped by the upstream specialist output and decayed through the selected horizon under an immutable visible policy with a configured floor.
- Forecast validity projection returning `CURRENT`, `EXPIRED`, or `RECALCULATION_REQUIRED` without rewriting prior forecast rows.
- Automatic recalculation detection for newer snapshots, changed upstream progress/schedule/cost results, expired validity, and changed active-response state.
- Append-only forecast policies and forecast history with case versioning, idempotent request hashing, audit/case-ledger entries, and a latest-projection pointer that does not merge forecast into case truth.
- Forecast policy and history APIs with target/scenario filtering and a browser Forecast & Scenarios workbench.
- Decision Case forecast panel for target, specialist input, branch, authorized response, hypothetical parameter, assumptions, horizon, and policy selection.
- Shared Python/TypeScript target, scenario, method, status, validity, and recalculation-trigger taxonomies.

Verification evidence:

- 56 API/domain/integration tests passed, including reproducible/idempotent production forecasts, ordered ranges, horizon confidence decay, active-response acceleration, hypothetical scenario separation, custom policy selection, full version history, changed-snapshot recalculation, schedule completion projection, and versioned cost EAC range.
- Live PostgreSQL `0008_cost_commercial → 0009_forecast_scenarios → 0008_cost_commercial → 0009_forecast_scenarios` migration rehearsal passed.
- Two Phase 8 tables and two append-only triggers were verified after re-upgrade.
- A direct PostgreSQL attempt to mutate a forecast policy was rejected by the append-only trigger and the smoke-test transaction left no record behind.
- Generated-contract freshness, Ruff, Python formatting/compilation, ESLint, and strict TypeScript passed with the `/forecast` and enhanced `/cases` routes.

Phase boundary: Phase 8 projects bounded results under explicit methods and assumptions. It does not convert projections into authorized schedules/budgets, assert cause or consequence severity, prioritize cases, recommend a disposition, approve a response, or record a human decision.

## Current work

### Phase 9 — Consequence, confidence, urgency, and priority

Status: **complete**.

Continued implementation:

- Added `/impact` browser workbench and home navigation for assessment creation and history, separate consequence/confidence/urgency/priority dimensions, five clocks, policy selection, ranking reasons, and consequence lineage.
- Preserved schedule/cost upstream stop gates: restricted specialist assessments cannot become supported consequence paths, and their status and limitations remain visible.
- Material milestone escalation now checks materiality; downstream and completion exposure require positive residual delay, so fully absorbed delay does not raise consequence severity.
- Attached exact specialist-result and evidence IDs to progress/schedule/cost consequence paths.
- Preserved missing-deadline limitations even when another verification restriction also applies.
- Advanced the impact calculation formula to `IMPACT-PRIORITY-1.0.2` for corrected gates and forecast confidence propagation; existing results are not rewritten.
- Added API regression scenarios for consequential versus float-absorbed delay, incomplete-network restrictions, clock interaction, confidence ceilings, idempotency/mismatch, stale case versions, history, tenant access, and unknown deadlines.

Latest continuation — forecast confidence and source propagation:

- Forecast-only impact assessments now resolve their snapshot/object-bound specialist sources and inherit upstream confidence instead of defaulting to zero.
- Source reliability caps truth, forecast, and consequence confidence; the forecast horizon also caps aggregate confidence unless an explicit approved override applies.
- Forecast consequence paths retain specialist/evidence IDs, semantic state, truth type, assumptions, and limitations. Hypothetical scenarios remain qualified as limited assessments.
- Upstream schedule/cost restrictions and forecast limitations remain visible even when only the forecast was selected.
- Added forecast-ID selection to `/impact` and regression scenarios for forecast-only/mixed inputs, hypothetical branches, source reliability, and results beyond the selected horizon.

Verification for this continuation:

- Generated-contract freshness, Python compilation, and whitespace checks passed.
- The workbench component, including forecast selection, passed an isolated strict TypeScript check.
- Six dependency-free confidence-rule tests passed: forecast horizon ceiling, weakest-source reliability, duplicate-input stability, missing/zero input handling, horizon decay, and invalid-input rejection.
- The confidence calculation is isolated in `app/confidence.py`; passing API tests cover the separate persistence, provenance, and authorization boundaries.
- Full Python/API suite passed: **69 tests**, including the previous Phase 9 safeguards and new forecast-confidence scenarios. Locked runtime/test dependencies installed successfully on retry; Ruff remains unavailable after its large download was deferred.
- Alembic offline PostgreSQL SQL generation passed through `0010_impact_priority`; this does not replace live migration/rollback and trigger verification.
- Full web lint/type/build checks are pending: npm installation failed with `ECONNRESET`; a cache-assisted retry was stopped after downloads continued to stall. Initial lint/type checks confirmed incomplete Next.js dependencies, not a passing application check.
- Live PostgreSQL migration rehearsal is pending: Docker CLI is installed, but its configured Colima daemon is not running.

Latest continuation — reviewer confidence override visibility and recovery forecast correction:

- Added a reviewer-facing confidence-override flow in `/impact`: it lists recorded overrides, requires the case version, snapshot, recorded upstream ceiling, approved confidence, and 20-character justification, then refreshes the case version and override history.
- The assessment form can select a recorded override. The API remains authoritative: it rejects an override unless its case, snapshot, and computed upstream confidence ceiling exactly match the new assessment.
- Web type checking remains unverified on this machine because the workspace dependency install is incomplete (`tsc: command not found`).
- Corrected the production-rate forecast dimensional calculation: productivity is a completion-ratio-per-day, so the forecast now divides remaining completion ratio by that rate rather than dividing an absolute remaining quantity by it. The old mismatch inflated completion horizons by the measurement denominator and incorrectly marked valid recovery comparisons as `LIMITED`.
- Advanced the immutable forecast formula to `FORECAST-DETERMINISTIC-1.0.1`; existing forecast rows retain their recorded formula version and are not rewritten.
- Focused forecast/impact/recovery verification passed: **19 tests**. The recovery comparison now passes with the original 60-day horizon while retaining the rule that genuinely limited forecasts cannot qualify for a priority reduction.

Latest continuation — confidence-bounded priority reach:

- Corrected priority scoring so cross-cutting reach is included before confidence weighting. A case with zero confidence can no longer gain priority solely from its number of affected controlled objects; active-response reduction remains explicit and is applied only after the confidence-bound score is calculated.
- Added deterministic regression coverage for zero-confidence cross-cutting reach and active-response reduction. Focused confidence/forecast/impact/recovery verification passed: **21 tests**.

Latest continuation — cross-machine validation and live migration rehearsal:

- Restored repository-wide Ruff formatting in the Phase 9 forecast, impact, recovery, and regression-test files; Python and web lint now pass without warnings.
- Full Python/API suite passed: **76 tests**. Generated-contract freshness, Python compilation, strict TypeScript, web lint, and the Next.js production build also passed.
- Live PostgreSQL `0009_forecast_scenarios → 0010_impact_priority → 0009_forecast_scenarios → 0010_impact_priority` migration rehearsal passed.
- Verified the `impact_priority_policy`, `confidence_override`, and `impact_assessment` append-only triggers after re-upgrade.
- A direct PostgreSQL attempt to mutate an impact-priority policy was rejected by the append-only trigger; the rollback-safe rehearsal left no test records behind.

Phase 9 completion:

- Added supported and weak-evidence cost/commercial consequence regression coverage with exact assessment/evidence lineage, currency, exposure ratio, upstream stop gates, and the explicit non-entitlement/non-liability boundary.
- Corrected commercial consequence propagation so an assessed timing effect remains visible when Phase 7 properly suppresses EAC; advanced the immutable calculation formula to `IMPACT-PRIORITY-1.0.4` without rewriting prior assessments.
- Added confidence-override governance regression coverage for optimistic case versions, exact computed-ceiling matching, reviewer identity and justification, immutable history, case-ledger provenance, and rejected mismatches.
- Replaced raw specialist/forecast UUID entry in `/impact` with case-loaded selectable progress, schedule, cost, forecast, and recovery-comparison inputs.
- Full verification passed: **80 Python/API tests**, generated-contract freshness, Ruff, Python compilation, ESLint, strict TypeScript, and the Next.js production build.
- Live PostgreSQL API smoke passed through authorized schedule, frozen snapshot, schedule assessment, independent impact dimensions, reviewer confidence override, and audit/case-ledger projections.

Phase boundary: Phase 9 records consequence, confidence, urgency, and priority independently with traceable reasons. Confidence history is calibration-ready; realized-outcome calibration remains coupled to the response/outcome lifecycle in Phase 11. Phase 9 does not select a management disposition, assemble a recommendation, or record a human decision.

### Phase 10 — Disposition, specialists, and orchestrator

Status: **complete**.

Initial implementation:

- Added shared Python/TypeScript taxonomies for specialist run state, orchestration state, and source/semantic/version/temporal/calculation/specialist-judgment contradiction classes.
- Added immutable, case/snapshot-bound orchestration runs and five bounded specialist-run records with attempts, input/output references, findings, calculations, evidence, truth labels, assumptions, contradictions, confidence, limitations, requested evidence, contract version, errors, and timestamps.
- Added migration `0011_orchestration_runs`, a latest-run case pointer, append-only PostgreSQL triggers, project/case query APIs, and optimistic/idempotent run creation.
- Added deterministic snapshot and result-boundary validation. A missing or verification-restricted impact assessment stops safely at `VERIFY`; supported consequences select a bounded disposition while missing noncritical specialists produce `DECISION_READY_WITH_LIMITATIONS` rather than a false full success.
- Added all five alternative dispositions, structured case briefs, human-review authority routing, explicit prohibited autonomous actions, and orchestration start/completion ledger and audit events.
- Regression coverage verifies safe stop behavior, five specialist boundaries, supported `INTERVENE`, limited aggregate status, idempotent replay/mismatch rejection, history, alternatives, and ledger projection.

Latest continuation — contradiction stops, retry lineage, and workbench:

- Added deterministic material contradiction detection for contradicted source truth, controlled-object disagreement, and direct-result versus forecast-lineage version conflicts.
- Persisted contradiction type, sources, status, materiality, description, and downstream invalidations; unresolved material contradictions propagate to every specialist result, create an evidence-resolution handoff, invalidate stronger disposition output, and stop at `VERIFY`.
- Added reason-coded explanations for all five disposition alternatives plus explicit evidence-request and monitoring-trigger projections in the structured case brief.
- Added immutable retry lineage. A retry creates a new run on the exact original snapshot, references the prior non-successful run, increments specialist attempt numbers, and never rewrites prior run history.
- Added `/orchestration` workbench and home navigation with case-loaded specialist inputs, forecast multi-selection, retry selection, requested questions, run history, specialist boundaries, alternatives, blockers, contradictions, and structured brief inspection.

Phase 10 completion:

- Added immutable reviewed contradiction resolutions naming the selected result, rejected/limited results, reviewer basis, and downstream invalidations. Re-orchestration recognizes matching resolutions but requires invalidated upstream results to be recalculated before lifting other stop gates.
- Added fail-closed specialist execution handling. Exceptions persist as `FAILED` specialist results with attempt, error class, zero confidence, limitations, and no invented output; a critical impact-specialist failure stops at `VERIFY`, while noncritical failures visibly limit the aggregate.
- Coupled disposition to recorded case sufficiency and governance stops without allowing orchestration to overwrite sufficiency state. `INTERVENE` routes to `APPROVAL_REQUIRED`, `ESCALATE` routes to `ESCALATION_REQUIRED`, and all recommendations retain human authority.
- Added deterministic narrative fidelity validation. Disposition drift, unsupported numbers, and autonomous authority claims fail closed against the structured brief before any optional narrative adapter can be trusted.
- Added migration `0012_contradiction_resolutions`, immutable resolution history APIs, authorization, optimistic versions, audit/case-ledger provenance, and append-only database protection.
- Live PostgreSQL Phase 10 API smoke passed through five specialist results, deterministic `INTERVENE`, limited readiness, approval routing, ledger events, and faithful narrative validation.

Verification evidence:

- **83 Python/API tests** passed.
- Live PostgreSQL migration rehearsals passed through `0012_contradiction_resolutions`, including rollback/re-upgrade of both Phase 10 revisions.
- All three Phase 10 tables and append-only triggers were verified after re-upgrade; direct orchestration-run and contradiction-resolution mutations were rejected and the rollback-safe probes left no data.
- Alembic offline SQL generation, generated-contract freshness, Ruff, Python compilation, ESLint, strict TypeScript, and the Next.js production build passed.

Phase boundary: Phase 10 publishes a versioned recommendation and structured brief, never a human decision or execution authority. Optional governed AI narrative adapters remain intentionally disabled; the deterministic/manual path and fidelity validator are complete. Human disposition, approval, response execution, and realized-outcome learning belong to Phase 11.

### Phase 11 — Human governance and response lifecycle

Status: **complete**.

Initial contract work:

- Added separate shared taxonomies for human agreement/disagreement, authority validation outcome, response execution status, realized-outcome classification, and learning category. These do not alter or reuse the Phase 10 recommendation state.

Initial governance implementation:

- Added immutable human decisions linked to a specific Phase 10 orchestration run but stored separately from its recommendation, with disposition, agreement/partial-agreement/disagreement, rationale, limitations, actor, timestamp, and optional response-authorization reference.
- Added exact authority validation against an active actor grant, authority type, case controlled-object scope, validity dates, amount ceiling, and currency. An authorized project role without a matching grant is insufficient.
- Enforced recommendation-agreement consistency, stopped/readiness gates, response-authorization boundaries, optimistic case versions, idempotency, and explicit analyst/outsider denial.
- Human disposition now advances the case to `HUMAN_DISPOSITION` and routes governance independently: intervention requires approval, escalation requires escalation authority, monitoring/verification returns to analysis authority, and no-action can be authorized to proceed.
- Added decision history APIs, a latest-decision case pointer, audit/case-ledger provenance, migration `0013_human_decisions`, and append-only PostgreSQL protection.

Response lifecycle implementation:

- Added immutable, idempotent response proposals linked to an authorized human `INTERVENE` decision. Proposed actions, assumptions, simulated effects, amount, and currency remain explicit proposal/scenario data and do not alter authorized or actual state.
- Added separate response authorization records linked to the proposal, human decision, exact active authority grant, captured authority scope, and external authorization reference. Controlled-object scope, validity window, amount ceiling, and currency fail closed.
- Added append-only execution-status observations with governed transitions and optional case-attached evidence. The API observes execution performed by the authorized project team; it does not issue an execution command.
- Added evidence-backed realized response outcomes, with non-observable outcomes kept distinct from achieved/partially achieved/not achieved conclusions.
- Response authorization and realized outcome now publish transactional `ResponseAuthorized` and `OutcomeObserved` outbox events in addition to project audit and chronological case-ledger provenance.
- Added proposal, authorization, execution-history, and outcome-history APIs plus reversible migration `0014_response_lifecycle` with append-only database protection.

Close/reopen and learning implementation:

- Integrated closure with governed response outcomes: once a case has response-outcome history, closure must reference an outcome belonging to that exact case rather than an arbitrary external identifier. Existing administrative and pre-response closure paths remain backward compatible.
- Integrated `RESPONSE_FAILED` reopening with both legacy active-response failures and the new append-only execution-observation history.
- Added immutable, idempotent learning records linked through realized outcome → response proposal → human decision → orchestration run. Each record freezes category, finding, contributing factors, recommended and human dispositions, agreement, predicted overall confidence when available, realized outcome, and exact policy/formula versions.
- Added learning history APIs, audit/case-ledger provenance, migration `0015_learning_records`, and append-only PostgreSQL protection.
- Corrected the integration fixtures for the installed Starlette/Python 3.14 combination by using explicit `TestClient.close()`; this avoids a context-manager startup stall without changing application behavior.

Verification evidence for this slice:

- Focused API coverage passed for agreement mismatch, missing authority, scoped amount/currency authority, authorized decision, lifecycle/governance routing, idempotent replay, outsider denial, history, and ledger events.
- Live PostgreSQL `0012_contradiction_resolutions → 0013_human_decisions → 0012_contradiction_resolutions → 0013_human_decisions` migration rehearsal passed; the table and append-only trigger were verified after re-upgrade.
- The focused end-to-end governance path passed from Phase 10 orchestration through human decision, proposal, authorization, execution observation, evidence-backed outcome, immutable learning/calibration, and governed closure, including idempotency and outbox assertions.
- All **37 Decision Case integration tests** passed, including the existing close/reopen regression suite.
- Live PostgreSQL `0013_human_decisions → 0015_learning_records → 0013_human_decisions → 0015_learning_records` migration rehearsal passed. All five Phase 11 response/learning tables and their append-only triggers were verified after re-upgrade.
- Full repository gate passed on 2026-09-15: generated contracts, **83 tests**, Ruff lint/format, ESLint, Python compilation, strict TypeScript, and the Next.js production build.

Phase boundary: Phase 11 completes the governed backend path from recommendation through separate human authority, observed execution, evidence-backed outcome, closure/reopening, and learning. It never issues an execution command or promotes proposals/scenarios into fact or authorized state. Decision Center workflow consolidation and reports belong to Phase 12.

### Phase 12 — Decision Center and reports

Status: **in progress**.

Initial Decision Center and reporting slice:

- Added a consolidated, project-scoped management-attention queue ordered by governed priority and urgency, with lifecycle, readiness, governance route, owner, controlled-object reach, open limitations, active responses, confidence, consequence window, deadline, and deterministic next action kept separate.
- Preserved recommendation lineage when a newer orchestration exists after a signed decision: the queue exposes both the latest system recommendation and the exact recommendation basis linked to the human decision, so agreement/disagreement cannot be misrepresented.
- Added versioned JSON report projections for the weekly decision brief, complete case dossier, material project-control exceptions, pilot KPI/cohort metrics, and governance/conformity checks.
- All report envelopes include organization/project, as-of and generated timestamps, actor, schema version, and an explicit semantic notice. Case dossiers retain snapshots, impact, orchestration, human decisions, response authorization/execution/outcome, learning, and chronological ledger records with their IDs and versions.
- Added the responsive `/decision-center` UI with project connection, lifecycle/governance filters, accessible queue table, non-color-only priority/urgency/confidence labels, visible system-versus-human disposition lineage, deterministic next actions, and downloads for all five governed JSON exports.
- Updated the home route to identify Phase 12 and link directly to the Decision Center.

Verification evidence for this slice:

- Focused end-to-end coverage passed for queue ordering fields, latest-versus-decision-basis recommendation lineage, closure next action, semantic export notice, all five report endpoints, and dossier decision/outcome/learning fidelity.
- Full repository gate passed on 2026-09-15: generated contracts, **83 tests**, Ruff lint/format, ESLint, Python compilation, strict TypeScript, and the Next.js production build including `/decision-center`.

Review queues and governed case-detail slice:

- Added seven dedicated project-scoped review queues for verification, human review, approval, escalation, governance blocks, overdue evidence, and forecasts expiring within seven days. Every entry includes the case projection, visible routing reason, next deadline, and required role.
- Added project-timezone metadata to the review projection and render queue deadlines with an explicit IANA timezone label rather than silently using the browser timezone.
- Extended full Decision Case detail with a separate human-governance workbench backed by the governed case dossier. Operators can record a signed human decision, response proposal/scenario, exact authorization, external execution observation, evidence-backed outcome, and immutable learning/calibration record without crossing system-recommendation boundaries.
- The case-detail workflow shows separate counts for decisions, proposals, authorizations, observations, outcomes, and learning records and retains the existing chronological case ledger beside them.
- Full repository gate passed again on 2026-09-15: generated contracts, **83 tests** including all **37 Decision Case integration tests**, Ruff lint/format, ESLint, Python compilation, strict TypeScript, and the Next.js production build.

Export fidelity and usability-readiness slice:

- Added deterministic SHA-256 content hashes over canonical JSON payloads and a fidelity manifest to every governed report. The manifest explicitly preserves evidence, analysis, forecast/scenario, recommendation, human decision, authorization, execution observation, and realized-outcome boundaries.
- Added a spreadsheet-friendly Decision Queue CSV export with separate latest recommendation, signed-decision recommendation basis, human disposition, confidence, priority, urgency, governance, deadline, and next-action columns. Response headers carry the export schema, semantic notice, and project timezone.
- Added regression coverage that independently reconstructs report hashes and verifies CSV semantic columns and metadata headers.
- Preserved Decision Center project context and lifecycle/governance filters in session-scoped browser storage; authenticated actor context is not placed in persistent local storage.
- Added global visible keyboard focus styling and touch-target behavior to complement semantic labels, table headers/caption, live status messages, responsive layouts, and non-color-only state text.
- Added `docs/15-operator-usability-protocol.md` with participant requirements, six time-boxed core tasks, accessibility/export checks, semantic hard failures, acceptance evidence, and a clear separation between automated workflow evidence and representative human observation.
- Full repository gate passed again on 2026-09-15: generated contracts, **83 tests**, Ruff lint/format, ESLint, Python compilation, strict TypeScript, and the Next.js production build.

Dashboard shell redesign (2026-09-16):

- Replaced the link-heavy landing page with a responsive white-and-burgundy command-center presentation containing operational metrics, an accessible plan-versus-actual SVG trend, priority distribution, recent signals, and control-health indicators.
- Added a persistent grouped left navigation rail, active-route treatment, compact project/top status bars, and a mobile drawer across every web route. The existing workbenches and governance semantics remain intact.
- Kept priority, signal category, project health, and authority messaging visibly distinct; dashboard indicators include an explicit notice that they are not human decisions or execution authority.
- ESLint and standalone strict TypeScript passed. The Next.js production compiler completed, then the build stopped in Next.js 16.3.4 while parsing TypeScript's valid `--showConfig` JSON; this toolchain failure remains unresolved and is not recorded as a passing production build. Browser review also remains pending because the sandbox denied binding the local development server to port 3000.

Single-input planning workspace and progress workbook (2026-09-16):

- Reworked the simple `/bootstrap` route into a project-first workspace. An operator loads and selects a governed project, after which code, timezone, currency, delivery model, and reporting cadence populate from the project record rather than being re-entered.
- The earlier browser IndexedDB workflow-template cache has been removed. The application now owns the standard six-column workbook projection on the API server, consistently across projects and clients.
- BOQ scope is matched to the workflow where supported. Unmatched commercial lines remain visibly listed in `BOQ Review` for consolidated work-package planning; they are not copied one-for-one into a second, unlinked pseudo-schedule.
- Generated XLSX files now contain `Progress Report`, organized by BOQ subdivision with task and proposed planning fields plus constrained operator inputs for work-complete percentage, reporting date, remarks, evidence reference, and responsible party. The sheet states that entered progress remains reported information until supported and verified.
- A review of `ms_project_schedule_from_boq (1).xlsx` found that an incompatible 38-activity workflow had been followed by 418 paraphrased BOQ-line tasks, most with one-to-three-day generic durations and no dates or logic. That generation path was removed. Generated outputs can no longer be recursively reused as templates, and weak BOQ/template coverage now fails with an actionable error instead of presenting an incomplete programme as valid.
- Focused workbook tests, Ruff lint/format, ESLint, and strict TypeScript pass after the correction. Producing a complete project timeframe still requires compatible package/activity coverage plus reviewed productivity, logic, calendar, and project date constraints; the converter does not invent those inputs.

OpenAI six-column schedule generation correction (2026-09-16):

- Confirmed that the supplied `Template.xlsx` is an output-format template: its authoritative content is the empty `Tasks` sheet with `ID`, `Name`, `Duration`, `Start`, `Finish`, and `Dependency`. Stale generated `BOQ Review` and `Progress Report` sheets are ignored and removed from output.
- Added a local-development OpenAI Responses API schedule generator. It sends normalized measured BOQ scope plus project start and optional required completion date, requests strict JSON-schema output, and directs the model to produce consolidated executable subdivisions rather than paraphrased BOQ lines.
- Added deterministic validation for consecutive IDs, unique task names, ISO dates, start/finish bounds, target completion, and predecessor-only dependencies before any XLSX is returned.
- API credentials are accepted only from server configuration as `VAI_OPENAI_API_KEY`; the model is configurable with `VAI_OPENAI_SCHEDULE_MODEL` and defaults to `gpt-5`. A future credential-management UI must be admin-only and is not part of the customer workspace.
- The final workbook contains one `Tasks` sheet and exactly the six requested columns. Five focused spreadsheet tests, Ruff, ESLint, and strict TypeScript pass. A live OpenAI call was not made because no API key was supplied in this checkout.

Local operator distribution:

- Added reproducible container images for the FastAPI service and Next.js application plus `compose.installer.yml` for PostgreSQL, automatic Alembic migrations, API health gating, web startup, and persistent database/evidence volumes.
- Added one-command Windows PowerShell and Linux shell launchers with prerequisite checks, health waiting, browser launch, data-preserving stop, and explicit destructive reset modes. Linux consistently prefers Podman when both Podman and Docker engines are available to avoid cross-engine port conflicts.
- Added `make package-installers`, which creates shareable Windows ZIP and Linux tar.gz evaluation bundles without repository, virtual-environment, dependency-cache, local-data, or secret files.
- Added `docs/16-local-installer.md` documenting requirements, ports, persistence, lifecycle commands, and the non-production security boundary.
- Fresh installer verification passed on 2026-09-15: both archives passed integrity/content checks; Compose configuration rendered successfully; Python 3.12 and Node 22 images built; a clean PostgreSQL volume migrated through `0015_learning_records`; API health returned `200`; the production Next.js container returned `200`; and a data-preserving Linux launcher stop/start path was exercised. The validated application was left running locally on ports 3000/8000 for operator use.

Remaining Phase 12 exit evidence: conduct and document the representative human sessions defined in `docs/15-operator-usability-protocol.md`. The technical workflow, report/export fidelity controls, saved filter/context behavior, and automated accessibility foundations are implemented; automated tests are not being presented as a substitute for operator observation.

## Remaining delivery count

The canonical roadmap contains 15 phases (`0` through `14`). Phases `0` through `11` are recorded complete, leaving **3 numbered phases**: Phases `12` through `14`. Amendment A adds one required corrective bootstrap track before Phase 13. Earlier verification entries are historical evidence, not fresh certification of a later checkout.

## Continuity handoff

- Repository-level working agreements and invariants are recorded in `AGENTS.md`; a fresh Codex session should load that file before acting.
- Resume B0.6–B0.8 acceptance hardening in `docs/17-boq-to-schedule-bootstrap.md`. Preserve the immutable B0.1–B0.5 source, normalization, structure, activity, duration, assumption, and schedule-logic boundaries.
- After B0.1–B0.8, conduct and document amended representative human sessions covering BOQ upload through schedule authorization and the existing Decision Center workflow. Do not mark Phase 12 complete from automated checks alone.
- The current working-tree checkpoint includes migrations through `0023_bootstrap_revision_delta`; the live database was rehearsed to that revision. Do not recreate completed Phase 10 orchestration, Phase 11 governance/response lifecycle, or B0.1–B0.5 bootstrap records.
- On a fresh machine or account, inspect `git status` and recent history, install locked dependencies if needed, and treat verification recorded below as historical until rerun locally.

## Next implementation order

Finish the outstanding B0.6 validation and regression matrix, harden B0.7 browser review/edit usability, and complete B0.8 conformity and schedule-effect checks. Then extend and run the Phase 12 operator protocol across the BOQ-first workflow. Production OIDC, object storage, malware scanning, and production OCR selections remain explicit external-integration limitations.
# Direct BOQ-to-MS-Project workbook handoff (2026-09-16)

The simple `/bootstrap` screen now accepts a text-native BOQ PDF and the user's six-column XLSX example, returning an MS Project import workbook. The prior governed workbench is preserved at `/bootstrap/advanced`. The stateless converter copies example timing/logic as draft planning inputs, renumbers/remaps predecessor IDs, places BOQ scope not confidently matched into unscheduled Tasks rows, and records source matching in `BOQ Review`. It does not authorize or publish a schedule. The local sample `BOQ 2.pdf` plus `ms_project_schedule_import.xlsx` produced 867 task rows (561 reference tasks plus 306 unscheduled BOQ rows) from 431 parsed BOQ items. PDF parsing is text-native only; verify BOQ completeness and planner timing before relying on the schedule. Current-check results must be recorded separately; this is not Phase 12 human operator acceptance.

## Windows local-development and BOQ scheduling verification (2026-10-12)

- Added root `npm run dev` orchestration for the bundled Windows PostgreSQL and Poppler runtimes, migrations, API, and Next.js development server so local testing no longer depends on separately configured processes.
- Exercised the real 75-page `BOQ 2.pdf`: 431 measurable rows were parsed and the live OpenAI path returned a 57-task workbook with exactly the six contracted columns, sequential IDs, complete names/dates, valid predecessor-only dependencies, and a final task on the requested 2027-12-12 completion date.
- Confirmed that the similarly named `Vai - BOQ 2.pdf` is a project-control presentation rather than a BOQ. Non-BOQ text now returns an actionable selection/scanning error; the focused workbook/parser suite passes (7 tests).
- Rendered all 15 application routes at desktop and narrow viewport sizes and confirmed HTTP 200 responses. Corrected narrow-screen context-input/button overflow. The governed workbenches still expose technical actor, organization, project, and case identifiers; replacing those with the local project picker remains outstanding usability work.
- Current verification: generated-contract check, Ruff check/format, ESLint, strict TypeScript, and the Next.js production build (17 static pages) pass. The full API suite has one pre-existing governance/orchestration mismatch: `test_orchestration_assembles_supported_disposition_and_specialist_boundaries` receives `STOPPED` where the test expects `LIMITED`; this is not recorded as a passing full gate.

## Operator context simplification (2026-10-12)

- Removed manual Actor, Organization, Project, and Decision Case identifier entry from every operator workbench. The local account and organization remain internal request context; operators now choose projects by code/name and decision cases by case number/title.
- Added one reusable context selector shared by Decision Center, Evidence, Signals, Cases, Progress, Schedule, Cost, Forecast, Impact, Orchestration, and the advanced BOQ workflow. The selector uses the workspace created in Projects and retains the active project locally.
- Removed UUID terminology from operator-facing form labels; technical record identifiers remain internal API values and are submitted behind readable selections where those projections exist.
- Current web verification passes: ESLint, strict TypeScript, a 17-page production build, rendered desktop checks for project/case selectors, and HTTP 200 checks across all affected routes.

## Persistent BOQ and schedule handoff (2026-10-13)

- The simple BOQ workspace now preserves the uploaded PDF and generated XLSX as project-scoped evidence artifacts. PostgreSQL retains their immutable metadata and the configured evidence store retains their bytes; production storage continues to fail closed without an external adapter.
- Added a visible completion panel with an explicit Excel download button, proposal/review notice, and three concrete next steps. Automatic one-shot browser download is no longer the only way to obtain the workbook.
- Added a project-file library to `/bootstrap`, reachable from the command center through **BOQ files & schedules**. Operators can download prior BOQs and generated workbooks again after refresh or in a later session.
- Verified the existing `BOQ 2.pdf` and generated six-column XLSX through storage/download round trips; both downloaded SHA-256 hashes matched their source files. The project library returned both entries. ESLint, strict TypeScript, and the 17-page production build pass.
- Corrected the live generator failure path after reproducing a Responses API call exceeding the former 180-second client timeout. The server now permits five minutes and converts timeout/network failures into readable API errors; the browser clears stale progress, confirms that the BOQ remains saved, and refreshes Project files even when generation fails. A focused timeout regression test, Ruff, ESLint, strict TypeScript, and an origin-aware API error check pass.
- Corrected simple-workspace BOQ revision registration: before upload, the browser now fetches the latest registered BOQ source and records the new evidence artifact as its explicit successor, then registers the matching source-version predecessor. A live repeated-PDF upload produced artifact HTTP 201 and source-version HTTP 201 with an exact version 1-to-2 chain; ESLint, strict TypeScript, and the 17-page production build pass.
- Reduced simple schedule-generation latency by setting GPT-5 reasoning effort to `minimal`, low text verbosity, and a bounded output ceiling for the strict schedule schema. A live 431-row BOQ request completed in 17.3 seconds with HTTP 200 and produced a validated 43-task, six-column draft ending on the requested completion date; the prior configuration had taken roughly three minutes or timed out. The later governed traceability schema uses a larger ceiling because it returns hundreds of BOQ allocations. Failure copy now explicitly states that no Excel workbook was created. The focused eight-test suite, Ruff, ESLint, strict TypeScript, and the 17-page production build pass.

## Governed BOQ schedule-agent correction slice (2026-10-20)

- Applied the supplied scheduling-agent correction requirements to the simple BOQ pipeline as product rules, while preserving the proposal-versus-authorization boundary.
- BOQ ingestion now retains page-qualified references and available Part/Chapter/Section hierarchy. Generated activities carry exact BOQ references, scope type, duration basis/note, and typed FS/SS/FF/SF relationships with lag and physical basis.
- Added independent deterministic QA for missing/duplicate/unknown BOQ allocation, invalid or violated relationship logic, selected-workweek conflicts, deadline conflicts, provisional durations, below-grade waterproofing before backfill, concealed-services inspection before ceiling closure, and distinct MWSS material-system coverage for heating, solar hot water, UPS, road layers, curbs, lift, fire pump, and PV.
- The XLSX retains the six-column `Tasks` import sheet and adds `BOQ Coverage` and `QA Review`. Critical findings return a downloadable `BLOCKED` proposal rather than suppressing the workbook; malformed structured output remains a hard failure.
- A real 431-item MWSS run returned HTTP 200 in 75.7 seconds with 35 activities, 431 coverage rows, and 87 findings (`30 CRITICAL`, `22 HIGH`, `35 WARNING`) and was correctly marked `BLOCKED`. Focused coverage increased to 13 passing tests; Ruff, ESLint, and strict TypeScript pass.

## Schedule-linked Excel progress reporting (2026-10-20)

- Every OpenAI-generated schedule workbook now opens on a `Progress Report` sheet mapped one-to-one to its schedule task IDs and BOQ references. Operators edit only the highlighted completion, reporting-date, remarks, evidence-reference, and responsible-party cells; the six-column `Tasks` import contract is unchanged.
- Added a plain-language `/progress` upload workflow that compares reported completion with time-phased planned completion at a selected reporting cut-off and identifies early, on-time, late, and missing reports. Reported percentages remain explicitly separate from evidence-backed verification.
- Added deterministic task-level schedule variance and a conservative potential-deadline-exposure scenario. The UI states that critical path, float, calendar, and evidence must be checked in Microsoft Project before treating this as a deadline forecast, and routes late work to the existing governed schedule-change proposal assistant.
- Current verification: 19 focused workbook, analysis, and revision tests pass; Ruff, ESLint, strict TypeScript, and the 17-page Next.js production build pass. All 15 operator routes returned HTTP 200 from the local Windows development stack, and the live progress-upload endpoint accepted a generated workbook and returned the expected unmapped-report state. Representative human operator acceptance remains outstanding.
