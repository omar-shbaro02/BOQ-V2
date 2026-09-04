# Implementation Status

Last updated: 2026-09-04

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

## Next phase

Phase 3 — Signals, screening, and case correlation.

Next implementation order:

1. Deterministic signal candidates for progress, schedule, cost, evidence conflict, and milestone exposure.
2. Relevance/materiality screening, expiry, reason-coded dismissal/defer, and idempotent deduplication.
3. Reviewed correlation outcomes for existing, new, and cross-cutting Decision Cases.
4. Signal inbox, project-scoped authorization, and audit events.
