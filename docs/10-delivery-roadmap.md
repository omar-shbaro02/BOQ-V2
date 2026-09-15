# 10 — Step-by-Step Delivery Roadmap

## Delivery rule

Build a vertical Decision Case capability before visual polish, then expand Decision Case by Decision Case. No phase is complete on code alone: its migration, authorization, audit, tests, documentation, and operator-visible failure states must also pass.

## Amendment A — corrective BOQ-to-Schedule prerequisite

The original roadmap assumed that a minimal authorized schedule already existed. The accepted BOQ-to-Schedule Bootstrap amendment closes that operational gap. Its detailed B0.1–B0.8 plan and BS-001–BS-010 gates are defined in `docs/17-boq-to-schedule-bootstrap.md`.

In a greenfield build this capability precedes Phase 1. In this repository, Phases 0–11 and the technical portions of Phase 12 already exist, so it is inserted as a corrective prerequisite before Phase 13 rather than renumbering or discarding governed downstream work. Phase 12 operator acceptance must be repeated against the BOQ-first journey after the corrective track is complete.

## Phase 0 — Bootstrap and freeze contracts

Work:

1. Create repository layout, local environment, CI, formatting/types/linting, test harness, migrations, seed mechanism, and ADR template.
2. Record selected stack and deployment topology in ADR-001.
3. Encode state, truth, disposition, readiness, lifecycle, governance, autonomy, controlled-object, and progress-basis taxonomies in shared schemas.
4. Add semantic invariant and forbidden-action tests before feature code.
5. Establish versioning, idempotency, audit, timezone, decimal/unit/currency, and error conventions.

Exit gate: clean environment boots; migration and rollback rehearsal pass; shared schemas are generated/consumed by API and web; governance tests initially fail for explicit unimplemented reasons rather than being absent.

## Phase 1 — Identity, project, and control context

Work:

1. Implement organization/project boundaries, OIDC integration, roles, project scopes, and authority hierarchy.
2. Create project, controlled-object graph, ownership, calendars, reporting periods, and delivery-model configuration.
3. Implement versioned baseline/current-authorized schedule context with activities, dependencies, milestones, and optional float.
4. Implement optional budget and BOQ versions with mapping, quantity, unit, rate, currency, and authorized changes.
5. Add guarded activation command for current-authorized versions and immutable history.

Exit gate: a user can configure one pilot project and activate a minimal authorized schedule; analytical roles cannot modify authorized context; effective-version selection is tested.

## Phase 2 — Evidence model and intake

Work:

1. Implement immutable artifacts, evidence items, assertions, provenance, state/truth labels, source reliability history, hashes, and supersession.
2. Implement manual entry and CSV/XLSX import preview/mapping/validation for context, progress, schedule, cost, and BOQ.
3. Add object storage, malware/size/type checks, batch idempotency, rejection reports, and access controls.
4. Implement verification events, support/contradict links, contradiction records, evidence requests, and expiry/staleness.
5. Add intake/evidence workbench.

Exit gate: conflicting reported and verified progress can coexist, be traced to source, and be routed for verification without silent coercion.

## Phase 3 — Signals, screening, and case correlation

Work:

1. Define signal types and deterministic candidate detectors for progress, schedule, cost, evidence conflict, and milestone exposure.
2. Implement relevance screening, dismiss/defer reason codes, expiration, dedupe, and materiality candidate.
3. Implement case-correlation suggestions and reviewed outcomes for existing/new/cross-cutting cases.
4. Add signal inbox and audit events.

Exit gate: signal and Decision Case remain distinct; duplicate inputs are idempotent; related and independent issues are correctly linkable without forced merging.

## Phase 4 — Decision Case lifecycle and sufficiency

Work:

1. Implement Decision Case aggregate, attachments, lifecycle transitions, ownership, snapshot creation, ledger, block/reopen/close rules.
2. Implement conclusion-specific minimum-evidence policies and readiness outcomes.
3. Add baseline-validity challenge and active-response detection.
4. Build evidence assembly view, requested evidence workflow, and limitation model.

Exit gate: cases can stop as `INSUFFICIENT` or `VERIFICATION_REQUIRED` with precise gaps, owner, and deadline; snapshots reproduce their source versions.

## Phase 5 — Progress truth and deviation intelligence

Work:

1. Support executed, reported, verified, and accepted/released progress with explicit measurement bases.
2. Implement reconciliation, compatible-basis comparison, planned/actual productivity, trend persistence, variance direction/magnitude/duration, and threshold policy.
3. Derive metrics with input/formula lineage and propagated semantics.
4. Surface contradictions and prevent unsupported truth upgrades.

Exit gate: the hero scenario's conflicting progress states are represented correctly; one noisy observation does not become a persistent trend.

## Phase 6 — Schedule and dependency intelligence

Work:

1. Parse and validate minimal schedule networks, calendars, constraints, dependencies, milestones, and float where supplied/calculable.
2. Calculate timing variance and downstream paths using the effective authorized version.
3. Assess dependency and milestone exposure with data-date and schedule-quality limitations.
4. Cover schedule-only and approved-change scenarios.

