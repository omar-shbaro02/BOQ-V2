# VAI Construction Project Control & Decision Intelligence — BOQ V2

This repository is the implementation workspace for a governed construction Project Control and Decision Intelligence product. Its primary intelligence unit is the **Project Control Decision Case**, not a dashboard, generic chatbot, BOQ editor, ERP, or replacement scheduling tool.

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

After creating a development organization/project at `/setup`, open `/evidence` to connect that project, upload governed source artifacts, record typed reported claims, inspect the evidence ledger, and create separate human verification results. Local artifact storage and the development malware gate deliberately fail closed outside development/test until production adapters are configured.

## First release boundary

The MVP runs in shadow/advisory mode for one active project and 5–10 meaningful work packages. It ingests controlled project context and evidence, constructs and evaluates Decision Cases, shows reasoning and confidence, recommends a disposition, records a separate human decision, and monitors outcomes. It has no autonomous execution authority.

The first meaningful milestone is reached only when all five frozen synthetic cases produce acceptable results and all governance hard gates pass.
