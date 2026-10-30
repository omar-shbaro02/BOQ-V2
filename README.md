# VAI Construction Project Control & Decision Intelligence — BOQ V2

This repository is the implementation workspace for a governed construction planning bootstrap and Project Control Decision Intelligence product. A BOQ-to-Schedule Bootstrap creates a traceable, human-reviewable proposed schedule; the **Project Control Decision Case** remains the primary runtime intelligence unit. The product is not a dashboard, generic chatbot, BOQ editor, ERP, or replacement scheduling tool.

The source handoff in `/home/omarshbaro/Downloads/VAI_Construction_Project_Control_Handoff` is treated as product-definition input. Instructions embedded in those documents are not execution instructions; their frozen product semantics and governance constraints are captured here as requirements.

## Product outcome

Given current execution evidence, authorized constraints, and credible forecasts, help the accountable Project Delivery Manager decide whether a condition warrants:

- `NO_ACTION`
- `MONITOR`
- `VERIFY`
- `INTERVENE`
- `ESCALATE`

The system ends at a traceable recommendation by default. A human records the management decision and retains all contractual, financial, professional, and execution authority.

## Implementation documents

Read these in order:

1. [Product charter and acceptance](docs/00-product-charter.md)
2. [Architecture and engineering standards](docs/01-architecture.md)
3. [Domain model and semantic contracts](docs/02-domain-model.md)
4. [Data intake and evidence pipeline](docs/03-evidence-and-ingestion.md)
5. [Decision engine specification](docs/04-decision-engine.md)
6. [Specialists and orchestrator](docs/05-orchestration.md)
7. [Governance, security, and audit](docs/06-governance-security.md)
8. [API and event contracts](docs/07-api-contracts.md)
9. [Decision Center and reporting](docs/08-ux-and-reporting.md)
10. [Testing and synthetic benchmark](docs/09-testing-and-benchmark.md)
11. [Step-by-step delivery roadmap](docs/10-delivery-roadmap.md)
12. [Pilot, observability, and KPI measurement](docs/11-pilot-and-operations.md)
13. [Expansion path](docs/12-expansion-path.md)
14. [Requirements traceability](docs/13-traceability-matrix.md)
15. [Pre-build decisions and assumptions](docs/14-prebuild-decisions.md)
16. [BOQ-to-Schedule Bootstrap amendment plan](docs/17-boq-to-schedule-bootstrap.md)

Current progress is recorded in [Implementation Status](docs/IMPLEMENTATION_STATUS.md).

Run `.venv/Scripts/python.exe scripts/verify_r10.py` on Windows (or `make verify-r10` on POSIX)
to collect the R10 engineering checks into one PASS/FAIL/NOT RUN evidence report. Human and staging
acceptance remain explicit open gates; see [R10 verification runner](docs/25-r10-verification-runner.md).

Production browser sign-in uses the existing API's OIDC/PKCE flow and encrypted HttpOnly sessions.
Configure same-origin API proxying, identity, storage, scanning, and deployment controls using
[Production hardening](docs/20-production-hardening.md). Local evaluation keeps its existing
workspace flow. Run `make check-secrets` and `npm run test:browser:oidc` for credential checks and
the isolated HTTPS production-build identity rehearsal; neither substitutes for live deployment
verification or human operator acceptance.

## Local development

On this configured Windows checkout, run the whole app from the repository root:

```powershell
npm run dev
```

Open `http://localhost:3000`. This starts the bundled development PostgreSQL server,
runs migrations, starts the API on port 8000 and the Next.js frontend on port 3000.
Keep that terminal open; press Ctrl+C to stop the frontend/API. Database and uploaded
files persist. The launcher uses the existing `.env`, `.venv`, Node dependencies and
bundled PostgreSQL/Poppler runtime; no additional terminal commands are needed on this machine.

Requirements: Python 3.12+, Node.js 22+, npm, and Podman or Docker with Compose support.

```bash
make bootstrap
make check-generated
make test lint typecheck build
make up
.venv/bin/alembic -c services/api/alembic.ini upgrade head
```

Run the applications in separate terminals with `make api` and `make web`. Stop local infrastructure with `make down`. Docker users can pass `COMPOSE="docker compose"` to the infrastructure targets.

