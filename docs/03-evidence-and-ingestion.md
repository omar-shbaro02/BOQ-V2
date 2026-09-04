# 03 — Data Intake and Evidence Pipeline

## 1. Minimum viable inputs

Required for the relevant core case:

- project identity;
- controlled work package/activity and responsible owner;
- planned start/finish and measurable progress basis;
- relevant schedule dependency;
- reporting date;
- actual or verified progress evidence;
- current work status;
- forecast basis/current production rate;
- evidence provenance and confidence;
- decision owner.

Conditionally required only when the conclusion depends on them: approved budget, actual/committed cost, BOQ quantity/value, milestone, float, blocker/cause evidence. The sufficiency policy is conclusion-specific—not a universal completeness checklist.

## 2. Intake channels

MVP supports manual structured entry plus CSV/XLSX imports for project context, schedule extracts, progress, cost, and BOQ; file upload for source evidence; and a connector interface for future APIs. Each import has preview, mapping, validation, rejection report, idempotency key, and immutable batch record.

Do not silently coerce ambiguous dates, currencies, units, percentages, or object mappings. Route ambiguity to user mapping or verification.

## 3. Evidence processing stages

1. Receive artifact/record and calculate content hash.
2. Record tenant, project, source system/person, captured/observed/received/as-of times, and access classification.
3. Preserve raw artifact and parser/extractor version.
4. Normalize candidate assertions without changing their truth strength.
5. Validate units, identity, time range, controlled-object mapping, and duplicate status.
6. Assign initial state/truth labels and source reliability prior.
7. Link supporting and contradicting evidence.
8. Request human verification when policy requires it.
9. Publish versioned evidence events for screening and affected open cases.

## 4. Provenance and reliability

Every evidence item includes source type, source ID, author/provider when known, collection method, timestamps, artifact pointer/hash, extraction method, reviewer, verification method, and confidence. Reliability history is tracked by source and evidence class; it may inform confidence but never erase current contradictory evidence.

## 5. Signal screening and case correlation

A signal is an observation worth evaluating, not yet a Decision Case. Screening returns relevance, materiality candidate, reason codes, affected objects, expiry, and next action. Noise can be dismissed with an auditable reason.

Correlation considers project, controlled objects, condition type, causal/dependency relations, reporting interval, open cases, and active responses. It returns `LINK_EXISTING`, `OPEN_NEW`, `CROSS_CUTTING_PARENT_CHILD`, `DEFER`, or `DISMISS` with confidence and rationale. Low-confidence matches require review; the system must not collapse independent issues into one case merely because they share a project.

## 6. Contradiction handling

- Preserve each assertion and source.
- Identify the precise field, period, basis, and object in conflict.
- Prefer evidence according to configured verification policy, independence, recency, measurement basis, and source reliability—not narrative confidence.
- Mark unresolved material conflict as a limitation and route to `VERIFICATION_REQUIRED` or human review.
- Re-evaluate every dependent metric and case when a contradiction is resolved.

## 7. Baseline validity and active response awareness

Before calling a deviation, confirm that the selected baseline/current-authorized version was effective at the case data date. Flag stale, disputed, or structurally invalid baselines. Detect active authorized recovery/change responses and assess performance against that response; do not repeatedly recommend intervention as if no response exists.

## 8. Acceptance tests

- Reimporting the same batch is idempotent.
- Corrections create superseding records without history loss.
- Unsupported mappings fail visibly.
- A reported percentage never becomes verified through import alone.
- Missing cost or BOQ data does not block a schedule-only conclusion.
- Missing minimal schedule evidence blocks a schedule-intervention conclusion.
- Strong contradictory evidence lowers readiness/confidence and generates a verification path.

