# BOQ bootstrap acceptance evidence

Audit date: 2026-10-26. This is R10 technical prerequisite evidence. Phase 12 and Amendment A
human acceptance remain open; no pilot authorization or Phase 13 entry is asserted.

## Reproduce the API evidence

```powershell
.\.venv\Scripts\pytest.exe services/api/tests/integration/test_evidence_api.py --basetemp .test-tmp/bs-audit -p no:cacheprovider --tb=short
```

The current checkout passes 37 cases in this module. The matrix below identifies executable
tests, rather than treating the historical 95-test result as current verification. All named
tests are in `services/api/tests/integration/test_evidence_api.py`.

| Gate | Executable evidence | Boundary still requiring acceptance |
| --- | --- | --- |
| BS-001 | `test_boq_source_preserves_workbook_structure_rows_and_revision_lineage` retains all twelve nonempty rows, all ten classifications and unresolved rows; summaries, provisional and material-only scope do not become execution tasks. | Representative planner reviews classifications and completeness against the source workbook. |
| BS-002 | The source/lineage test and `test_bootstrap_real_xlsx_to_authorized_schedule_and_revision_isolation` map two concrete lines to one execution activity, preserve both references, and calculate four days from 200 m3 / 50 m3 per working day. | Planner confirms grouping and productivity are defensible for the intended project. |
| BS-003 | The source/lineage test retains explicit and generated procurement prerequisites, relation, lag, basis, confidence and review state; the `missing_prerequisite` validation case blocks review. | Planner reviews construction and procurement prerequisites, including generated proposals. |
| BS-004 | The source/lineage test preserves proposed/unauthorized milestones and constraints; `constraint`, `milestone`, `prior_milestone` and `missing_feeder` validation cases block review. | Human confirms contractual sources, dates, feeders and separate approval route. |
| BS-005 | The source/lineage test retains six unresolved durations/assumptions; `missing_duration` and `invalid_duration` validation cases block review. | Planner supplies and explains duration, productivity, crew/calendar assumptions where applicable. |
| BS-006 | `test_bootstrap_cpm_review_authority_and_exports` exercises FS, SS, FF and SF relationships, late-date constraints, floats, replay and payload mismatch; validation cases cover cycles, fractional lags, negative float, weak critical inputs and horizon limits. | Representative planner reviews a credible project network and the meaning of criticality/float. This is not an independent external scheduler comparison. |
| BS-007 | The source/lineage test retains location/grouping and a visibly assumed unreviewed calendar; the valid CPM test skips a supplied holiday and weekend, while `calendar` blocks an unreviewed calendar. | Planner confirms supplied location allocation and actual working calendar. No unsupported spatial decomposition or crew is inferred. |
| BS-008 | The real-XLSX test imports added scope, freezes its delta, rejects an unapproved prior release and proves the exact current authorized context remains unchanged. | Operator interprets mapping/activity/available schedule effects and separately reviews any replacement. |
| BS-009 | `test_bootstrap_dependency_cycle_blocks_review` explicitly tests empty/duplicate schedules, absent traceability/durations, missing feeders and other blockers. `test_boq_commercial_arithmetic_and_duplicate_findings_are_visible` blocks commercial errors and duplicate primary allocation. | Planner demonstrates correction and recalculation without bypassing blockers. Additional project-specific validation is not inferred from these fixtures. |
| BS-010 | Valid CPM cases record actor-bound field edits, deny missing/amount-bounded authority, require a separate active exact grant, reject duplicate approval and stale review, and export JSON/CSV/XLSX with separate authorization metadata. The real-XLSX test publishes the typed current schedule consumed by existing control services. | Representative humans complete their own planner/authority tasks and explain the exported semantics. |

## Corrections found by this audit

Calculation version `1.1.0` applies fixed-start, fixed-finish and finish-no-later-than constraints
to the backward pass. Previously an activity could show float extending beyond its explicit
constraint. A three-day task alongside a two-day SS successor illustrates the defect: when the
successor must finish on day two, its float is zero, not one day.

