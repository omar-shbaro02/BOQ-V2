# 07 — API and Event Contracts

## 1. API principles

Use versioned REST/JSON for commands and queries in MVP, publish OpenAPI, and maintain JSON Schemas for domain payloads. IDs are opaque UUIDs. Dates/times use ISO 8601. Quantities carry unit; money carries currency; percentages carry measurement basis. Mutation endpoints require idempotency and optimistic concurrency.

## 2. Primary resources

- `/projects`, `/projects/{id}/authority-map`, `/projects/{id}/policies`
- `/controlled-objects`, `/relations`
- `/authorized-context/versions`, `/schedule-versions`, `/budget-versions`, `/boq-versions`
- `/evidence`, `/evidence-batches`, `/verification-events`, `/contradictions`
- `/signals`, `/case-correlations`
- `/decision-cases`, `/decision-cases/{id}/evaluations`, `/decision-cases/{id}/ledger`
- `/evidence-requests`, `/specialist-runs`, `/forecasts`, `/scenarios`
- `/recommendations`, `/human-decisions`, `/responses`, `/outcomes`
- `/reports`, `/metrics`, `/benchmark-runs`, `/conformity-reports`
- `/projects/{id}/bootstrap/boq-sources` and `/projects/{id}/bootstrap/boq-sources/{source-id}`

BOQ bootstrap source creation references an existing governed evidence artifact and requires an idempotency key. The returned immutable version includes the artifact digest, predecessor, parser/version, extraction status/confidence, workbook or page structure, warnings, and raw row locations. Creating a revision requires both the latest prior source version and an artifact that explicitly supersedes the prior artifact.

`POST /projects/{id}/bootstrap/boq-sources/{source-id}/normalizations` creates one immutable normalization for an extracted source. It accepts optional per-sheet header-row and one-based canonical-column overrides, requires an idempotency key, and returns counts for total, schedule-relevant, and review-required rows. `GET /projects/{id}/bootstrap/boq-sources/{source-id}/normalization` returns every canonical line with raw-source lineage, normalized and unmapped values, classification basis, confidence, review state, and warnings.

Planning-structure endpoints create and list immutable proposed WBS/work-package versions for a normalized BOQ. Revision commands support package split/merge, BOQ-line remap, planner acceptance, and rejection. Every revision names the exact predecessor, reason, actor, action, changed IDs, and idempotent request hash; stale predecessors fail closed. `REVIEWED` is planner review only and never means current-authorized or baseline-authorized schedule state.

Schedule-draft generation accepts the latest planner-reviewed structure plus explicit duration and productivity records. It returns immutable archetyped activities, BOQ-line references, quantity/unit aggregation, duration status/basis, unrounded calculations, visible productivity provenance, warnings, and first-class assumptions. Missing or incompatible duration support yields `VERIFICATION_REQUIRED`; the API never supplies an implicit productivity, crew, shift, efficiency, overtime, calendar, or authorized state.

`POST /projects/{id}/bootstrap/schedule-drafts/{generation-id}/logic` creates the immutable B0.5 schedule-logic proposal for one exact draft generation; `GET` returns it. Inputs may include explicit dependencies, validated sequence templates, proposed milestones and constraints, and a reviewed working calendar. Relationships retain type, lag, basis, confidence, and review state. Missing calendars become visible low-confidence review assumptions. Milestones and constraints are always returned as proposed and unauthorized; neither contract evidence nor BOQ wording creates schedule authority.

`POST /projects/{id}/bootstrap/schedule-drafts/{generation-id}/calculations` calculates immutable CPM dates, float, milestone variance, validation findings, input hash, and readiness from the exact draft and logic proposal. A blocker prevents `POST /projects/{id}/bootstrap/schedule-calculations/{calculation-id}/reviews`. Planner review stores field-level original/revised values, actor, time, and reason in an immutable release; only a separate `POST /projects/{id}/bootstrap/schedule-releases/{release-id}/approve` with an exact active human schedule-authority grant can create a current-authorized schedule context. A reviewed release cannot be approved twice. `GET /projects/{id}/bootstrap/schedule-releases/{release-id}/export/{json|csv|xlsx}` returns authenticated exports with BOQ traceability and semantic state. `POST` and `GET /projects/{id}/bootstrap/boq-sources/{source-id}/revision-delta` compare a normalized BOQ revision without mutating the current authorized schedule.

