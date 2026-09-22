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

Provide paginated, filterable projections for decision queue, evidence queue, contradictions, upcoming clocks, human-review queue, open responses, and KPI views. Filters include project, owner, controlled object, case type, lifecycle, readiness, disposition, confidence, priority, governance state, reporting period, and overdue clock.

## 5. Events

Internal outbox events include:

`EvidenceRegistered`, `EvidenceVerified`, `ContradictionDetected`, `SignalRaised`, `SignalScreened`, `CaseOpened`, `SignalLinked`, `CaseEvaluationRequested`, `EvaluationCompleted`, `EvidenceRequested`, `RecommendationPublished`, `HumanDecisionRecorded`, `ResponseAuthorized`, `OutcomeObserved`, `CaseClosed`, `CaseReopened`, `AuthorizedContextActivated`, and `PolicyChanged`.

Events include event/schema version, event ID, aggregate/version, tenant/project, occurred/recorded times, actor, correlation/causation IDs, and data classification. Consumers must be idempotent; an outbox prevents database/event divergence.

## 6. Error contract

Machine-readable errors contain code, message, field paths, correlation ID, retryability, and safe details. Required codes include semantic-basis mismatch, stale version, insufficient evidence, unresolved contradiction, governance blocked, authority required, forbidden transition, duplicate/idempotent command, and unsupported conclusion.

## 7. Compatibility

Additive changes remain backward compatible within a major API version. Taxonomy/schema/policy versions travel with stored outputs. Breaking changes require migration, replay-impact analysis, and contract tests for web, imports, reports, and benchmark fixtures.
