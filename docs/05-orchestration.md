# 05 — Specialists and Project Control Decision Orchestrator

## 1. Orchestrator mandate

The Project Control Decision Orchestrator owns the Decision Case lifecycle, evaluation snapshot, evidence sufficiency, specialist coordination, contradiction routing, decision readiness, recommendation assembly, and governance routing. It is not an unrestricted super-agent and cannot exercise project authority.

## 2. Specialist contracts

Each specialist accepts a case ID, immutable snapshot ID, scoped inputs, policy version, and requested questions. It returns a typed result containing findings, calculations, evidence references, truth labels, assumptions, contradictions, confidence, limitations, requested evidence, and version metadata.

### Evidence & Progress Specialist

Reconciles execution truth, progress bases, evidence provenance, acceptance/release state, trends, contradictions, and evidence gaps. It cannot verify evidence without a configured verification event or infer schedule/cost consequences outside its contract.

### Schedule & Dependency Specialist

Evaluates authorized schedule version, timing variance, calendars, logic, float when available, dependency propagation, milestone exposure, and minimal-schedule limitations. It cannot publish a schedule revision.

### Cost & Commercial Control Specialist

Evaluates approved/current-authorized budget, commitments, actuals, accruals, BOQ/value basis, cost-progress alignment, forecast exposure, and commercial limitations. It cannot approve spend, changes, claims, or liability.

### Forecast & Scenario Specialist

Produces bounded forecasts/scenarios under explicit assumptions and horizons; compares continued-performance and approved-response states; quantifies ranges and horizon confidence. It cannot turn a forecast into actual or authorized state.

### Impact & Priority Specialist

Assesses consequence paths, multi-clock urgency, recovery-window erosion, cross-cutting reach, relative priority, and candidate disposition inputs. It cannot record the human decision.

These are logical boundaries. MVP may execute them as deterministic modules plus limited AI calls rather than five separate agents.

## 3. Coordination algorithm

1. Lock/select the evaluation snapshot and policy versions.
2. Run sufficiency and governance prechecks.
3. Run evidence/progress analysis.
4. Run schedule and cost analysis in parallel when their required inputs exist.
5. Run forecast only on semantically valid upstream outputs.
6. Run impact/priority after consequence inputs exist.
7. Detect incompatible facts, bases, versions, assumptions, and confidence claims across outputs.
8. Resolve deterministically where policy permits; otherwise request verification/review.
9. Apply confidence propagation and horizon decay.
10. Assemble readiness and candidate recommendation.
11. Apply governance gates and publish a versioned recommendation.

## 4. Failure and retry behavior

Specialist failure cannot be hidden. Record status (`PENDING`, `RUNNING`, `SUCCEEDED`, `LIMITED`, `FAILED`, `SUPERSEDED`), attempts, error class, and partial safe outputs. Retries must be idempotent and reuse the snapshot. If a critical specialist fails, downgrade readiness or stop. Noncritical missing analysis may produce `DECISION_READY_WITH_LIMITATIONS` only when policy permits.

## 5. Contradiction protocol

Classify contradictions as source, semantic-basis, version, temporal, calculation, or specialist-judgment conflicts. Resolution must name the chosen assertion, rejected/limited assertions, policy or reviewer basis, and downstream invalidations. Material unresolved contradictions require verification or human review.

## 6. AI safeguards

- Tool/data access is allowlisted per specialist.
- Inputs are minimized to the scoped case and project permissions.
- Outputs must validate against JSON Schema; invalid outputs retry then fail closed.
- Evidence citations are checked against the snapshot.
- Unsupported numbers/causes are rejected.
- Prompts and outputs are recorded with appropriate redaction and retention controls.
- Model output cannot invoke baseline, budget, authorization, execution, or human-decision commands.