## 3. Important commands

### Exact context authorization and human identity (remediation R10)

`POST /projects/{id}/authorized-context/activate` requires `Idempotency-Key`,
`source_version_id`, `authority_grant_id`, `expected_current_context_id`, an approval reference,
and a reason. The expected current ID is null for initial authorization and the exact current ID
for replacement. Stale predecessors and changed idempotent replays return 409. Only an active,
actor-owned, project-wide grant of the matching context type permits activation: baseline/current
schedule approval according to source state, budget approval, BOQ approval, or progress-weighting
approval. Package- or amount-bounded grants cannot authorize a whole context. A raw `CHANGE_APPROVAL`
grant cannot bypass the reviewed project-context change route.

Activation freezes the exact grant ID, scope, validity dates, predecessor, and request hash in
immutable audit history. An identical replay returns its original context, even if later
superseded or the grant is now revoked; it does not reauthorize that context. Project-row locks
serialize approvals and the existing database constraint enforces one current context per type.
Planner review freezes the then-current schedule predecessor; approval after replacement requires
fresh review. Subsequent reviews and approvals append new release versions.

All project/organization operations enforce tenant and active database membership before payload
or resource processing. Human-reserved commands independently reject service/unknown identities
and `SYSTEM_SERVICE` membership, even when that identity also holds admin roles and grants.
Creating VERIFIED/CORROBORATED evidence through typed creation or import requires a human verifier
or project admin; reported ingestion remains available to authorized service principals. Audit
actor type records the authenticated principal classification. See the deployment claim contract
in [production hardening](20-production-hardening.md).

Migration `0031_audit_append_only` adds PostgreSQL UPDATE/DELETE and TRUNCATE rejection to audit
history. Its downgrade removes enforcement without deleting historical rows. Deployment must
still restrict the runtime role from owning schemas, disabling triggers, or issuing DDL.

### Read-only snapshot assistant (remediation R8)

`POST /projects/{id}/project-control/snapshots/{snapshot-id}/assistant` accepts `question` and/or a
selected `topic`: overview, completion, schedule, cost, forecast, RAG, risks, evidence, or next
review. The caller must have project read access. This query performs no database writes and has
no execution, approval, communication, or model-tool adapter. Action/instruction-injection requests
produce an explicit `ACTION_NOT_PERMITTED` response; unsupported questions remain unsupported.

Answers contain structured facts, exact source record citations, input data dates, state/truth
semantics, limitations/unknowns, separate management considerations/review routes, generator
version, and deterministic content hash. A fidelity validator compares each fact with the exact
frozen fact catalog and checks advisory text and citation allowlists. Completion arithmetic is
Decimal-based. Financial fields are package/assessment scoped, not fabricated project totals;
insufficient assessments cannot turn intermediate zeros into supported facts. Forecasts and
reported risk/issue/change records retain their source semantics. Later project records and
current mutable case state cannot enter an answer to an older snapshot.

### Snapshot-bound project health (remediation R7)

`POST /projects/{id}/project-control/snapshots` accepts optional `health_policy` and exact
`schedule_assessment_ids`. A selected policy requires project-admin privileges, a matching recording
owner, version, rationale, effective date, explicitly ordered numerical thresholds, source freshness,
and material package weight. Reusing a policy version with different parameters fails with 409.
All parameters and derived results are frozen on the snapshot. Omitting policy leaves health
Unknown and preserves the existing snapshot API and idempotency contract.

