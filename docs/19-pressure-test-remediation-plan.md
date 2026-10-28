# Pressure-Test Remediation Plan

Status: **active**  
Started: **2026-10-23**  
Current product classification: **Internal Alpha**

## Objective

Close the gaps found in the 2026-10-23 repository pressure test without weakening the existing
Decision Case, evidence, authority, immutability, or semantic-separation contracts. The target is a
pilot-safe system that can answer, from governed stored project information, where the project
stands, why, what evidence supports the answer, and what requires human attention.

This plan does not mark Phase 12 complete. Representative operator sessions remain mandatory, and
Phase 13 cannot begin until the existing roadmap gates are satisfied.

## Non-negotiable acceptance boundary

The final product-level answer must distinguish:

- authorized baseline and current schedule;
- planned, reported, executed, verified, and accepted progress;
- approved budget, commitments, actuals, accruals, forecast-to-complete, and EAC;
- evidence, derived analysis, forecast/scenario, recommendation, human decision, authorization,
  execution observation, and realized outcome;
- unknown, insufficient, contradicted, and zero values; and
- system advice from human authority.

No dashboard, report, assistant, or presentation may strengthen or silently replace the stored
source semantics.

## Delivery order

### R0 — Verification and test isolation

- [x] Record the pressure-test findings and ordered remediation plan.
- [x] Prevent local OpenAI credentials from changing deterministic test results.
- [x] Add a dedicated opt-in live-adapter test profile.
- [x] Apply and verify the Next.js security upgrade reported by the production build.
- [x] Rehearse PostgreSQL migration upgrade, downgrade, and re-upgrade through the current head.
- [x] Add browser E2E coverage for the BOQ-first and Decision Center critical paths.

R0 verification: default tests block real HTTP transports and clear optional AI credentials;
`pytest -m live_adapter --live-adapters` is the explicit, potentially paid live profile. Next.js and
its ESLint configuration are pinned to 16.4.2; production npm audit reports zero findings. Five
development-only transitive findings remain in the ESLint glob dependency chain and remain an R10
release blocker. Browser checks use a disposable database/API with no live credentials and cover
BOQ persistence/download/revision after scheduler failure, queue semantics, filtering, and CSV.

Exit: the default repository gate is deterministic, offline-safe, and repeatable on a configured
developer machine.

### R1 — Authoritative project completion and control snapshot

- [x] Define versioned work-package progress weights and permitted weighting bases.
- [x] Fail closed for empty, duplicate, nonpositive, over/under-total, or non-project weights.
- [x] Calculate planned and actual project completion from compatible governed measurements.
- [x] Preserve package contributions, exclusions, unknowns, confidence, and formula lineage.
- [x] Create an immutable project-control snapshot binding schedule, progress, cost, forecast,
  evidence, policies, and data date.
- [x] Add tenant, stale-version, idempotency, append-only, and semantic regression tests.

Exit: overall completion is reproducible from a frozen snapshot and is never task-count based.

### R2 — Snapshot-correct reports

- [x] Persist report snapshots with report date, data date, project-control snapshot, source IDs,
  policy/formula versions, generator, approval status, canonical hash, and fidelity manifest.
- [x] Prevent an `as_of` report from including later records or current mutable state.
- [x] Generate weekly, monthly/executive, exception, on-demand status, case dossier, pilot KPI,
  and governance/conformity projections from the same snapshot service.
- [x] Add explicit draft/reviewed/approved report lifecycle and authority checks for external use.
- [x] Add hash, temporal-fidelity, cross-tenant, and append-only tests.

Exit: a previously issued report never changes and can be reproduced from its exact inputs.

### R3 — Real command-center dashboard

- [x] Remove hardcoded operational metrics and sample signal counts from the command center.
- [x] Require an explicit active project and project-control snapshot.
- [x] Show completion, schedule position, cost position, EAC, forecast finish, evidence quality,
  limitations, and attention cases from the same backend projection used by reports.
- [x] Preserve visible unknown/insufficient states; never substitute zero.
- [x] Verify dashboard/report equality for all shared metrics.

Exit: every displayed operational value has a traceable API field and snapshot reference.

### R4 — BOQ commercial integrity and allocation

- [x] Reconcile quantity × unit rate to total with currency-aware configurable tolerance.
- [x] Detect invalid signs, inconsistent summaries, duplicate stable lines, and incompatible units.
- [x] Add versioned BOQ-to-WBS/activity allocation quantities, percentages, values, and basis.
- [x] Prevent quantity, percentage, or value over-allocation.
- [x] Preserve one-to-many and many-to-one schedule traceability without double counting.
- [x] Surface all unresolved arithmetic and allocation findings before schedule approval.

