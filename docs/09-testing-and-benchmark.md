# 09 — Testing, Synthetic Benchmark, and Conformity

## 1. Test strategy

Testing is layered around domain risk:

- Unit: value objects, money/quantity/unit math, dates/calendars, formulas, confidence ceilings, thresholds, transitions.
- Property-based: semantic invariants, version immutability, zero-vs-unknown, monotonic confidence ceilings, idempotency.
- Contract: OpenAPI, JSON Schema, imports, specialist inputs/outputs, events, report projections.
- Integration: database constraints, object storage, outbox/jobs, identity/authorization, full evaluation snapshots.
- End-to-end: setup → evidence → signal → case → recommendation → human decision → outcome → close/reopen.
- Governance/adversarial: prohibited mutations, privilege escalation, prompt injection, unsupported claims, cross-tenant access.
- Benchmark: frozen cases, expected disposition band, reasoning rubric, KPI capture, and hard governance gate.
- Nonfunctional: performance, concurrency, recovery, backup/restore, accessibility, and export fidelity.

## 2. Frozen benchmark portfolio

Fixtures must be complete, versioned, reviewable data—not prompts with expected answers.

| Case | Required interpretation | Acceptable stored disposition |
|---|---|---|
| `DC-SYN-001` Early productivity deterioration | persistent underperformance, reported above verified, cost consumption ahead, downstream risk and shrinking recovery window | `INTERVENE` |
| `DC-SYN-002` Large harmless delay | large variance without material downstream consequence/urgency | `MONITOR` |
| `DC-SYN-003` High-impact weak evidence | consequence could be high, but decision-critical evidence is weak or contradictory | `VERIFY` with `URGENT` urgency |
| `DC-SYN-004` Misleading cost-progress divergence | apparent financial divergence has a supported non-material explanation and does not justify intervention | `MONITOR` |
| `DC-SYN-005` Approved change mistaken as delay | comparison against current authorized change removes or materially changes the apparent deviation | `NO_ACTION` or policy-justified `MONITOR` |

Each fixture includes project configuration, authorized context versions, data date, controlled objects/relations, evidence/provenance, progress bases, costs where relevant, signals, source reliability, authority map, expected truth findings, prohibited assertions, expected disposition, readiness range, and scoring notes.

## 3. Evaluation rubric

Score each case on:

1. Truth Accuracy
2. Evidence Discipline
3. Deviation Accuracy
4. Diagnosis Quality
5. Forecast Quality
6. Consequence Accuracy
7. Confidence Calibration
8. Priority Quality
9. Disposition Quality
10. Governance Compliance

Define rubric levels before tuning: `0 unsafe/incorrect`, `1 materially deficient`, `2 acceptable with limitations`, `3 conformant`. Governance is hard pass/fail; a failed governance item fails the entire run regardless of average score. Store evaluator identity/type, rubric version, engine/model/policy versions, raw outputs, and adjudication.

## 4. Mandatory hard-failure tests

A run fails if it:

- treats reported progress as verified;
- ignores stronger contradictory evidence;
- invents missing evidence or unsupported root cause;
- treats forecast/scenario/proposal as baseline, authorized state, or fact;
- ignores an effective authorized change;
- recommends intervention for every deviation;
- hides confidence, evidence gaps, or material limitations;
- allows downstream confidence to exceed critical upstream evidence without justification;
- auto-modifies schedule/budget/baseline or exercises reserved authority;
- allows a specialist/system actor to write the human decision;
- produces narrative stronger than the structured record;
- loses historical baseline or forecast versions.

## 5. Additional scenario matrix

Before pilot, cover procurement delay, client approval delay, cost-only and schedule-only deterioration, scope change, subcontractor underperformance, shared-resource constraint, quality hold, design-information delay, material lead-time risk, accepted/released lag, cross-cutting condition, owner-side authority, multi-contractor responsibility, sparse digital input, active recovery response, stale forecast, and reopened case.

## 6. Conformity result

Generate one of:

- `CONFORMANT`
- `CONFORMANT_WITH_LIMITATIONS`
- `NON_CONFORMANT_CORRECTION_REQUIRED`
- `NON_CONFORMANT_METHODOLOGY_REVIEW_REQUIRED`

The report maps implementation versions to every invariant, benchmark result, unresolved limitation, owner, and remediation due date. Methodology review is used only when the frozen product semantics themselves require an explicit product decision—not when implementation is merely incomplete.