Health contains progress, supported schedule completion exposure, EAC/budget alignment, evidence
confidence, and historical governance dimensions. Every result carries its rule, thresholds, input
references, cut-off, confidence/unknown confidence, limitations, and Red/Yellow review route.
Package RAG is calculated first; project materiality aggregates the exact authorized weights.
Known adverse conditions stay visible alongside unknown coverage. Neither Green nor a recorded
clear analytical route conveys execution approval.

`supporting_context` freezes selected schedule assessments, historical case-snapshot/audit routes,
and cut-off-valid project context records. Later case transitions and context versions do not enter
an issued snapshot. All new case audit events preserve governance/readiness/lifecycle state;
older events without those fields remain Unknown. Reports use the exact stored health projection
shown by the command center. Migration rollback refuses to discard populated immutable health or
supporting context; rollback is available before those fields have governed data.

### Report-derived stakeholder presentations (remediation R9)

The project-control snapshot response includes `shared_metrics` (`CONTROL-METRICS-1.0.0`), the
deterministic factual projection consumed by dashboard, persisted reports, assistant, and slides.
Percentages use decimal arithmetic and explicit display rounding. Cost values remain assessment-
and work-scope-specific; insufficient assessments expose Unknown rather than intermediate totals.
New report snapshots freeze project identity and the shared projection without changing older
immutable reports.

Under `/projects/{id}/decision-center`, `POST /presentations` accepts `report_snapshot_id` and
unique `recipient_record_ids` with `Idempotency-Key`. The report must already be approved and its
payload hash must match. Recipients must be exact ACTIVE stakeholder versions marked as report
recipients in that report's frozen context. Later registry changes are not substituted. This
command generates a self-contained HTML slide deck with complete embedded source JSON, source
approval linkage, semantic notices, Unknowns, and escaped reported text. It sends no messages.
Unsupported or oversized presentations fail rather than truncating their source.

`GET /presentations` and `GET /presentations/{id}` expose immutable source/generator/content hashes,
selected recipient versions, fidelity manifest, actor, and lifecycle history.
`POST /presentations/{id}/lifecycle-events` requires its own idempotency key, exact
`expected_version` (event count, initially 1), reason, and REVIEWED then APPROVED transitions.
Approval requires that actor's active project-wide `REPORT_APPROVAL` grant, including validity
dates; amount- or package-bounded grants cannot approve the deck. Changed replays and stale
commands fail with 409.

`GET /presentations/{id}/content` downloads a deck for internal review.
`GET /approved-presentations/{id}/content` additionally requires presentation approval. Both
validate stored bytes and source lineage and record an audit event. The download includes
`X-VAI-Content-SHA256`, `X-VAI-Source-Report`, `nosniff`, and private/no-store headers. Browser
printing is available inside the deck; the server stores and approves the exact HTML bytes,
not a separately printed PDF. Neither report nor presentation approval grants execution authority.

Migration `0030_presentation_artifacts` adds append-only artifact and lifecycle tables. Empty
downgrade is reversible; downgrade refuses to discard populated immutable presentation history.

### Governed progress workbook ingestion (remediation R6)

Upload the XLSX through the project evidence-artifact route first, then call
`POST /projects/{id}/progress/workbook-imports` with `Idempotency-Key`, `artifact_id`, the exact
`schedule_context_id`, timezone-aware `data_date`, explicit `reported_confidence`, and a mapping
for every workbook task (`task_id`, `activity_code`, `controlled_object_id`). The source must be a
clean scanned project artifact whose stored hash still matches. Task names/dates, project object
codes, reporting dates, current-authorized context, and authorization time must match. Formulas,
fractional or duplicate task IDs, invalid percentages, stale context, missing mappings, and tenant
or role mismatch fail closed. Failed imports do not commit partial measurements.

