# Implementation Status

Last updated: 2026-09-05

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

## Next phase

Phase 6 — Schedule and dependency intelligence.

Next implementation order:

1. Parse and validate minimal activity networks, calendars, constraints, dependencies, milestones, and supplied/calculable float.
2. Resolve the schedule version effective at each case data date and calculate activity/milestone timing variance.
3. Trace credible downstream paths and distinguish isolated delay from consequential delay.
4. Surface schedule-quality and missing-dependency limitations without inventing unsupported logic.
5. Add schedule intelligence to Decision Cases and cover schedule-only and approved-change scenarios.