Pre-start milestone deadlines now count the actual working days before project start; every such
deadline previously collapsed to index -1. Free float is capped by total available float, including
the project-finish boundary for SF relationships. Negative total float remains visible and blocks
review. New results carry the new version in their input hash. Existing immutable calculations,
releases, approvals and authorized contexts are not rewritten.

The blocker fixture now uses distinct work packages except when deliberately testing duplicate
scheduling or a within-package prerequisite. This avoids incidental duplicate-scheduling failures
masking the intended validation scenario.

## Browser workflow evidence

```powershell
$env:PLAYWRIGHT_CHANNEL='chrome' # Optional installed-browser alternative.
npm.cmd run test:browser -- --grep 'advanced BOQ corrections'
```

The named journey in `tests/browser/critical-paths.spec.ts` uses a separate synthetic organization
and project. It uploads a real XLSX, normalizes and groups two BOQ lines, shows a missing-duration
blocker and disabled review, creates a successor reviewed version, supplies project productivity,
and recalculates four working days with an explicit holiday. It stages an actor-attributed name
edit, records planner review, observes missing-grant denial, creates the exact human grant and
authorizes separately. The downloaded JSON retains the edited name, release state and exact
authorized-context reference. Importing added BOQ scope produces a delta while preserving that
current context; sources/releases survive page reload. The focused journey passes.

The fixture files are generated by `scripts/e2e_api.py` under ignored `.test-tmp/`; browser tests
use a disposable database and no paid AI credentials. This establishes workflow availability,
not participant understanding, realistic construction sequencing or human acceptance. The ordinary
suite also exercises the separate simple-PDF scheduler-failure/persistence path.

## Remaining implementation and acceptance boundaries

The advanced governed workflow is `/bootstrap/advanced`. The simple PDF/AI proposal workflow at
`/bootstrap` is a separate entry path and cannot stand in for advanced publication acceptance.
Advanced text-native PDF tables now use `VAI_BOQ_PDF_TEXT` version 1.0.0 and the same immutable
source/row/normalization boundary as workbooks. Each page must expose an unambiguous supported
English description/quantity header with at least three distinct recognized columns. Page-local
columns preserve empty cells; every text row retains page, row, word bounding boxes in PDF points,
original text, extraction confidence and review warnings. Repeated or differing layouts are never
silently treated as a verified source. Normalizer version 1.2.0 caps classification confidence at
MEDIUM for these proposed 0.75-confidence extractions and preserves the original row text.

Blank/scanned pages, mixed text/scanned documents, missing supported headers and multiple different
table layouts on a page retain `VERIFICATION_REQUIRED` and cannot be normalized. Missing Poppler,
malformed documents, timeout and resource errors preserve the source with a visible extraction
failure. OCR, arbitrary/multiline table reconstruction and non-English header mapping remain
unsupported. Even successfully extracted tables require visual completeness review; text-layer
presence does not prove that image-only or omitted scope is absent.

The parser limits input to 25 MiB, output/error files to 16 MiB each, elapsed extraction to thirty
seconds, parsed pages to 200 and words to 100,000; it terminates and waits for a failed/over-limit
child and removes temporary files. XML entities and external references are denied. Page/word limits
reject the complete extraction rather than truncating it. Polling file sizes is not an OS-level
memory/disk sandbox; a maintained Poppler runtime and deployment resource isolation remain required.

`test_boq_pdf.py` and `integration/test_boq_pdf_api.py` provide 23 focused tests, including real
Poppler extraction of a rendered two-page fixture, word/cell/page lineage, mixed-page denial,
unavailable-engine handling, entity/geometry/resource denial, process cleanup, tenant denial,
idempotent replay and zero schedule authorization. The browser journey now covers both XLSX and
text-native PDF inputs through corrected CPM, separate authorization, export and revision isolation.
Poppler's `pdftotext` must be on PATH for the real-engine tests and PDF browser journey. Both API and
browser CI jobs now install it; remote CI has not been executed. The existing API container and
portable Windows runtime already supply Poppler.

Inline reviewed edits cover names, responsible owners and the API's permitted progress-basis field.
The advanced source-review panel now shows retained raw cells/text beside normalized values,
classification/rule, confidence, review status, exclusions and warnings. It exposes page/sheet/row,
original artifact download, parser/hash, word-region and exact line references, unmapped values,
filter/search and bounded 25-row pages. Stored correction history supplies draft references after
reload. Reconnecting clears previous project drafts, calculations, staged edits and reference defaults.

