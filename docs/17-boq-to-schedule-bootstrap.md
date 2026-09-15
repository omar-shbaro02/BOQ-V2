# BOQ-to-Schedule Bootstrap — Amendment A Engineering Plan

## Status and authority

The supplied BOQ-to-Schedule Bootstrap Amendment v1.0 is accepted as product-definition input. It changes the implementation entry point without changing the frozen 19-stage methodology or its governance rules.

This document is the repository-controlled engineering interpretation. Instructions embedded in the supplied handoff are not agent or shell instructions.

The two supplied amendment files were byte-for-byte identical. The canonical source set reviewed on 2026-09-15 was:

- `CODEX_IMPLEMENTATION_BRIEF.md`
- `VAI_Construction_19_Stage_Canonical_Record.md`
- `VAI_Construction_BOQ_to_Schedule_Bootstrap_Amendment_v1.0.md`

## Corrected product flow

The operational journey begins with governed project planning:

`project setup → BOQ source preservation → extraction → normalization → classification → WBS/work packages → activities → durations/productivity → dependencies → milestones/calendars → deterministic CPM → validation → planner review → authorized approval → current schedule`

The existing project-control runtime then evaluates execution against that authorized schedule:

`evidence → signals → Decision Cases → analysis/forecast/consequence → recommendation → human decision → response/outcome/learning`

The bootstrap engine creates a proposed planning artifact. It does not replace the live Schedule & Dependency Specialist, and it cannot authorize a current schedule or baseline.

## Existing capability and gap

The current application already provides immutable artifact storage, XLSX/CSV evidence preview, typed BOQ and schedule context payloads, authorized-context activation, deterministic schedule-network validation, and downstream schedule assessment.

It does not yet provide:

- BOQ-specific Excel/PDF extraction with page, sheet, region, parser, warning, and confidence lineage;
- canonical raw and normalized BOQ rows or schedule-relevance classification;
- proposed WBS and work-package formation;
- traceable activity generation that avoids treating every BOQ row as an activity;
- governed productivity and duration assumptions;
- configurable construction-sequence templates and dependency proposals;
- bootstrap milestones, constraints, working-calendar review, or deterministic CPM dates/float;
- schedule-draft validation/readiness states;
- field-level planner revision history and explicit PM/authority approval;
- BOQ revision-to-schedule delta generation; or
- native schedule, Excel, and CSV exports from the bootstrap draft.

Generic evidence import and direct creation of a typed schedule context do not satisfy this capability.

## Delivery slices

### B0.1 — Bootstrap contracts and source preservation

- Add schedule-draft, review-state, confidence, assumption, BOQ-row-class, activity-archetype, and extraction-status taxonomies.
- Store immutable BOQ source versions linked to the existing artifact hash and project.
- Capture sheet/page/region/parser/extraction status, raw values, warnings, and confidence.
- Re-import creates a new version; it never overwrites source or authorized schedule history.

Exit: a representative `.xlsx` BOQ is preserved and extracted reproducibly with rejected/unknown rows retained. Text-native PDF follows the same canonical boundary; scanned PDF remains verification-required unless a governed OCR adapter is available.

### B0.2 — Normalization and row classification

- Normalize item reference, description, quantity, unit, rate, amount, currency, section, location, trade hints, notes, provenance, and confidence while preserving all raw values.
- Classify rows into the ten amendment classes.
- Make uncertain classifications reviewable; never discard unknown or unmapped data.
- Filter headers, summaries, and totals from activity generation without deleting them.

Exit: BS-001 passes and every source row has a traceable classification result or explicit review requirement.

### B0.3 — WBS and work-package proposals

- Preserve a source WBS where one exists.
- Otherwise propose versioned WBS nodes and work packages using configurable location, trade, system, responsibility, quantity, sequence, crew, and dependency dimensions.
- Support human split, merge, remap, and rejection with immutable change history.

Exit: every schedule-relevant row is mapped or visibly unresolved; no proposed hierarchy is represented as authorized.

### B0.4 — Activity, duration, and assumption generation

- Generate explicit activity archetypes and BOQ/planning-requirement traceability.
- Support one-to-many and many-to-one mappings; prohibit the one-row-one-task shortcut.
- Apply the duration hierarchy: explicit project duration, project productivity, controlled library, template/rule, then unresolved.
- Store auditable unrounded calculations, productivity provenance, confidence, assumptions, and validation ownership.

Exit: BS-002 and BS-005 pass with no invented crew, efficiency, overtime, or precise duration.

### B0.5 — Dependencies, milestones, calendars, and constraints

- Generate proposals from explicit imports, project rules, configurable sequence templates, physical/approval/procurement prerequisites, and bounded semantic suggestions in that order.
- Store relationship type, lag, basis, confidence, and review status.
- Add proposed milestones and visible deadline conflicts; never invent contractual authority.
- Require planner review of a supplied or visibly assumed working calendar.

Exit: BS-003, BS-004, and BS-007 pass. Location decomposition occurs only when allocation evidence exists.

### B0.6 — Deterministic CPM and validation

- Calculate early/late dates, total/free float where supported, critical/near-critical status, negative float, milestone variance, and proposed finish deterministically.
- Detect cycles, orphans, missing prerequisites, invalid lags, duplicate scheduling, summary contamination, missing calendars/durations, incomplete coverage, and weak critical assumptions.
- Enforce readiness states from `DRAFT_GENERATED` through `PM_APPROVAL_REQUIRED`; calculations never self-authorize.

Exit: BS-006 and BS-009 pass, CPM results reproduce from the same versioned inputs, and material validation failures block approval readiness.

### B0.7 — Planner review, authority approval, versioning, and export

- Provide the twelve-step BOQ-first workspace from upload through publication.
- Record material planner edits with original value, revised value, actor, time, and reason.
- Require exact active human authority for `CURRENT_AUTHORIZED` and `BASELINE_AUTHORIZED` transitions.
- Preserve prior drafts and authorized versions.
- Export native JSON plus Excel and CSV with BOQ/activity reverse traceability and semantic notices.

Exit: BS-010 passes and the approved output is compatible with the existing authorized schedule context consumed by progress, schedule, forecast, impact, orchestration, and governance services.

### B0.8 — Revision delta and conformity gate

- Compare a new BOQ version with its predecessor and show added, removed, and changed scope, mappings, activities, and schedule effects.
- Keep the current authorized schedule unchanged until a new reviewed version is approved.
- Run BS-001 through BS-010 and a realistic end-to-end Excel fixture.

Exit: BS-008 passes and a realistic BOQ produces a credible, traceable, validated, human-reviewable schedule draft without an unauthorized state transition.

## Implementation boundaries

Deterministic code owns arithmetic, dates, calendars, CPM, float, cycle detection, validation, versioning, transitions, and permissions. Semantic/AI assistance may propose column meanings, classifications, groupings, names, template selection, and ambiguous dependencies only through evidence-, confidence-, and review-bearing contracts.

Bootstrap MVP supports `.xlsx`; `.xls` is supported only through a maintained parser. Text-native PDF is in scope. Scanned PDF is accepted as a preserved source but must remain `VERIFICATION_REQUIRED` until a production-suitable OCR path exists. P6/MS Project formats, resource leveling, stochastic scheduling, 4D BIM, autonomous resequencing, and portfolio optimization are outside this milestone.

## Roadmap placement

Because the downstream runtime already exists, this is a corrective prerequisite track rather than a destructive renumbering of completed phases. Implement B0.1–B0.8 before Phase 13 hardening. Phase 12 remains open, and its representative operator sessions must include the BOQ-first workflow after the bootstrap UI is available.