Exit: BOQ totals and allocations reconcile or remain visibly blocked.

### R5 — Project context domains

- [x] Add an immutable/versioned Project Charter with objectives, constraints, milestones,
  success criteria, delivery strategy, and authority reference.
- [x] Add stakeholder and report-recipient registries with project role and communication rules.
- [x] Add governed Daily Update records with evidence, weather, labor/equipment, quantities,
  blockers, safety/quality observations, and reporting cut-off.
- [x] Add evidence-linked Risk, Issue, and Change Request lifecycles.
- [x] Ensure approved changes create new authorized contexts rather than rewriting history.

Exit: the core project context required for reporting and decisions is persisted and auditable.

### R6 — Governed progress workbook ingestion

- [x] Treat uploaded workbooks as project-scoped evidence artifacts.
- [x] Bind every progress row to the exact authorized schedule activity and version.
- [x] Store reported measurements separately from verification and acceptance.
- [x] Use the authorized working calendar and schedule network for date/exposure calculations.
- [x] Remove the calendar-day/max-task approximation from authoritative conclusions.
- [x] Retain a clearly labeled preview mode only where useful.

R6 scope: imports freeze the exact authorized network and calendar, calculate elapsed working
days, and use only exact authorized progress-plan points for planned completion. Missing plan
points remain unknown. Workbook percentages create `REPORTED` / `REPORTED_CLAIM` evidence and
measurements, with no verification or acceptance. Downstream exposure remains explicitly unknown
until the existing governed schedule-assessment path receives adequate verified evidence; a
workbook's max-task variance never becomes a forecast. The local-only preview remains explicitly
unpersisted and approximate.

Exit: workbook progress survives refresh, has evidence lineage, and cannot bypass truth gates.

### R7 — Explainable project and package RAG

- [x] Define versioned Green/Yellow/Red policies for schedule, progress, cost, evidence, and
  governance dimensions.
- [x] Calculate package status first, then project status using explicit materiality and weighting.
- [x] Include rule, threshold, input IDs, data date, confidence, and limitation reasons.
- [x] Prevent color-only communication and prevent unknown from becoming Green.
- [x] Link every Red/Yellow status to the relevant signal or Decision Case route.

R7 uses explicit project-admin-owned policy parameters, frozen inside each control snapshot.
No numerical materiality or confidence thresholds are silently supplied. Unknown/stale/restricted
sources cannot produce Green, and unresolved snapshot contradictions withhold a supported progress
conclusion. Package results precede weighted project aggregation; small Red packages remain visible
and produce project Yellow even below the material Red-weight threshold. Schedule conclusions use
exact selected assessments, and governance uses historical audit state rather than current mutable
case state. Legacy snapshots without those sources remain Unknown.

Exit: every RAG result is deterministic, explainable, reproducible, and evidence-linked.

### R8 — Grounded project assistant and advisory

- [x] Add read-only project-status queries over one selected immutable control snapshot.
- [x] Answer completion, schedule, cost, forecast, RAG, risks, evidence, and next-review questions.
- [x] Require citations to stored record IDs and expose limitations/unknowns.
- [x] Keep deterministic calculations authoritative; AI may summarize but not calculate or approve.
- [x] Add prompt-injection, evidence-allowlist, unsupported-number, and authority-claim tests.

R8 is a deterministic status assistant with no model/tool execution path. It answers selected
topics and recognizable status questions using a frozen fact catalog and record-ID allowlist.
Reported context remains reported, limited forecasts retain their limits, insufficient financial
conclusions remain Unknown, and source dates are explicit. It neither queries newer project state
nor mutates records. The compact command-center panel exposes citations and human-review
considerations without adding another navigation surface or a paid model call.

Exit: the assistant cannot answer beyond the selected snapshot or perform management actions.

### R9 — Presentation and communication consistency

- [x] Generate stakeholder presentations only from an immutable report snapshot.
- [x] Use the same metrics, dates, facts, limitations, and semantic notices as the report/dashboard.
- [x] Store the generated artifact hash, source report ID, generator version, approval, and recipient
  selection.
- [x] Add automated cross-artifact equality checks.