Typed material-correction forms now stage explicit durations, sourced productivity (removing the
execution override explicitly), reviewed calendars/holidays, and explicit/template relationship
type/lag corrections. A human command creates a successor structure/draft, binds original/revised
input fields and previous durations to actor/time/reason, and remaps copied logic to new activity
IDs. Missing assumed-calendar review stays unresolved. Corrections do not create CPM or authority;
the UI clears prior calculation/review defaults and requires recalculation and separate approval.
The typed correction panel also edits milestone targets with a supplied source reference and
constraint dates/types with a supplied basis; these remain proposed and unauthorized. The API
accepts complete typed logic for other milestone/constraint fields and relationship changes.
Superseded planning structures cannot produce a fresh review or approve an earlier pending release,
even with an otherwise valid grant. Prior approved contexts and immutable action replays remain intact.

`integration/test_bootstrap_corrections.py` covers replay, mismatches, stale versions, atomic denial,
service/tenant/read-only denial, unknown input preservation, assumption provenance, dependency/
milestone/constraint remapping and preservation of an already authorized schedule. The real
PostgreSQL rehearsal runs the same source-to-publication path and a two-writer correction race,
with one success and one stale conflict, plus corrected-history UPDATE/DELETE denial and recovery.
That path exposed/fixed source/normalization/generation parent insertion ordering that SQLite had
not enforced. Finalized parents are inserted before dependent rows without updating append-only
history. No migration was added; head remains 0031_audit_append_only.

The browser path now includes a procurement fixture with explicit duration, productivity, calendar
and dependency-lag edits, as well as source review/download/filtering and history across reload.
Automated accessibility/reflow checks include loaded source/correction controls at desktop/320px.
B0.6–B0.8 and representative human acceptance remain open as recorded in the amendment plan.

The connected-scenario audit subsequently found two prerequisites: bootstrap review had no explicit
controlled-object/planned-quantity input, and baseline approval had no distinct BASELINE context.
Typed review control inputs now provide sourced mappings and explicit planned points without
interpolation. Baseline approval creates separate baseline/current contexts; later current approval
preserves the formally approved baseline. An unapproved baseline source cannot replace that link.
Review remains proposed and approval requires its exact grant. The advanced review screen stages
these controls, and API tests record an exact authorized planned measurement while rejecting a
changed denominator. Approval/export retains BOQ trace and server-owned lineage.

`test_bootstrap_controls.py` covers the API path and denial/replay/supersession semantics. It also
runs in real PostgreSQL under migration `0032_context_history_guard`: baseline/current/superseded
payloads and approval provenance reject SQL mutations, while legitimate supersession succeeds.
The upgrade/downgrade/re-upgrade and full logical database/artifact restoration pass. This closes
technical prerequisites for acceptance steps 7–8; it does not prove the complete connected
17-step scenario or supply human acceptance. Earlier statements that no migration was needed
refer to the earlier source/material-correction slice; current head is 0032.

The complete connected 17-step public-API scenario now passes on SQLite and migrated PostgreSQL;
see [connected acceptance evidence](24-connected-acceptance-evidence.md) for the exact step matrix,
commands, manifests, cross-artifact checks and limitations. Its records/artifacts are included in
the local logical recovery. This supersedes the earlier prerequisite-only resume point above;
it does not replace representative operator or deployed-provider acceptance.

No completed representative-session record or actual staging application URL was found in `docs/`
during this audit. `15-operator-usability-protocol.md` specifies sessions; it is not their result.
`20-production-hardening.md` contains configuration placeholders and explicitly outstanding live
acceptance. Preserve those distinctions when collecting the remaining evidence.

Resume with the representative planner and Project Delivery Manager sessions under
[the operator protocol](15-operator-usability-protocol.md), the unsupported PDF layout boundaries,
and live-provider, staging load/soak and disaster-recovery acceptance in
documents 20–22. Record participant observations and accountable deployment results before changing
release acceptance. Do not infer acceptance from an automated actor named as a human in a synthetic
fixture.
