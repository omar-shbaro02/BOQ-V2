# 04 — Decision Engine Specification

## 1. Evaluation principle

Truth precedes intelligence. Every evaluation is run against an immutable input snapshot and produces a versioned result. Re-evaluation creates a new version; it never rewrites prior reasoning.

## 2. Pipeline

### Step 1 — Control context

Resolve project, controlled objects, accountable owner, decision owner, reporting/data date, relevant authorized versions, measurement bases, dependencies, milestones, budget/BOQ when relevant, authority map, and active responses. If the applicable authorized state is unclear, challenge baseline validity and restrict conclusions.

### Step 2 — Evidence sufficiency

Evaluate required evidence by candidate conclusion. Return present, missing, stale, contradictory, and requested evidence plus maximum supportable readiness. Missing evidence narrows the conclusion; it never produces filled-in facts.

### Step 3 — Current truth

Reconcile reported, actual, verified, executed, and accepted/released measures. Output explicit assertions with truth type, evidence references, as-of time, and confidence. Surface unresolved contradictions.

### Step 4 — Deviation detection

Compare compatible measurement bases against the correct current-authorized state. Calculate magnitude, direction, duration, trend, and threshold crossings. A single transient observation does not establish a persistent trend unless policy explicitly allows it.

### Step 5 — Diagnosis

Identify evidenced cause, contributing factors, and alternative hypotheses. Separate known cause, judgment, assumption, and unknown. Never force a root cause. Record whether an active response explains or is already addressing the condition.

### Step 6 — Forecast

Project bounded outcomes using explicit method, current production/cost basis, horizon, dependencies, assumptions, range, and scenario. Confidence normally decays with horizon. Store forecasts separately from authorized schedule/budget and actual state.

### Step 7 — Consequence

Assess credible effects on dependent work, milestones, completion, cost, quality/acceptance, commercial exposure, recovery options, and decision authority. Consequence must reference the causal/dependency path and forecast/evidence supporting it.

### Step 8 — Confidence

Calculate separate confidence for truth, diagnosis, forecast, consequence, and overall recommendation. Apply ceilings from critical upstream evidence. Any override requires a reason and reviewer-visible provenance.

### Step 9 — Multi-clock urgency

Keep at least these clocks separate:

- time until consequence/material milestone impact;
- time needed to verify missing evidence;
- time needed for management/contractual approval;
- time needed to mobilize a response;
- remaining recovery window.

Urgency derives from the interaction of those clocks, not simply from status color or lateness.

### Step 10 — Priority

Priority ranks management attention using consequence, urgency/recovery window, confidence, strategic/materiality policy, cross-cutting reach, and active-response status. Large variance can have low priority; modest deterioration can have high priority when options are closing.

### Step 11 — Readiness and disposition

Apply governance gates first, then select one allowed disposition:

| Disposition | Typical condition |
|---|---|
| `NO_ACTION` | no material current/emerging consequence or authorized change explains variance |
| `MONITOR` | credible condition exists but intervention is not yet justified; specify trigger/date |
| `VERIFY` | material decision hinges on resolvable weak/conflicting evidence; specify request and deadline |
| `INTERVENE` | credible, sufficiently supported material condition needs action within owner authority |
| `ESCALATE` | material condition exceeds authority, crosses governance threshold, or requires urgent senior/specialist review |

`VERIFY` may carry an urgency attribute such as `URGENT`; `VERIFY_URGENTLY` is a presentation label, not a sixth stored disposition.

### Step 12 — Decision handoff

Produce a structured case brief: condition, evidence, contradictions, deviation, diagnosis/unknowns, forecast, consequences, confidence, clocks, priority, recommended disposition, limitations, evidence request/monitoring trigger, authority route, and prohibited autonomous actions.

## 3. Policy configuration

Thresholds, weights, materiality bands, confidence bands, evidence expiry, trend persistence, escalation routes, and calendars are versioned by project/delivery model. Defaults must be visible and overrideable only by authorized configuration roles. Configuration changes affect future evaluations unless an explicit replay is requested.

## 4. Stop rules

Stop or limit the pipeline when identity, applicable authorized context, measurement basis, required dependency, or critical evidence is unavailable/contradicted. A stop result includes readiness, exact blocker, safe conclusions, requested evidence, owner, and due time. No narrative may imply a stronger conclusion.

## 5. Explainability contract

Every recommendation must answer:

1. What condition exists or may emerge?
2. Which evidence supports and contradicts it?
3. Compared with which authorized state and measurement basis?
4. What is known, derived, assumed, judged, or unknown?
5. What consequence is credible, by when, and through what path?
6. How confident is each layer and why?
7. Which clock makes it urgent or not urgent?
8. Why this disposition instead of each plausible alternative?
9. Who has authority and what must happen next?

## 6. Narrative fidelity

Case summaries are projections of structured results. They must cite evaluation and evidence IDs, use qualified language matching truth/confidence, retain material contradictions/limitations, distinguish forecast/scenario from fact, and never claim that a recommendation was approved or executed.

