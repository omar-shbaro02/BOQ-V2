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

