# 08 — Decision Center, Human Workflow, and Reporting

## 1. UX principle

The interface is a Decision Center, not a status-dashboard wall. It should direct limited management attention while making evidence, uncertainty, authority, and the distinction between recommendation and decision unmistakable.

## 2. Required screens

### Project setup

Configure project identity, timezone/calendar, delivery model, users/roles, authority map, policies, controlled objects, minimal schedule, optional BOQ/budget, and data-source mappings. Activation requires validation and a visible authorized-context version.

### Intake and evidence workbench

Upload/import with preview and errors; browse source lineage; map objects/units; compare claims; verify/reject evidence; resolve contradictions; respond to evidence requests.

### Signal inbox

Show signal, source, relevance reason, affected objects, possible related cases, materiality candidate, and actions to dismiss/defer/link/open. Never label a signal as a management decision.

### Decision queue

Default sort reflects governed priority, urgency clocks, readiness, and active response—not just variance. Show concise condition, controlled objects, consequence window, confidence, recommended disposition, owner, next deadline, and limitation badge.

### Decision Case detail

Required panels:

1. Case identity, lifecycle, owner, attached objects, and active response.
2. Current condition and recommended disposition.
3. Readiness, governance route, limitations, and next required action.
4. Authorized-vs-reported-vs-verified/actual comparison with measurement bases.
5. Evidence ledger, provenance, supporting/contradicting links, and source reliability.
6. Deviation and trend persistence.
7. Diagnosis with known/unknown/hypothesis labels.
8. Forecast/scenario ranges and horizon confidence.
9. Consequence paths and multi-clock urgency.
10. Priority explanation and alternative-disposition rationale.
11. Separate human-decision form with authority validation.
12. Response, outcome, closure/reopen, and full chronological audit ledger.

### Review and governance queues

Dedicated queues for verification, human review, approval, escalation, governance blocks, overdue evidence, and expiring forecasts. Make the required role and deadline explicit.

## 3. Semantic visual rules

- Never encode confidence and priority with the same badge/color vocabulary.
- Always prefix forecasts/scenarios and show as-of/horizon.
- Show unknown as unknown, not zero or blank.
- Label reported, executed, verified, and accepted/released values separately.
- Display the applicable authorized version/effective date near comparisons.
- Human decision appears in a separate signed section; agreement with recommendation is calculated, not assumed.
- Narratives link to structured details and cannot hide material caveats.

## 4. Accessibility and usability

Meet WCAG 2.2 AA target, keyboard navigation, non-color-only state indicators, accessible tables/charts, responsive laptop/tablet layouts, preserved filter state, local project time display, and export parity. Test with realistic 5–10 package pilot data and time-box the core review flow.

## 5. Reports

MVP reports:

- weekly decision brief: new/changed/closed cases, recommended vs human disposition, urgent clocks, evidence gaps, active responses;
- case dossier: reproducible snapshot, evidence, structured reasoning, decisions, audit ledger, and outcomes;
- project-control exception report: material conditions only, with suppressed/dismissed signal counts;
- pilot KPI report: Intervention Lead Time and supporting metrics with cohort/definition versions;
- governance/conformity report: prohibited-action tests, review routes, benchmark results, and limitations.

Exports must preserve truth labels, limitations, timestamps, version IDs, and recommendation/decision separation. A PDF or spreadsheet summary must not strengthen the structured record.