Every supplied completion becomes separate immutable reported evidence and a `REPORTED`
measurement; unreported rows create neither and retain unknown values. The immutable import
freezes activity mappings, input artifact, source evidence/measurement IDs, network/calendar
basis, formula version, limitations, and cut-off. `GET /progress/workbook-imports` and
`GET /progress/workbook-imports/{id}` return that history. Reusing the same idempotency key with
different input fails, and reimporting the same artifact/context/cut-off with a new key is rejected.
The saved path never calls the calendar-day/max-task preview approximation. Verification,
acceptance, and downstream schedule assessment remain separate governed commands.

### Material bootstrap corrections (Amendment A prerequisite)

`POST /projects/{id}/bootstrap/schedule-drafts/{generation-id}/corrections` requires a human
planning actor and `Idempotency-Key`. It accepts the exact `expected_structure_version_id`,
`expected_logic_proposal_id` (null only if no logic exists), a correction reason, complete typed
`draft_inputs` (duration/productivity plus validation owner), and optional complete `logic_inputs`.
An omitted logic input preserves the existing explicit/template relationships, milestones,
constraints and calendar assumptions. Caller-supplied relationship/activity references name the
**previous** draft; the server remaps them to the new activities. Generated procurement
prerequisites are regenerated without duplicating explicit/template edges.

The command locks project correction sequencing, rejects stale structure/logic, no-op inputs,
foreign activity references, payload/key mismatches and machine/service/read-only callers. It
atomically creates a successor reviewed structure and proposed generation, copying/remapping
logic when present. It never creates a calculation, planner schedule release, authorized context
or execution instruction. Fresh CPM, validation, planner review and exact human authority remain
separate. A prior current/baseline context remains unchanged.

Immutable structure `change_summary.material_correction` retains previous/new generation IDs,
previous logic, field paths, original/revised inputs, previous activity durations/bases, actor,
UTC time, reason and semantic notice. `GET /schedule-drafts/{id}` exposes that metadata as
`correction_history` (null for older/non-correction generations); source planning-structure
history also exposes it for refresh/recovery. `PlanningCalendarInput.source_reference` is an
optional bounded provenance string for a reviewed calendar correction. Existing schema/history
and taxonomy values are retained; there is no persistent schema migration for this command.

### Governed project context (remediation R5)

`POST /projects/{id}/project-context/records` creates an immutable charter, stakeholder, daily
update, risk, issue, or change-request version. `GET /records` and `GET /records/{record-id}` retain
every version, evidence link, lifecycle event, and semantic notice. Writes require
`Idempotency-Key`; changed payloads with a reused key fail with 409. Successors must name the exact
latest `supersedes_record_id`. The single charter stream uses `record_key=PROJECT_CHARTER`.

`POST /records/{record-id}/transitions?expected_version=N` appends a human lifecycle event;
`N` is the current lifecycle-event count, starting at zero. It requires its own idempotency key,
reviewer role, valid transition, and current record version. Analysts and contributors cannot
record human lifecycle decisions. Charter and change approval additionally require a matching,
active, project-wide `CHARTER_APPROVAL` or `CHANGE_APPROVAL` grant owned by that actor and an
explicit approval reference; bounded amount or package grants cannot authorize an unbounded
project context change.

Operational records require active project evidence. Daily updates validate evidence dates and
their cut-off against the project's timezone; review never creates verification or progress
measurements. Change requests freeze `affected_context_type` and
`expected_authorized_context_id` (null only when no authorized context exists). Approval rejects
stale controlling context and requires an exact, unused, project-local `PROPOSED` context source.
It creates a new authorized context through the existing activation service and records that
context ID on the immutable lifecycle event. It does not mutate the source payload or authorize
execution. These APIs provide persisted context; they do not send stakeholder communications.

Use action endpoints or explicit command resources for behavior that is more than CRUD:

- screen/dismiss a signal;
- correlate a signal, open a case, or link to a case;
- request evidence and record verification;
- evaluate/re-evaluate a case;
- submit for review and publish a recommendation;
- record a human disposition;
- authorize a response through its governed route;
- close or reopen a case;
- import and activate an authorized context version;
- run benchmark and generate conformity report.

