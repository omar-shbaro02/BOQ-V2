# 00 — Product Charter and Acceptance Contract

## 1. Product thesis

Project managers often have enough data but lack a continuously reliable, reconciled, forward-looking view of which conditions need management attention now. VAI adds a governed decision layer above source systems. Its value is earlier credible intervention while recovery options still exist.

## 2. Primary operator, buyer, and scope

- Primary operator: accountable Project Delivery Manager, initially a contractor-side Project Manager.
- Buyer: projects or operations leadership in a construction organization.
- Initial scope: one project, 5–10 work packages, shadow mode.
- Controlled objects: work packages, activities, milestones, BOQ items, approvals, procurement items, risks, changes, resources, and cross-cutting conditions. MVP must fully support work packages and activities; other object types use an extensible attachment contract.
- Decision ownership: package, area, project, and escalation hierarchy.

## 3. Frozen primary decision

Given current execution evidence, authorized project constraints, and credible forecasts, determine which current or emerging project-control condition warrants management intervention now instead of continued monitoring, verification, or no action.

Supporting analysis—detection, verification, comparison, diagnosis, forecast, impact, confidence, urgency, and priority—must serve this decision and must never be presented as the human decision itself.

## 4. Required end-to-end capability

The product must support this complete chain:

`Raw evidence / signal → relevance screen → case correlation → Decision Case open/update → evidence sufficiency → truth assessment → deviation → diagnosis → forecast → consequence → confidence → multi-clock urgency → priority → recommended disposition → human decision → response/escalation → outcome monitoring → close/reopen → learning`

It must also preserve the operating chain:

`Authorize → plan → observe → report → structure → verify → reconcile → compare → diagnose → forecast → assess impact → prioritize → decide → simulate response → approve/escalate → execute → verify outcome → update authorized state → learn`

## 5. MVP functional scope

1. Project and control context, including current authorized schedule and optional cost/BOQ context.
2. Evidence registry with provenance, versions, confidence, time, source reliability, and verification state.
3. Signal intake, screening, deduplication, and correlation into Decision Cases.
4. Progress truth across reported, executed, verified, and accepted/released measurements.
5. Schedule and dependency analysis, including milestones, float when available, and downstream exposure.
6. Cost and commercial alignment, including approved budget, actual, committed, earned/physical basis, and explanation of apparent divergence.
7. Bounded forecast and scenario evaluation with assumptions, horizons, and uncertainty.
8. Consequence, confidence, multi-clock urgency, priority, and recommended disposition.
9. Evidence requests, contradictions, limitations, stop states, and escalation routing.
10. Separate human decision, authority, response, outcome, closure, reopening, and learning records.
11. Decision Center queues, case detail, audit history, reports, and KPI instrumentation.
12. Synthetic benchmark runner and implementation conformity report.

## 6. Explicit non-goals

The MVP is not a full ERP, Primavera or MS Project replacement, BIM authoring suite, procurement ERP, complete claims platform, safety-management system, autonomous project manager, giant dashboard suite, or generic chatbot. BOQ data is strategically valuable but not mandatory for every conclusion.

## 7. Success metrics

Primary KPI: **Intervention Lead Time**—the time gained between VAI's first decision-ready recommendation and the point at which the same material condition would otherwise have become actionable under the agreed comparison method.

Supporting KPIs:

- Material Exception Precision and Recall
- Decision/Disposition Accuracy and operator agreement
- Completion and cost-at-completion forecast error
- Confidence calibration
- Decision latency and time to decision-ready evidence
- Recovery window preserved
- Schedule and avoidable cost deterioration reduced

Metric definitions, timestamps, denominators, cohorts, and comparison method must be versioned before pilot measurement.

## 8. Release acceptance

Release is accepted only if:

- Decision Case is the primary intelligence unit.
- All mandatory state and truth semantics are enforced in storage, services, UI, and narrative.
- The runtime can return `VERIFICATION_REQUIRED` or `INSUFFICIENT` without inventing a conclusion.
- Recommendations and human decisions are separately authored, stored, permissioned, and audited.
- Authorized baselines cannot be mutated through analytical workflows.
- Historical evidence, baselines, forecasts, decisions, and reasoning remain reproducible.
- Five frozen benchmark cases pass expected disposition ranges, reasoning evaluation, and governance hard gates.
- Pilot operator can understand why a case exists, what is known, what is uncertain, what may happen, why it matters now, and who must decide.

