# 02 — Domain Model and Semantic Contracts

## 1. Aggregate roots

### Project

Owns identity, timezone, delivery model, reporting calendar, configured taxonomies, authority map, and pointers to authorized context versions.

### Controlled Object

Generic project entity referenced by a case: work package, activity, milestone, BOQ item, approval, procurement item, change, risk, resource, area, or project. Relations express containment, dependency, responsibility, and cross-cutting scope.

### Evidence Item

Immutable observation or source-derived record with provenance. One source document may yield multiple evidence items. Evidence can support or contradict claims and must retain the source artifact reference.

### Decision Case

The primary intelligence aggregate. It owns case identity, linked signals and controlled objects, lifecycle, evaluation snapshots, readiness, specialist outputs, recommended disposition, governance route, and links to—but not ownership of—human decisions and outcomes.

### Human Decision

A separate append-only record created by an authorized person. It contains decision, rationale, authority scope, limitations, timestamp, and optional response authorization.

## 2. Mandatory state semantics

Every time-dependent project datum is tagged with exactly one semantic state:

| State | Meaning |
|---|---|
| `BASELINE` | formally established reference version |
| `CURRENT_AUTHORIZED` | currently approved controlling state, possibly changed from baseline |
| `ACTUAL` | observed occurrence or consumption |
| `REPORTED` | assertion received but not necessarily verified |
| `VERIFIED` | checked against an accepted verification method |
| `FORECAST` | expected future state from a stated basis |
| `PROPOSED` | requested but not authorized change |
| `SCENARIO` | hypothetical bounded alternative |
| `SUPERSEDED` | retained historical version replaced by a newer one |

State transitions are explicit. Observation may update `ACTUAL`; analysis may create `FORECAST` or `SCENARIO`; only an authorized change command can create a new `CURRENT_AUTHORIZED` version and supersede the previous one.

## 3. Mandatory truth semantics

Every assertion is tagged with one truth type:

`VERIFIED_FACT`, `CORROBORATED_FACT`, `REPORTED_CLAIM`, `DERIVED_METRIC`, `ASSUMPTION`, `UNKNOWN`, `CONTRADICTED`, `JUDGMENT`, or `SCENARIO_ESTIMATE`.

Required rules:

- Zero is a value; unknown is absence/uncertainty. They are never interchangeable.
- A derived metric references its inputs and formula version.
- Corroboration records independent supporting sources and the policy used.
- Contradiction retains every conflicting assertion and cannot be resolved by deletion.
- A diagnosis can be `UNKNOWN`; plausible causes remain labeled hypotheses/judgments.
- Semantic tags inherit into derivatives and narratives. A transformation cannot upgrade truth.

## 4. Progress contract

Progress measurements contain quantity, unit, numerator, denominator, as-of time, measurement basis, state, truth type, source, and controlled object. Supported bases include:

- physical quantity executed;
- physical quantity verified;
- accepted/released quantity;
- duration elapsed;
- weighted milestone;
- BOQ/value earned;
- reported percent complete.

Percentages with different bases must not be compared as if equivalent. `Executed`, `Verified`, and `Accepted/Released` remain distinct when the project uses those gates.

## 5. Schedule, cost, and forecast contracts

- Schedule versions include authorized status, calendars, activities, logic links, constraints, milestones, data date, and source lineage. Minimal schedule conclusions require planned start/finish and relevant dependency; float is conditional.
- Cost records keep approved budget, authorized changes, current authorized budget, commitments, actuals, accruals when available, forecast-to-complete, and estimate-at-completion separate.
- BOQ records preserve item, description, quantity, unit, rate, currency, value, revision, and mapping to controlled objects. Missing BOQ cannot block conclusions that do not depend on it.
- Forecasts include target metric, method, input snapshot, production basis, horizon, point/range result, assumptions, scenario flag, confidence by horizon, and expiry/recalculation trigger.

## 6. Decision Case minimum fields

- Identity, title, project, type, opened time, owner, and attached controlled objects.
- Signal links and correlation rationale.
- Control-context snapshot and authorized version references.
- Evidence set, sufficiency assessment, contradictions, and requested evidence.
- Current truth, deviation, diagnosis, forecast, consequence, confidence, urgency, priority.
- Readiness and limitations.
- Recommended disposition and reason codes.
- Governance state, autonomy class, required reviewer/approver/escalation route.
- Human decision link, response, outcome, closure/reopen reason, and learning record.

## 7. Lifecycle and readiness

Primary lifecycle:

`OPEN → EVIDENCE_ASSEMBLY → ANALYSIS → REVIEW → DECISION_READY → HUMAN_DISPOSITION → RESPONSE_ESCALATION → OUTCOME_MONITORING → CLOSED`

Governed side states are `BLOCKED` and `REOPENED`. Transition tables must define actor, preconditions, command, emitted event, and prohibited transitions. Closing requires an outcome or explicit administrative rationale. New material evidence, forecast expiry, failed response, or renewed consequence may reopen a case.

Readiness is separate from lifecycle:

- `DECISION_READY`
- `DECISION_READY_WITH_LIMITATIONS`
- `VERIFICATION_REQUIRED`
- `INSUFFICIENT`

## 8. Semantic invariants

- Forecast is not fact or baseline.
- Recommendation is not human decision.
- Status, impact, priority, confidence, and variance magnitude are independent fields.
- Reported progress is not verified progress.
- Installed/executed is not accepted/released where those gates apply.
- Confidence cannot exceed critical upstream evidence without explicit, stored justification.
- Authorized changes are compared against the correct effective authorized version.
- Historical baselines and forecasts remain queryable and reproducible.