Each command returns resulting resource version, emitted event IDs, governance result, and any validation/authorization errors.

## 4. Query projections

### Production browser identity and request gates (R10)

`GET /auth/login` starts a server-side OIDC code/PKCE transaction; `GET /auth/callback` validates
state, nonce, access-token identity, and client ID-token binding before setting a short-lived
encrypted HttpOnly host cookie. `GET /auth/session` returns mode, verified actor, and organization
only. It never returns a token. `POST /auth/logout` clears that browser session. Development/test
session discovery returns DEVELOPMENT mode without upgrading local identity into production.

All cookie-authenticated mutations require the configured exact HTTPS Origin. Explicit bearer
API clients continue to use their signed token, database membership, and exact authority grants.
Saved browser actor/organization fields are not production identity. Size/rate refusals return
413/429 before a command can commit; chunked bodies are counted independently of Content-Length.
See `docs/20-production-hardening.md` for configuration, limits, and deployment verification.

Provide paginated, filterable projections for decision queue, evidence queue, contradictions, upcoming clocks, human-review queue, open responses, and KPI views. Filters include project, owner, controlled object, case type, lifecycle, readiness, disposition, confidence, priority, governance state, reporting period, and overdue clock.

## 5. Events

Internal outbox events include:

`EvidenceRegistered`, `EvidenceVerified`, `ContradictionDetected`, `SignalRaised`, `SignalScreened`, `CaseOpened`, `SignalLinked`, `CaseEvaluationRequested`, `EvaluationCompleted`, `EvidenceRequested`, `RecommendationPublished`, `HumanDecisionRecorded`, `ResponseAuthorized`, `OutcomeObserved`, `CaseClosed`, `CaseReopened`, `AuthorizedContextActivated`, and `PolicyChanged`.

Events include event/schema version, event ID, aggregate/version, tenant/project, occurred/recorded times, actor, correlation/causation IDs, and data classification. Consumers must be idempotent; an outbox prevents database/event divergence.

## 6. Error contract

Machine-readable errors contain code, message, field paths, correlation ID, retryability, and safe details. Required codes include semantic-basis mismatch, stale version, insufficient evidence, unresolved contradiction, governance blocked, authority required, forbidden transition, duplicate/idempotent command, and unsupported conclusion.

## 7. Compatibility

Bootstrap schedule review accepts optional `control_inputs`: calculated activity code, an active
same-project WORK_PACKAGE/ACTIVITY ID, measurement basis, source reference, and explicit planned
points (date, numerator, denominator, unit, basis). Dates must be unique/ascending, with consistent
unit/denominator and the selected basis. Duplicate activity/object mappings, foreign/missing
objects, unknown activities and conflicting basis edits fail closed. Inputs are attributed in
review history; omitted plans remain unknown. Approval rechecks the stored object mapping.

Baseline bootstrap approval creates a separate BASELINE context and a CURRENT_AUTHORIZED context
linked to that source. Current-only approval creates a PROPOSED source and current successor,
retaining any formally approved baseline reference. An unapproved BASELINE source is not treated
as approval. Authorized payloads preserve server-owned calculation/review/control/authorization
lineage; exports also retain the original BOQ references. Planned measurements must match the
authorized point exactly; an authorized schedule does not verify actual progress.

Migration `0032_context_history_guard` protects context payload/source/approval history from SQL
UPDATE/DELETE/TRUNCATE. Only CURRENT_AUTHORIZED → SUPERSEDED with a valid supersession timestamp
and every other field unchanged is permitted. Downgrade removes these guards without deleting
context history. Earlier review hashes remain compatible when optional control inputs are absent.

Additive changes remain backward compatible within a major API version. Taxonomy/schema/policy versions travel with stored outputs. Breaking changes require migration, replay-impact analysis, and contract tests for web, imports, reports, and benchmark fixtures.
