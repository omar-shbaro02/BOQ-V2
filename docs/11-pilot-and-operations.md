# 11 — Pilot, Observability, and KPI Measurement

## 1. Pilot contract

- Mode: shadow/advisory; execution authority is none.
- Scope: one active construction project, approximately 5–10 meaningful work packages.
- Core cases: productivity deterioration, schedule/dependency threat, cost-progress divergence, evidence conflict, and milestone exposure.
- Cadence: align ingestion and case review to the project's reporting cycle, plus event-driven material evidence.
- Participants: accountable PM, project controls, data contributors/verifiers, pilot product owner, auditor/evaluator, and named escalation authority.

Before launch, sign off the authorized context, authority map, evidence mappings, materiality policies, review/service targets, KPI definitions, expected comparison process, and incident route.

## 2. KPI instrumentation

Capture timestamps for signal occurrence (when knowable), evidence observation/receipt, signal creation, case opening, evidence request/completion, decision-ready state, recommendation publication, human review/decision, response authorization/start, consequence realization, and case closure.

For Intervention Lead Time, publish the exact formula and counterfactual/reference timestamp before pilot scoring. Report distribution and individual adjudicated cases; do not hide negative or zero lead time in an average.

Precision/recall require an adjudicated material-condition set and documented review of missed cases. Disposition agreement is not automatically correctness. Forecast error uses frozen forecast versions and matching horizons. Confidence calibration groups predictions by comparable outcome definitions.

## 3. Operational telemetry

Monitor:

- ingestion success, rejects, lag, duplicates, stale feeds, and evidence age;
- signals by outcome, correlation accuracy, cases by lifecycle/readiness/governance;
- evaluation duration/failure/retry, specialist limitations, contradiction count/age;
- forecast expiry, urgent clocks, overdue evidence/review/escalation;
- recommendation-to-human agreement and override reasons;
- policy/model/schema versions and narrative validator failures;
- authorization denials, suspicious access, audit continuity, object-store errors;
- API latency/error, job backlog, database/object storage capacity, backup status.

Alerts must name owner, severity, runbook, and business consequence. Avoid paging on expected `INSUFFICIENT` decisions; alert on systemic evidence failure or breached service targets.

## 4. Runbooks

Create and test runbooks for failed import, incorrect object mapping, stale/invalid baseline, unresolved contradiction, evaluation failure, unsupported AI output, wrong recommendation report, suspected unauthorized change, tenant/data exposure, unavailable dependency, backup restore, and audit gap.

Emergency containment may disable ingestion, evaluation, AI narrative, exports, or a tenant/project independently. It must not erase evidence or history.

## 5. Pilot review and exit

Weekly review samples correct, incorrect, missed, overridden, verification-blocked, and closed/reopened cases. Record whether the cause is data quality, configuration, engine defect, usability, operator process, or methodology gap.

Pilot completion requires enough reporting cycles to observe meaningful cases and outcomes; no fixed duration substitutes for evidence. The final report covers KPI results, governance incidents, forecast/calibration results, operator feedback, limitations, maintenance burden, and recommended next Decision Case type.