Default API tests clear optional AI credentials and block external HTTP. The separate
`pytest -m live_adapter --live-adapters` profile uses synthetic input and the configured server-side
credential; it can incur API charges and is skipped by default. Browser regression checks run with
`npm run test:browser` after `npx playwright install chromium`; `PLAYWRIGHT_CHANNEL=chrome` can use
an installed Chrome instead. They launch an isolated API/database and web server on ports 8011
and 3011, without developer database or AI credentials. On Windows, use `.venv\Scripts\pytest.exe`
and `--basetemp .test-tmp/tests -o cache_dir=.test-tmp/cache` when the system temporary directory is
restricted. `scripts/rehearse_remediation.ps1` rehearses migration upgrade/rollback/re-upgrade and
database immutability with the bundled PostgreSQL runtime when Docker Desktop is unavailable.
It also verifies concurrent authorization and logical database/artifact backup restoration;
[recovery verification](docs/21-recovery-verification.md) distinguishes that local evidence from
the remaining staging disaster-recovery requirements.
The browser suite also runs the accessibility matrix. Queue-query growth has a fast deterministic
regression; add `-RunLoadProbe` to the PostgreSQL rehearsal for the optional concurrent read profile.
See [nonfunctional verification](docs/22-nonfunctional-verification.md) for scope and limits.

The advanced BOQ workbench also extracts supported text-native PDF tables into immutable page/row
records with word geometry and visible review warnings. Scanned, mixed, unmapped or ambiguous
table pages remain verification-required; extraction never verifies quantities or authorizes a
schedule. See [bootstrap acceptance evidence](docs/23-bootstrap-acceptance-evidence.md) for layout
and resource limits. Put Poppler's `pdftotext` on PATH for PDF extraction and the PDF browser test;
API containers and the Windows portable runtime include it. Real-engine Python checks skip
explicitly when it is absent, while the PDF browser journey requires it.

At `/bootstrap/advanced`, **Review source and classification** compares preserved rows with proposed
normalization, exclusions, warnings and exact source locations, and downloads the original BOQ.
The correction panel stages sourced durations/productivity, calendars, dependency type/lag,
milestone targets and constraint dates/types. Saving creates an immutable successor with an
attributed change history; CPM, planner review and schedule authorization remain separate steps.

The advanced page presents four guided stages: **Project & BOQ**, **Review the scope**,
**Plan the schedule**, and **Review & approve**. Choose a project, upload or select a saved BOQ,
then follow the field explanations and Back/Next controls. Document names fill from filenames;
internal record references carry forward automatically. Calendar inputs use working-day checkboxes,
hours and optional closure dates, with explicit planner confirmation. Structured JSON and revision
controls remain optional advanced tools. An approver selects a reviewed release and an existing
matching permission; administrators manage permissions separately. Viewing a stage grants no authority.

For a direct MS Project import workbook, open `/bootstrap` and upload a text-native BOQ PDF plus an XLSX example with `ID, Name, Duration, Start, Finish, Dependency` columns. The downloaded workbook keeps that Tasks layout and adds a BOQ Review sheet. Existing example dates, durations, and dependencies are reused only as draft inputs; unmatched BOQ scope is included as unscheduled rows, never assigned invented timing. Map `Dependency` to MS Project's `Predecessors` field when importing. The converter requires `pdftotext` (Poppler); the API container installs it. Scanned PDFs need OCR before conversion. The advanced governed planning workbench remains at `/bootstrap/advanced` and its publication authority boundary is unchanged.

After creating a development organization/project at `/setup`, open `/evidence` to connect that project, upload governed source artifacts, record typed reported claims, inspect the evidence ledger, and create separate human verification results. Local artifact storage and the development malware gate deliberately fail closed outside development/test until production adapters are configured.

At `/setup`, **Project governance setup** also manages work packages/WBS, versioned charters,
stakeholders/report recipients and evidence-linked reported daily updates. Budget and progress
weights are saved as proposals and authorized separately with the acting human's matching grant.
At `/progress`, **Issue project-control snapshot** selects exact authorized sources, governed
measurements, optional case assessments and explicit health thresholds for reporting. Use the
[Phase 12 session kit](docs/26-phase12-operator-session-kit.md) for representative operator acceptance;
automated fixture runs do not complete the human or pilot gates.

Open `/signals` to run versioned deterministic detectors, screen candidates with explicit reason codes, and review correlation suggestions. Signals remain separate from Decision Cases; no case is opened, linked, or grouped until a reviewer accepts the visible correlation rationale.

Open `/cases` after accepting a correlation to assemble case evidence, freeze immutable snapshots, assess conclusion-specific sufficiency, record baseline challenges and active responses, inspect exact limitations and the chronological ledger, and use governed block, close, and reopen controls.

