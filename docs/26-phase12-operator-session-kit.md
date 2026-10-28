# Phase 12 operator session kit and delivery gates

This kit prepares representative human acceptance. It is **not a completed session record**.
Automated actors, generated fixtures and a successful R10 run cannot stand in for participants.

## Recommended local scenario

Use the non-confidential five-package concrete scenario: foundations, columns, beams, slabs and
stairs. The connected API exercise preserves two BOQ lines per package, distinct allocations,
four explicit finish-to-start prerequisites and separate baseline/current authorization.
Each synthetic package has 200 m3 scope; the explicit fixture productivity is 100 m3/working day,
not a production default or an engineering-approved construction sequence. Sourced authorized
planned quantity is 200 m3 and separately verified quantity is 80 m3 at a common observation time.
Explicit BOQ-value weights are 0.2 each. The aggregate is 100% planned and 40% verified completion.

Only the first package has the selected cost and schedule assessments. Its USD 2,000 authorized
budget, 1,200 commitment, 900 actual, 100 accrual and separate earned/physical values must not be
presented as project-wide cost totals. Missing analyses for the other packages retain unknowns.
The selected verified delay is 8 days. An earned-value EAC is a forecast, not actual expenditure
or new budget authority. No liability or entitlement is inferred.

The API test emits `operator-boq.xlsx` and `operator-boq-revision.xlsx` beside its manifests. The
revision changes the first line from 120 to 130 m3 with a reconciled amount and adds retaining-wall
scope under WP-06. It is a proposed input for the operator's revision task; generating the file
does not import it, update allocations or replace an authorized schedule. Both the one-package
and five-package exercises run on SQLite and enforcing PostgreSQL, including logical recovery.

Run `scripts/verify_r10.py` to regenerate current evidence. Find the five-package source files under
the new run's `postgres/pytest/.../five-package/` directory. The connected manifest identifies its
project, source/artifact, baseline/current contexts and exact per-step record references.
Fixtures in the browser setup test use their own fresh organization/project and are separate
from the API scenario; do not combine their records as one completed 17-step UI journey.

## Operator preparation

The recommended participants are:

- a Project Delivery Manager accountable for delivery and familiar with approval/escalation routes;
- a planner or project-controls practitioner who works with BOQs, calendars, schedules and progress;
- optionally, an independent accessibility or audit observer.

The two required participants must not be implementers of this workflow. Actual people and a live
pilot project have not been supplied; role recommendations do not create participation evidence.
Use synthetic data for sessions and provision their test memberships/grants through the existing
administrator route. Never assign production authority based on a generated fixture role.

1. Open `/setup`, create or select the acceptance project, and **Load project controls**.
2. Create the WBS/work packages. Save the charter, review it, and use a separate matching grant to
   approve its exact version. Register the stakeholder and report-recipient communication rules.
3. Use `/bootstrap/advanced` to preserve, normalize, review and schedule the BOQ. Supply explicit
   productivity/calendar/dependency inputs and control mappings; separately authorize the baseline.
4. Return to `/setup` to save proposed weights and budget. Inspect the exact proposal and use the
   separate matching authority to activate each. Explain each retained source/version boundary.
5. In `/evidence` and `/progress`, record reported updates and separate human verification, then
   normalize measurements against the exact authorized planned points. Daily updates in `/setup`
   remain reported and require active project evidence at or before the reporting cutoff.
6. Use the signal/case workbenches to review correlation, freeze evidence and select supported
   progress, schedule, cost and forecast assessments. Missing inputs must visibly restrict analysis.
7. In `/progress`, expand **Issue project-control snapshot**. Explicitly choose authorized weights
   and schedule, matching planned/verified-or-accepted pairs, exact optional case assessments and
   the approved project health thresholds. No numerical thresholds or amounts are prefilled.
8. Open the command center, query its frozen-snapshot assistant, then review and separately approve
   a report and stakeholder presentation in the Decision Center. Download and compare source facts.

These are preparation instructions, not facilitator prompts to deliver during a measured task.
Use the time-boxed tasks and hard-failure rules in [the operator protocol](15-operator-usability-protocol.md).
Its five core condition types still require representative case coverage; five work packages do
not constitute five distinct benchmark cases.

## Session record template — NOT RUN

Copy this section into the acceptance evidence folder for each actual session; leave unknowns
blank. Preserve observations as observed or participant-reported, with their source explicit.

| Field | Actual observation |
| --- | --- |
| Session ID/date, observer and data version | Pending |
| Participant identifier, role and independence from implementation | Pending |
| Browser/viewport, input method and assistive technology | Pending |
| Project timezone, source/version IDs and starting state | Pending |
| Task number, start/end time and completed/failed result | Pending |
| Wrong turns, inaccessible controls and facilitator prompts | Pending |
| Participant explanation of truth, uncertainty, priority/clocks and authority | Pending |
| Export/artifact hashes and source parity | Pending |
| Confidence (1–5) and verbatim feedback | Pending |
| Semantic-boundary errors, defect reference and retest result | Pending |
| Accountable acceptance decision and supporting evidence | Pending |

## Remaining phase gates

| Phase | What can be evidenced now | Required exit evidence still open |
| --- | --- | --- |
| 12 | Operator setup, governed controls, snapshot creation, multi-package API scenario and browser regressions | Representative planner/PM sessions, core-case task coverage and manual accessibility. Full 17-step browser creation remains separate from the API proof. |
| 13 | Existing R10 engineering prerequisites and fresh dependency audits | Phase 12 acceptance first; then frozen benchmark portfolio/rubric, extended scenarios, deployed-provider/load/recovery acceptance, conformity review and findings closure. |
| 14 | Pilot requirements in document 11 and this proposed package scope | Phase 13 exit and explicit pilot entry; an actual active project, named participants/authority, approved KPI/reference definitions, real reporting cycles, adjudicated outcomes and go/no-go review. |

This preserves the repository's phase order. No observed acceptance, production deployment,
completed benchmark, real pilot KPI, project participant or live-project result is invented.
