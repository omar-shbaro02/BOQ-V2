# 06 — Governance, Security, and Audit

## 1. Autonomy classes

- `A0_OBSERVATION_READ_ONLY`: ingest, view, and notify without analysis.
- `A1_ANALYTICAL_AUTONOMY`: structure, calculate, detect, reconcile, forecast, and assess.
- `A2_ADVISORY_AUTONOMY`: prioritize, recommend, and prepare escalation.
- `A3_CONTROLLED_EXECUTION`: execute only a precisely scoped command after explicit human authorization; outside MVP default.
- `A4_HUMAN_RESERVED`: baseline/scope/budget approval, contractual commitments, regulated professional/safety decisions, liability, and management decision.

MVP operates through A2. A3 capability must be disabled by default even if interfaces anticipate it.

## 2. Governance states

`ANALYSIS_AUTHORIZED`, `VERIFICATION_REQUIRED`, `HUMAN_REVIEW_REQUIRED`, `APPROVAL_REQUIRED`, `ESCALATION_REQUIRED`, `GOVERNANCE_BLOCKED`, and `AUTHORIZED_TO_PROCEED`.

Governance state is separate from case lifecycle, readiness, recommendation, and human decision.

## 3. Hard prohibitions

The analytical runtime cannot:

- modify or silently replace an authorized baseline;
- approve scope changes or material expenditure;
- publish an approved schedule revision;
- issue contractual commitments or assign liability;
- record a human management decision;
- authorize project execution;
- make regulated technical, quality, or safety approvals;
- promote forecast/scenario/proposal into actual or authorized state.

Enforce these at API authorization, service command boundaries, database roles/constraints, and tests—not solely in prompts or UI.

## 4. Roles and segregation

Minimum roles: organization admin, project admin, data contributor, verifier, analyst/controller, decision owner, approver/escalation authority, auditor/read-only, and system service. Project-scoped grants and authority limits must support package, area, project, amount, decision type, and escalation hierarchy. A service principal cannot impersonate a human decision owner.

## 5. Command gates

Every material mutation command includes authenticated actor, tenant/project, authority basis, expected version, purpose, idempotency key, timestamp, and correlation ID. Commands that affect authorized state additionally require explicit approval record, scope, effective date, and source document. Analytical commands never share the same handler as authority commands.

## 6. Audit requirements

Append-only audit events capture actor/service, action, object/version, before/after references, time, request/correlation IDs, policy/config/model versions, and authority result. Retain evidence access logs and exports. Corrections are new events. Provide a chronological case ledger suitable for audit and pilot review.

## 7. Security baseline

- OIDC, MFA according to provider policy, short-lived sessions, secure cookies.
- Least-privilege RBAC plus project/controlled-object scope checks.
- TLS in transit; managed encryption at rest; secrets manager and key rotation.
- Tenant isolation in queries and database policy where practical.
- Malware scanning and content-type/size limits for uploads.
- Signed object URLs with short expiry.
- Input validation, output encoding, CSRF protection, rate limits, and dependency scanning.
- Data classification, configurable retention, legal hold/export, and recoverable deletion procedures.
- Backups, point-in-time recovery, and regularly tested restoration.
- AI prompt-injection defenses: artifacts are untrusted data, tool calls are allowlisted, and document text cannot alter system policy.

## 8. Governance acceptance tests

Tests must prove that an analyst/service cannot write a human decision, a recommendation cannot imply approval, a forecast cannot update an authorized schedule, baseline changes require the authority route, contradictory material evidence triggers review, and every protected command produces a complete audit event or fails atomically.

