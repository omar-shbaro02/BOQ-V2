# Phase 12 Operator Usability Protocol

## Purpose

Validate that a pilot Project Delivery Manager can identify the next material Decision Case and
explain its evidence, uncertainty, clocks, recommendation, human authority route, and next action
without confusing those concepts. Automated tests establish workflow availability; they do not
substitute for an observed session with a representative operator.

## Participants and setup

- Recruit at least one Project Delivery Manager and one project-controls practitioner who did not
  implement the workflow.
- Use 5–10 realistic work packages and the five frozen case types `DC-SYN-001` through `005` when
  those Phase 13 fixtures are available. Until then, use equivalent seeded cases covering
  intervention, harmless delay, weak evidence, cost/progress divergence, and authorized change.
- Record browser, viewport, assistive technology if used, project timezone, participant role, and
  test-data version. Do not use live confidential project data.
- Start the amended session with a non-confidential XLSX BOQ containing direct execution,
  procurement, material-only, provisional, summary, and ambiguous rows; include two direct rows
  that belong to one work package. Prepare a superseding BOQ revision with added and changed scope.

## BOQ-first bootstrap tasks (Amendment A)

Run these before the Decision Center tasks below. The project-controls practitioner operates the
planner stages; the Project Delivery Manager performs the authority and release stages.

1. In ten minutes, upload the workbook at `/bootstrap`, inspect the immutable source version,
   normalize it, and explain why summary, material-only, provisional, and ambiguous rows were not
   silently scheduled.
2. In ten minutes, review proposed packages and the two-to-one BOQ/activity trace, supply a
   defensible productivity or explicit duration basis, and identify every unresolved assumption.
3. In ten minutes, propose dependencies, milestones, and a reviewed working calendar; calculate
   CPM and explain the proposed finish, float, critical activities, deadline variance, and any
   blocker. An intentionally conflicting deadline must not become approval-ready.
4. In ten minutes, submit planner review, attempt publication without the matching active grant
   (expect denial), then use the separate authorized human route to publish and export JSON, CSV,
   and XLSX. Verify that the authorized schedule is the current control context and that export
   notices distinguish proposals from authority.
5. In five minutes, upload the superseding BOQ, review added/removed/changed scope and available
   mapping/activity/schedule effects, and show that the current authorized schedule remains
   unchanged until a newly reviewed version is separately approved.

Record each task's time, errors, facilitator prompts, source and schedule version IDs, export
hashes, grant scope, and the participant's explanation of each semantic boundary. Any invented
duration, unreviewed calendar presented as fact, blocker bypass, authority bypass, or revision
that silently changes the current schedule is a hard failure. Both participants must complete the
stages appropriate to their role without a hard failure before Amendment A operator acceptance.

## Time-boxed tasks

1. In three minutes, select the case needing the earliest management attention and explain why its
   priority and urgency differ from its confidence.
2. In five minutes, identify the evidence limitation blocking a decision, its owner/deadline, and
   the correct verification queue without treating unknown as zero.
3. In seven minutes, compare the latest recommendation with the recommendation linked to the signed
   human decision and explain any agreement/disagreement.
4. In ten minutes, record a human decision and response proposal, then identify the separate grant
   and reference required before execution can be observed.
5. In five minutes, inspect an evidence-backed outcome, close or reopen the case on a valid basis,
   and export the case dossier.
6. Using only the export, explain the applicable snapshot, policy/formula versions, truth labels,
   recommendation, human decision, authorization, execution observation, outcome, and limitations.

## Acceptance evidence

- Task completion time and completion/failure for every task.
- Incorrect semantic statements, wrong turns, inaccessible controls, and facilitator prompts.
- Successful keyboard-only traversal with visible focus and meaningful labels.
- Export hash verification and confirmation that JSON/CSV does not strengthen the source record.
- Participant confidence on a 1–5 scale plus verbatim improvement notes.

Phase 12 usability acceptance requires both participants to complete Tasks 1–3 and 5–6 without a
semantic-boundary error. Any recommendation interpreted as approval, proposal interpreted as
authorization, or observation interpreted as a system execution command is a hard failure.

## Current automated evidence

The integration suite covers the end-to-end governed case path, queue/review projections, stale
recommendation lineage, report envelopes, deterministic export hashes, CSV semantic columns,
tenant scope, and closure basis. ESLint, strict TypeScript, and the production build cover static UI
integrity. The representative human sessions above remain required before Phase 12 is marked
complete.
