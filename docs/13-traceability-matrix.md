# 13 — Requirements Traceability Matrix

This matrix proves that every frozen methodology stage has an implementation and verification home. The source stages are product requirements; this repository's documents are the engineering plan.

| Source stage | Required capability preserved | Primary implementation documents | Verification |
|---|---|---|---|
| 1 Operator Reality | accountable PM, reconciliation responsibility, authority boundary | 00, 06, 08 | role/authority E2E and prohibited-action tests |
| 2 Business Pain | reliable current truth and forward visibility for earlier intervention | 00, 04, 11 | pilot lead-time and truth-quality review |
| 3 Decision Freeze | five dispositions and one primary management question | 00, 04 | disposition rule/benchmark tests |
| 4 Hero Scenario | productivity, conflicting progress/cost, dependency and milestone risk | 02–05, 09 | `DC-SYN-001` fixture and E2E |
| 5 Value and KPI | Intervention Lead Time and supporting KPIs | 00, 11 | versioned metric tests and pilot report |
| 6 Operating Chain | authorized/actual/forecast separation and full learn loop | 02, 04, 06, 10 | state-transition and end-to-end tests |
| 7 Minimum Inputs | conclusion-specific sufficiency; BOQ conditional | 02–04 | missing-data and schedule-minimum tests |
| 8 Decision Architecture | truth through governed handoff; stop allowed | 04 | pipeline contract and stop-rule tests |
| 9 Orchestrator | lifecycle, coordination, contradictions, closure/reopen | 02, 05 | orchestration integration tests |
| 10 Specialists | five bounded analytical responsibilities | 05 | contract and forbidden-write tests |
| 11 Shared Schema | complete schema, state/truth taxonomies, semantic distinctions | 02, 07 | schema/property/constraint tests |
| 12 Governance | autonomy classes, governance states, human authority | 06 | hard governance suite and audit review |
| 13 Pressure Test | persistence, inheritance, signals/correlation, cross-cutting cases, horizon confidence, baseline validity, reliability, multi-clock urgency, narrative fidelity, reasoning quality, active response | 02–05, 08–10 | explicit unit/integration/benchmark cases |
| 14 Plasticity | progress gates, scoped ownership, multiple object types, configurable delivery/evidence maps, specialist authority boundary | 00–06, 09 | extended scenario matrix |
| 15 Synthetic Dataset | five frozen cases and ten scoring dimensions | 09 | automated run plus human adjudication |
| 16 Conformity | implementation labels and mandatory product preservation | 09 | generated conformity report |
| 17 Pilot Wrapper | shadow mode, 1 project, 5–10 packages, core cases/KPIs, no execution | 00, 10, 11 | pilot readiness and outcome reviews |
| 18 Commercial Story | earlier credible decisions, differentiated Decision Cases, advisory boundary | 00, 08, 11 | pilot decision brief and KPI evidence |
| 19 Expansion/Handoff | MVP sequence and Decision-Case-led expansion | 10, 12 | phase gates and expansion approval |

## Cross-cutting functionality checklist

- [x] Controlled project context and effective authorized versions
- [x] Evidence provenance, reliability, verification, contradiction, and supersession
- [x] Signals distinct from cases; screening, dedupe, correlation, cross-cutting linkage
- [x] Decision Case lifecycle, snapshots, readiness, blocked/closed/reopened states
- [x] Reported/executed/verified/accepted progress and measurement bases
- [x] Schedule dependencies, milestones, optional float, and baseline validity
- [x] Cost, commitments, actuals, BOQ/earned basis, authorized changes, and commercial boundary
- [x] Bounded/versioned forecasts, scenarios, assumptions, horizons, and confidence decay
- [ ] Consequence paths, confidence propagation, multi-clock urgency, and priority
- [ ] Five dispositions with monitoring triggers/evidence requests and explanations
- [ ] Five bounded specialist responsibilities and orchestrator failure/contradiction behavior
- [ ] Governance/autonomy states, scoped roles, separate human decision, response authority
- [ ] Outcomes, active-response awareness, closure/reopen, and learning/calibration
- [ ] Decision Center, review queues, audit ledger, fidelity-preserving reports/exports
- [ ] Synthetic benchmark, extended scenarios, hard failures, and conformity report
- [ ] Pilot instrumentation, operational observability, security, recovery, and expansion gate

The checklist becomes executable backlog items during build. An item is complete only when its implementation, UI/API exposure where applicable, authorization, audit, documentation, and tests all meet the relevant phase exit gate.