R9 uses one deterministic shared metric projection for snapshot responses, dashboard completion,
report payloads, assistant completion, and report-derived HTML slide decks. Costs remain scoped
to individual supported assessments. Decks embed the complete frozen report and selected recipient
versions, retain visible Unknowns and semantic notices, and have separate human review/approval
history. Exact hashes, source approval linkage, recipient eligibility, replay/stale-version gates,
and active actor-owned authority are verified. Four browser journeys pass, including report and
presentation approval/download and ten-slide rendering/overlap checks. Migration 0030 was rehearsed
through upgrade/downgrade/re-upgrade with real PostgreSQL foreign keys, append-only denial, and
populated-history rollback protection. Human operator acceptance remains part of R10.

Exit: dashboard, report, and presentation cannot contradict one another for the same snapshot.

### R10 — Production and pilot hardening

Use [the verification runner](25-r10-verification-runner.md) to collect current local engineering
evidence and explicit NOT RUN requirements. A successful selected-check exit does not close R10,
representative operator acceptance or deployed-provider/pilot gates.

Backend adapter selection/integration is implemented for Auth0-compatible OIDC/JWKS, Amazon S3,
and private ClamAV, with no additional application screens. Thirty focused identity, storage,
scanner-protocol, and archive-resource tests pass. Production browser sessions, request/rate/header
limits, and redacted credential checks are also implemented; the default suite passes 305 tests.
The HTTPS production-build rehearsal verifies PKCE/JWKS/token/cookie/sign-out behavior against a
synthetic issuer, full 12 MiB proxy fidelity, and mobile layout. The current
npm audit reports zero runtime/development findings. These are technical prerequisite corrections,
not Phase 13 entry or pilot authorization. Live provider/IAM/scanner and deployed TLS/forwarding
checks, and the remaining hardening and human gates below, are still required. See
`docs/20-production-hardening.md` for configuration, explicit bounds, evidence, and deployment gaps.

The route-wide matrix now passes 939 tenant/membership denials across 157 scoped operations plus
93 service/unknown-principal denials across 31 human-reserved commands. Exact context approval,
whole-case authority scope, and verified-evidence gates are covered. Migration 0031 protects audit
history, including after real logical backup/restoration of all 79 public tables and both stored
synthetic artifacts. A focused PostgreSQL approval race yields one approval and one stale conflict.
These do not replace broader load/accessibility checks or staging disaster recovery. Python and
npm dependency audits now report zero known vulnerabilities after updating affected Python pins.
See `docs/21-recovery-verification.md` for the recovery evidence and remaining acceptance procedure.

Local accessibility/performance prerequisites now pass: 42 browser journeys include all fifteen
pages at desktop/320px widths and populated governance/progress/health states. Focus, keyboard
scrolling, target size, semantic table/group, contrast, reflow and loading-race defects were fixed.
A 50-case queue now uses seven SQL statements instead of 301; an opt-in real-PostgreSQL profile
passes 96 concurrent reads with identical payloads and no database changes. These are local
regression results, not complete WCAG acceptance or deployed capacity evidence. Manual accessibility,
representative operator sessions, staging load/soak and disaster recovery remain open. See
`docs/22-nonfunctional-verification.md` for reproducible scope and limitations.

- [x] Select and implement production OIDC, object storage, and malware scanning adapters.
- [ ] Validate those adapters against actual providers and deployed TLS/forwarding controls.
- [x] Add upload archive/resource limits, rate limits, security headers, and secret-handling checks.
- [x] Run the route-wide cross-tenant and authority-denial matrix.
- [x] Run local concurrency, performance, automated accessibility and logical backup/restore checks.
- [ ] Complete manual accessibility, staging load/soak and deployed disaster recovery.
- [ ] Complete BS-001–BS-010 and the representative Phase 12 operator protocol.
- [ ] Resolve all critical/high findings before pilot authorization.

The BS-001–BS-010 technical evidence audit is now recorded in
`docs/23-bootstrap-acceptance-evidence.md`: 37 evidence/bootstrap API cases pass, including added
constraint, calendar and validation regressions. CPM version 1.1.0 corrects constraint-limited late
dates, pre-start milestone float and free-float bounds without rewriting historical results. A
new advanced browser journey covers XLSX upload, blocked-draft correction/recalculation, exact
authority denial/approval, export and revision isolation. The release checkbox remains open for
representative human sessions. Governed text-native PDF intake now preserves page/word geometry,
original text, proposed cells and review warnings for supported tables. Twenty-three PDF cases
and both XLSX/PDF advanced browser journeys pass. Scanned/mixed/unmapped layouts remain blocked;
OCR and arbitrary/multiline table reconstruction are unavailable. Document 23 records these limits
and the richer material-edit boundary instead of treating simple PDF/AI exports as publication.