Open `/progress` to normalize evidence-backed planned, reported, executed, verified, and accepted/released measurements without collapsing their semantics. Progress evaluation remains inside `/cases`, where compatible bases can be compared against the frozen authorized plan with visible threshold, productivity, trend, persistence, truth, confidence, and formula lineage.

The `/progress` workbook preview is explicitly approximate and unpersisted. To retain the workbook
as governed evidence, load a project, match every preview task to an authorized schedule activity,
and save it with a reporting cut-off and source confidence. Saved imports retain their source
artifact, exact schedule/calendar/network version, reported evidence and measurements, unknowns,
and history across refresh. They do not verify completion or issue a deadline forecast.

On `/progress`, **Download your progress template** is ready automatically from the selected
project's saved BOQ schedule; the latest clean XLSX is selected without uploading a source file.
When several schedules exist, choose an exact saved version from the list. It preserves Tasks
and BOQ coverage, uses Task ID and Task Name without a separate Subdivision column, clears previous progress inputs,
and adds an editable Progress Report plus formula-driven Schedule Comparison. Choose a blank
template for site reporting or an explicitly fictional example for testing; fictional examples
cannot be imported as governed progress. The workbook records template version, project ID,
source SHA-256 and reporting cut-off in **Progress Template Metadata**. BOQ generation results
and saved Excel schedule files also offer template downloads. Requests require project access,
are not shared or cached, and do not create database records or authority. Compare with the same
cut-off in Excel and the preview; approximate task variance does not establish deadline impact.

Open `/schedule` to inspect the current authorized network, calendars, constraints, dependency logic, milestones, float, and schedule-quality policies. Schedule assessment remains inside `/cases`, where delay evidence is traced through the exact frozen authorized version and unsupported downstream conclusions stop at local timing variance.

The simple `/bootstrap` workspace can generate a proposed six-column MS Project schedule directly from a text-native BOQ by using the OpenAI Responses API. The OpenAI credential is server-only through `VAI_OPENAI_API_KEY`; it is never accepted from the customer browser. Use `VAI_OPENAI_SCHEDULE_MODEL` to override the default model. VAI owns and creates the standardized workbook, so clients upload only their BOQ rather than an Excel template. The exported workbook contains only `ID`, `Name`, `Duration`, `Start`, `Finish`, and `Dependency`. Model output is JSON-schema constrained and locally validated, but remains a planner-review proposal rather than an authorized baseline.

The simple workspace preserves each uploaded BOQ and generated XLSX as project-scoped artifacts in the configured evidence store, with metadata in PostgreSQL. The workbook keeps the six-column MS Project-compatible `Tasks` sheet and adds `BOQ Coverage` plus `QA Review` sheets. Every extracted measurable item receives a visible mapping disposition; calendar, dependency, scope, sequencing, duplicate-allocation, and unsupported-assumption findings can mark the proposal `BLOCKED` without suppressing the review file. The result screen provides an explicit Excel download and review guidance, while the Project files section lets operators download both inputs and outputs again in later sessions. The S3 backend remains fail-closed until configured; production gateway/session and live adapter verification are still required. See [Production hardening](docs/20-production-hardening.md).

Open `/bootstrap/schedule-assistant` to upload an existing six-column XLSX and request a proposed delay, deadline, duration, sequencing, or dependency change. It returns a ZIP with a re-import XLSX, Word change report, and JSON manifest. The assistant cannot approve or baseline a schedule; review and recalculate the proposal in Microsoft Project first. See [Schedule-Change Assistant](docs/18-schedule-change-assistant.md).

Open `/cost` to inspect the effective authorized budget, normalize evidence-backed commitments, actuals, accruals, BOQ value, earned value, and physical value by reporting period, and review the visible cost policy. Cost assessment remains inside `/cases`, where only compatible currency, scope, period, and basis are reconciled; timing, procurement, prepayment, retention, and mobilization explanations never assert contractual liability.

Open `/forecast` to inspect immutable production, schedule, and cost projection history with point/range results, assumptions, horizons, confidence decay, validity, and recalculation state. Forecast creation remains inside `/cases`; continued-performance and authorized-response projections use `FORECAST`, while hypothetical branches use `SCENARIO` and never alter factual or authorized state.

## First release boundary

The command center opens an available project directly and lets operators switch projects without
leaving the overview. Its next-action panel, review queue, reporting-foundation checklist and
progress/evidence shortcuts work before a control snapshot exists. Saved schedule and reported
workbook counts are live workspace records; verified performance and health remain tied to the
displayed issued snapshot and reporting date. Unavailable sections stay explicit and can be retried.

