# Schedule-Change Assistant

## What it does

The Schedule-Change Assistant turns a written planning request into a **proposed** revision of a
six-column MS Project import workbook. Typical requests include a delay, an earlier completion
target, resequencing, a duration change, or a dependency change.

It returns one ZIP file with a re-importable XLSX, a planner-facing Word report, and a structured
JSON manifest. It uses `gpt-5.6-sol` by default, configured only on the server with
`VAI_OPENAI_SCHEDULE_ASSISTANT_MODEL` and `VAI_OPENAI_API_KEY`.

## What it is allowed to change

Only existing task duration, start date, finish date, and predecessor IDs may change. Every task ID
and name must remain exactly as supplied. It cannot add, delete, split, merge, or re-scope work.

## How it avoids drift and hallucination

The assistant is not trusted as the final scheduler. It is constrained in layers:

1. It receives only the uploaded schedule and the current request. Both are untrusted data, so
   hidden instructions cannot change its rules.
2. It must return strict structured data: feasibility, evidence gaps, risks, assumptions, planner
   actions, and a complete task list.
3. It must not invent crews, productivity, access, permits, calendars, approval status, funding,
   contractual entitlement, or scope. Missing information becomes an evidence gap.
4. The server rejects changed task IDs or names, missing/duplicate tasks, invalid dates, unknown or
   self dependencies, and dependency cycles.
5. The report retains the prompt version, model, source-workbook SHA-256 digest, and changed-task
   count. It is visibly labelled as a proposal.

For deadline compression, the assistant may identify possible parallel work or resequencing, but it
must say `CONDITIONAL` or `NOT_FEASIBLE_WITH_GIVEN_EVIDENCE` where the supplied schedule does not
prove the target can be met.

## What it cannot do

- Approve, authorize, baseline, or publish a schedule.
- Give contractual, legal, commercial, or safety authority.
- Assert that a plan is executable, risk-free, or contractually entitled.
- Replace a qualified planner or the Microsoft Project recalculation.

## Operator workflow

1. Save the current six-column schedule XLSX.
2. Open `/bootstrap/schedule-assistant`, upload it, and state the desired change plus known constraints.
3. Read feasibility, evidence gaps, risks, and planner actions in the Word report.
4. Import the proposed XLSX into Microsoft Project and recalculate.
5. Have a qualified planner review it. Use the governed Bootstrap workflow for authorization or a baseline.

## Future additions to consider

- Reviewed project calendars, productivity libraries, and resource constraints.
- A planner-approved catalogue of construction sequence templates.
- Persistent proposal/audit records and governed comparison with the authorized schedule.
- Evaluation fixtures for delay, compression, missing-evidence, calendar, and prompt-injection cases.
