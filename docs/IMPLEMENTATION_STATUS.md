# Implementation Status

Last updated: 2026-09-21

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