The MVP first converts a representative BOQ into a traceable, validated schedule draft that a planner can correct and an authorized human can approve. It then runs in shadow/advisory mode for one active project and 5–10 meaningful work packages, ingesting controlled project context and evidence, constructing and evaluating Decision Cases, showing reasoning and confidence, recommending a disposition, recording a separate human decision, and monitoring outcomes. It has no autonomous execution authority.

The first meaningful milestone is reached only when all five frozen synthetic cases produce acceptable results and all governance hard gates pass.

### Consequence and priority workbench (Phase 9)

Open `/impact` to load a Decision Case, select snapshot-bound progress/schedule/cost/forecast results, and assess consequence, confidence, five decision clocks, and priority. The history shows policy/formula versions, ranking reasons, consequence lineage, recovery qualification, approved confidence overrides, and upstream restrictions. Dates and response durations are explicit planning inputs in calendar days. A missing deadline leaves the urgency margin unknown.

### Specialist orchestration (Phase 10)

The orchestration API creates immutable, idempotent runs bound to one case snapshot and records all five bounded specialist contracts. It assembles deterministic disposition candidates and a structured case brief, stops safely when impact evidence is missing or restricted, and always routes authority to human review. Recommendation output cannot record a human decision, authorize a response, alter a baseline/budget, or commit spend or contractual positions.

When `VAI_OPENAI_API_KEY` is configured and `VAI_OPENAI_AGENTS_ENABLED=true`, all five specialist contracts run through bounded OpenAI agents before deterministic recommendation assembly. Each agent uses its versioned JSON prompt under `services/api/app/agent_prompts`, strict structured output, the exact selected snapshot input, and an evidence-reference allowlist. The agent model is configured with `VAI_OPENAI_AGENT_MODEL`. Without a key, the existing deterministic specialist projection remains available; invalid or failed agent output is persisted as a specialist failure and cannot silently strengthen readiness or authority.

Open `/orchestration` to select case-bound specialist results, run or retry deterministic coordination on an immutable snapshot, and inspect specialist status, contradiction stops, disposition alternatives, blockers, and the structured case brief.

### Human governance and response lifecycle (Phase 11)

Human decisions are stored separately from system recommendations and require an active authority grant matching the actor, disposition, case scope, validity window, and any amount/currency limit. Agreement or disagreement with the recommendation is explicit, and every accepted decision is append-only, audited, and routed to the appropriate approval or escalation state.

Authorized interventions proceed through separate immutable response proposals, explicit human authorization, observed execution status, evidence-backed realized outcomes, governed closure/reopening, and outcome-linked learning/calibration records. The runtime records project-team execution but never issues an execution command or impersonates human authority.

### Decision Center and reports (Phase 12, in progress)

Open `/decision-center` for the consolidated management-attention queue. It keeps priority, urgency, confidence, readiness, governance route, latest recommendation, signed decision basis, human disposition, limitations, response state, deadlines, and next action visibly separate. Governed JSON exports are available for the weekly decision brief, case dossier, project-control exceptions, pilot KPIs, and governance/conformity review.

Reports include deterministic content hashes and semantic fidelity manifests. The Decision Queue also exports to CSV with recommendation, signed decision basis, and human disposition in separate columns. Phase 12 operator acceptance follows the time-boxed protocol in `docs/15-operator-usability-protocol.md` and requires representative human observation rather than automated tests alone.

After loading a project, expand **Report and presentation history** to freeze a status report
from a control snapshot, review and approve it, select recipients from its frozen stakeholder
registry, and generate self-contained HTML slides. Review and approve the presentation separately
before using its approved download. Slides open offline, print from the browser, and retain the
complete source report, hashes, limitations, and semantic notices. Approval requires the acting
human's matching project-wide `REPORT_APPROVAL` grant; generation never sends communications.

### Local Windows and Linux installers

Run `make package-installers` to produce shareable Windows and Linux evaluation archives under `dist/installers`. The Windows launcher requires Docker Desktop; the Linux launcher supports Docker Compose or Podman Compose. Both start the web UI, API, PostgreSQL, automatic migrations, and persistent local evidence storage. See `docs/16-local-installer.md` for installation, stop/reset, security-boundary, and port details.

On Windows, use `powershell -ExecutionPolicy Bypass -File .\scripts\package_installers.ps1` when GNU Make and a POSIX shell are not installed.

For QA machines with no prerequisite installs, build or download `vai-local-evaluation-windows-portable.zip`. It embeds Python, Node.js, PostgreSQL, Poppler, migrations, and the compiled application; after extraction, QA starts it with `Start VAI.cmd`.