The advanced source/normalization inspector and typed material-correction controls are implemented.
Duration/productivity, reviewed calendars, dependency type/lag, milestone target and constraint
date/type edits create attributed immutable successors, never calculations or authority. Earlier
pending reviews/approvals are rejected after the planning version changes. A new real-PostgreSQL
source-to-publication/correction/race/recovery path exposed and fixed parent insertion ordering
that SQLite had not enforced. Document 23 records the supported surfaces and current evidence;
human usability, deployment and pilot-entry gates remain open.

Exit: Phase 12 evidence passes, Phase 13 hardening passes, and pilot entry is explicitly approved.

## End-to-end acceptance scenario

The connected audit has closed prerequisites for steps 7–8: typed sourced control mappings and
explicit planned quantities at review; distinct baseline/current contexts with retained approved
baseline lineage; SQL context-history protection; and exact authorized planned measurement matching.
Migration 0032 passed real upgrade/rollback/re-upgrade and logical recovery. The complete connected
scenario below now passes through public API commands in one synthetic project on SQLite and
migrated PostgreSQL (2026-10-27). It verifies exact baseline/schedule, separate cost bases, verified
delay assessment, frozen health, report/presentation approval and cross-artifact equality after
later reported updates. Its records and artifact bytes are included in PostgreSQL logical recovery.
Step references, commands and scope limits are recorded in
[connected acceptance evidence](24-connected-acceptance-evidence.md). This closes the technical API
demonstration, not representative human or live deployment acceptance.

The completed system must pass this sequence without semantic shortcuts:

1. Create a project.
2. Define and authorize its charter.
3. Create or import its WBS.
4. Import and validate its BOQ.
5. Import or generate a proposed schedule.
6. Link BOQ, WBS, and schedule using reconciled allocations.
7. Review and authorize the current schedule and baseline.
8. Record a daily update and governed progress measurements.
9. Record commitments, actuals, accruals, and earned/physical value.
10. Record and verify a delay or blocker.
11. Freeze a project-control snapshot and calculate current health.
12. Produce explainable package and project RAG status.
13. Query the assistant using only the frozen snapshot.
14. Produce evidence-backed management considerations.
15. Generate and approve a project report snapshot.
16. Generate a stakeholder presentation from that report snapshot.
17. Prove dashboard, report, presentation, and assistant factual consistency.

## Source-of-truth target

| Concern | Target authoritative record |
| --- | --- |
| Project identity | Project |
| Charter | Authorized Project Charter version |
| WBS | Reviewed WBS version |
| BOQ | BOQ source version and normalized lines |
| BOQ allocation | Allocation version |
| Schedule | Authorized schedule context/release |
| Baseline | Authorized baseline context |
| Actual progress | Evidence-backed progress measurements |
| Budget | Authorized budget context |
| Actual and committed cost | Evidence-backed cost records |
| Forecast | Immutable forecast projection |
| RAG and project health | Immutable project-control snapshot projection |
| Stakeholders | Project stakeholder registry |
| Reports | Immutable report snapshot |
| Presentations | Artifact derived from one report snapshot |

## Today’s execution sequence

Work in dependency and decision-risk order, stopping only where a migration rehearsal, operator,
or external adapter is genuinely required:

1. ~~Complete R0 deterministic test isolation and rerun the full gate.~~
2. ~~Specify the R1 weighting and project-control snapshot contract against existing domain rules.~~
3. ~~Implement the smallest end-to-end R1 slice with regression tests.~~
4. ~~Implement R2 snapshot persistence and temporal fidelity.~~
5. ~~Replace the hardcoded dashboard through the R1/R2 projection.~~
6. ~~Complete R4 commercial integrity/allocation and R5 governed project context.~~
7. ~~Complete R6 governed progress workbook ingestion, R7 explainable RAG, and R8 grounded assistant.~~
8. ~~Complete R9 report-derived stakeholder presentations and communication consistency.~~
9. ~~Demonstrate the complete 17-step acceptance scenario against one connected governed project
   through public API commands on SQLite and migrated PostgreSQL.~~ See document 24 for evidence.
10. Resume R10 representative operator/manual accessibility acceptance and live deployment
    verification using documents 23–24. Production deployment checks, human acceptance and pilot
    approval remain explicit dependencies and cannot be supplied by automated evidence.

## Completion tracking

Update this checklist and `docs/IMPLEMENTATION_STATUS.md` after every meaningful verified slice.
Do not mark a workstream complete from documentation, static code inspection, or AI-generated
output alone.
