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

## Local development

Requirements: Python 3.12+, Node.js 22+, npm, and Podman or Docker with Compose support.

```bash
make bootstrap
make check-generated
make test lint typecheck build
make up
.venv/bin/alembic -c services/api/alembic.ini upgrade head
```

Run the applications in separate terminals with `make api` and `make web`. Stop local infrastructure with `make down`. Docker users can pass `COMPOSE="docker compose"` to the infrastructure targets.

For a direct MS Project import workbook, open `/bootstrap` and upload a text-native BOQ PDF plus an XLSX example with `ID, Name, Duration, Start, Finish, Dependency` columns. The downloaded workbook keeps that Tasks layout and adds a BOQ Review sheet. Existing example dates, durations, and dependencies are reused only as draft inputs; unmatched BOQ scope is included as unscheduled rows, never assigned invented timing. Map `Dependency` to MS Project's `Predecessors` field when importing. The converter requires `pdftotext` (Poppler); the API container installs it. Scanned PDFs need OCR before conversion. The advanced governed planning workbench remains at `/bootstrap/advanced` and its publication authority boundary is unchanged.

After creating a development organization/project at `/setup`, open `/evidence` to connect that project, upload governed source artifacts, record typed reported claims, inspect the evidence ledger, and create separate human verification results. Local artifact storage and the development malware gate deliberately fail closed outside development/test until production adapters are configured.

Open `/signals` to run versioned deterministic detectors, screen candidates with explicit reason codes, and review correlation suggestions. Signals remain separate from Decision Cases; no case is opened, linked, or grouped until a reviewer accepts the visible correlation rationale.

Open `/cases` after accepting a correlation to assemble case evidence, freeze immutable snapshots, assess conclusion-specific sufficiency, record baseline challenges and active responses, inspect exact limitations and the chronological ledger, and use governed block, close, and reopen controls.

Open `/progress` to normalize evidence-backed planned, reported, executed, verified, and accepted/released measurements without collapsing their semantics. Progress evaluation remains inside `/cases`, where compatible bases can be compared against the frozen authorized plan with visible threshold, productivity, trend, persistence, truth, confidence, and formula lineage.

Open `/schedule` to inspect the current authorized network, calendars, constraints, dependency logic, milestones, float, and schedule-quality policies. Schedule assessment remains inside `/cases`, where delay evidence is traced through the exact frozen authorized version and unsupported downstream conclusions stop at local timing variance.

The simple `/bootstrap` workspace can generate a proposed six-column MS Project schedule directly from a text-native BOQ by using the OpenAI Responses API. The OpenAI credential is server-only through `VAI_OPENAI_API_KEY`; it is never accepted from the customer browser. Use `VAI_OPENAI_SCHEDULE_MODEL` to override the default model. VAI owns and creates the standardized workbook, so clients upload only their BOQ rather than an Excel template. The exported workbook contains only `ID`, `Name`, `Duration`, `Start`, `Finish`, and `Dependency`. Model output is JSON-schema constrained and locally validated, but remains a planner-review proposal rather than an authorized baseline.

Open `/cost` to inspect the effective authorized budget, normalize evidence-backed commitments, actuals, accruals, BOQ value, earned value, and physical value by reporting period, and review the visible cost policy. Cost assessment remains inside `/cases`, where only compatible currency, scope, period, and basis are reconciled; timing, procurement, prepayment, retention, and mobilization explanations never assert contractual liability.

Open `/forecast` to inspect immutable production, schedule, and cost projection history with point/range results, assumptions, horizons, confidence decay, validity, and recalculation state. Forecast creation remains inside `/cases`; continued-performance and authorized-response projections use `FORECAST`, while hypothetical branches use `SCENARIO` and never alter factual or authorized state.

## First release boundary

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

### Local Windows and Linux installers

Run `make package-installers` to produce shareable Windows and Linux evaluation archives under `dist/installers`. The Windows launcher requires Docker Desktop; the Linux launcher supports Docker Compose or Podman Compose. Both start the web UI, API, PostgreSQL, automatic migrations, and persistent local evidence storage. See `docs/16-local-installer.md` for installation, stop/reset, security-boundary, and port details.
