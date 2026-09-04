# 01 — Architecture and Engineering Standards

## 1. Recommended architecture

Build a modular monolith first. Preserve domain boundaries in code and schema so workloads can be separated later without premature distributed-system complexity.

- Web application: Next.js + TypeScript.
- API and decision runtime: Python + FastAPI + Pydantic.
- Domain/persistence: PostgreSQL + SQLAlchemy + Alembic.
- Background work: PostgreSQL-backed jobs for MVP; introduce a dedicated broker only when volume proves necessary.
- Evidence objects: S3-compatible object storage with hashes and immutable versions.
- Identity: OIDC provider with project-scoped RBAC.
- Telemetry: OpenTelemetry-compatible traces, structured logs, metrics, and immutable audit records.
- Packaging: containers; local development through one compose profile.
- AI use: provider-neutral adapter behind governed, schema-constrained tasks. Deterministic calculations and policy rules remain authoritative.

Any stack change requires an Architecture Decision Record and must preserve the contracts in this documentation.

## 2. Logical modules

| Module | Owns | Must not own |
|---|---|---|
| Identity & Tenancy | users, roles, organizations, project access | analytical conclusions |
| Control Context | projects, objects, schedule, budget, BOQ, authorized versions | actual evidence |
| Evidence | source records, provenance, claims, verification, contradictions | baseline changes |
| Signals & Correlation | signal screening, dedupe, case linkage | dispositions |
| Decision Cases | lifecycle, readiness, assembled case snapshot | human authority |
| Specialist Analysis | bounded progress, schedule, cost, forecast, impact outputs | cross-domain writes |
| Policy & Governance | autonomy, permissions, gates, approval/escalation requirements | hidden overrides |
| Human Decisions | explicit decisions, authority, response authorization | recommendation generation |
| Outcomes & Learning | response tracking, outcome evidence, close/reopen, calibration | retroactive history edits |
| Reporting & KPI | projections, exports, metrics | source-of-truth mutation |

## 3. Runtime flow

1. Ingestion stores raw input and normalized evidence without overwriting prior versions.
2. Screening emits relevant signals with reason codes.
3. Correlation links a signal to an existing open case or proposes a new case.
4. Orchestrator creates an immutable evaluation snapshot.
5. Sufficiency and governance gates determine which analyses may run.
6. Specialists read the snapshot and return typed outputs with evidence references and limitations.
7. Orchestrator resolves contradictions, applies confidence ceilings, and assembles a recommendation.
8. Human reviewer records a separate disposition and any authorized response.
9. Outcome monitoring ingests new evidence, closes or reopens cases, and records learning/calibration data.

## 4. Deterministic and AI boundary

Use deterministic code for identifiers, taxonomy validation, arithmetic, units, date logic, version selection, schedule-network calculations, threshold policies, confidence ceilings, lifecycle transitions, permissions, audit, and benchmark scoring.

AI may assist with document extraction, evidence classification, candidate correlation, contradiction explanation, bounded diagnosis hypotheses, narrative assembly, and reasoning evaluation. Every AI output must:

- conform to a versioned schema;
- cite stored evidence IDs;
- label assumptions, unknowns, judgments, and scenarios;
- be validated by deterministic policy gates;
- include model/provider/prompt/policy versions;
- be replaceable by manual or deterministic input;
- never write authorized state or a human decision.

## 5. Repository target layout

```text
apps/web/                 Next.js Decision Center
services/api/             FastAPI routes and composition
packages/domain/          entities, value objects, state machines
packages/decision_engine/ deterministic analysis and policies
packages/specialists/     bounded specialist contracts/adapters
packages/connectors/      CSV/XLSX/API/document ingestion
packages/contracts/       JSON Schema/OpenAPI/event schemas
packages/reporting/       exports and KPI calculations
tests/unit/
tests/integration/
tests/contract/
tests/governance/
tests/benchmarks/
fixtures/synthetic/
infra/
docs/adr/
```

## 6. Engineering rules

- UTC storage; project timezone for display and calendar calculations.
- Decimal quantities and money; never binary floating-point for commercial arithmetic.
- Units and currencies are explicit; conversions are versioned and traceable.
- Append-only versions for governed records. Corrections supersede; they do not erase.
- Idempotency keys for imports and commands; optimistic concurrency on mutable workflow records.
- Every derived value carries formula/policy version and input references.
- Database constraints enforce semantic separation where possible.
- Narrative is generated from structured truth and may simplify but never strengthen it.
- No secrets or personal data in logs, prompts, or benchmark fixtures.

## 7. Quality gates

Every merge must pass formatting, static types, linting, unit tests, schema compatibility, migrations against a clean database, authorization tests, governance invariant tests, and affected benchmark cases. Production deployment additionally requires backup/restore evidence, security review, performance checks, and a conformity report.