Exit gate: the engine distinguishes large harmless delay from smaller consequential delay and blocks unsupported schedule conclusions.

## Phase 7 — Cost and commercial intelligence

Work:

1. Reconcile approved/current-authorized budget, changes, commitments, actuals, accruals, BOQ value, physical/earned basis, and reporting periods.
2. Calculate cost-progress alignment and forecast-to-complete/EAC only when inputs support them.
3. Explain timing, procurement, prepayment, retention, mobilization, and measurement-basis effects without asserting contractual liability.
4. Cover cost-only and misleading-divergence scenarios.

Exit gate: cost signals retain currency/basis/version lineage, and the engine does not intervene merely because cost and physical percentages differ.

## Phase 8 — Forecast and scenarios

Work:

1. Implement deterministic production-rate and schedule consequence forecasts with ranges, assumptions, horizons, and recalculation triggers.
2. Add cost-at-completion forecasting where data is sufficient.
3. Support continued-performance, active-response, and hypothetical scenarios without contaminating forecast/authorized state.
4. Implement confidence decay by horizon and forecast version history.

Exit gate: forecasts are reproducible and visually/structurally distinct from facts, baselines, proposals, and scenarios.

## Phase 9 — Consequence, confidence, urgency, and priority

Work:

1. Implement consequence paths across dependencies, milestones, completion, cost, commercial exposure, and recovery options.
2. Implement confidence components, upstream ceilings, source reliability influence, override justification, and calibration logging.
3. Implement consequence, verification, approval, mobilization, and recovery-window clocks.
4. Implement transparent priority policy including cross-cutting reach and active-response awareness.

Exit gate: status/variance, consequence, confidence, urgency, and priority are stored and displayed independently; ranking has traceable reason codes.

## Phase 10 — Disposition, specialists, and orchestrator

Work:

1. Implement five bounded specialist contracts and run metadata.
2. Implement orchestrator sequencing, parallel safe analyses, retries, contradiction protocol, stop behavior, and deterministic validation.
3. Implement disposition rules, alternative-disposition explanation, readiness/limitations, and structured recommendation.
4. Add optional governed AI adapters and narrative fidelity validator only after deterministic contracts pass.

Exit gate: an evaluation produces a reproducible case brief, no specialist crosses its write boundary, and invalid/unsupported AI output fails closed.

## Phase 11 — Human governance and response lifecycle

Work:

1. Implement governance states, policy gates, review/approval/escalation queues, and authority validation.
2. Implement separate human decisions with actor, authority, rationale, agreement/disagreement, and timestamps.
3. Implement response proposal/simulation, explicit authorization link, execution-status observation, and outcome evidence.
4. Implement close/reopen and learning/calibration records.

Exit gate: end-to-end case completes without the runtime ever impersonating human authority; prohibited-action and audit tests pass.

## Phase 12 — Decision Center and reports

Work:

1. Implement setup, evidence workbench, signal inbox, decision/review queues, full case detail, and audit ledger.
2. Apply semantic visual rules, accessibility, responsive layouts, filtering, project timezone, and export fidelity.
3. Implement weekly decision brief, case dossier, exception, KPI, and conformity reports.
4. Conduct operator usability testing against all core case types.

Exit gate: a pilot PM can complete the core review workflow and explain the recommendation, uncertainty, clocks, authority, and next action from the UI/export.

## Phase 13 — Benchmark, hardening, and release candidate

Work:

1. Build frozen fixtures for `DC-SYN-001` through `005` and the extended scenario matrix.
2. Run scoring, reasoning-quality review, calibration checks, and every governance hard-failure test.
3. Perform cross-tenant, authorization, upload, prompt-injection, dependency, accessibility, performance, concurrency, backup/restore, and disaster-recovery checks.
4. Generate conformity report; resolve all hard failures and document limitations.

Exit gate: all five expected outcomes pass, governance is 100% pass, no critical/high security defect is open, restoration is demonstrated, and conformity is at least `CONFORMANT_WITH_LIMITATIONS` with pilot-safe limitations.

## Phase 14 — Shadow-mode pilot and learning loop

Work:

1. Select one live project and 5–10 packages; freeze KPI definitions, ground-truth/adjudication process, cadence, roles, escalation rules, and data retention.
2. Backfill context, validate authorized versions, train users, and run parallel/shadow review without execution authority.
3. Measure decisions, false/missed material exceptions, forecasts, confidence, time-to-evidence, and Intervention Lead Time.
4. Review weekly; classify product, data, policy, usability, and methodology issues separately.
5. Produce pilot outcome report and explicit go/no-go/iterate decision.

Exit gate: the pilot demonstrates evidence of earlier credible intervention decisions without governance breach; expansion is authorized explicitly rather than assumed.

## Dependency order

Phases 0–4 are foundational. Phases 5–7 may partially overlap after snapshots and evidence contracts stabilize. Phase 8 depends on valid progress/schedule/cost inputs; Phase 9 depends on forecasts and consequences; Phase 10 assembles them; Phase 11 precedes operational release. Amendment A must now complete before Phase 13, and Phase 12 acceptance must include its BOQ-first workflow. Phase 13 completes hardening and Phase 14 validates the product.
