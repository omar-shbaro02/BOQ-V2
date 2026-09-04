# ADR-001 — Start with a Modular Monolith

- Status: accepted for bootstrap
- Date: 2026-09-04

## Context

The product needs strong semantic, transactional, authority, and audit boundaries before it needs independent service scaling. The initial pilot is one project and 5–10 work packages.

## Decision

Use a modular monolith with a Next.js TypeScript web application, FastAPI Python API/decision runtime, PostgreSQL persistence, S3-compatible evidence storage, OIDC identity, and OpenTelemetry-compatible telemetry. Keep domain modules and versioned contracts explicit so components can be separated later.

Deterministic rules own arithmetic, lifecycle, semantics, permissions, and governance. Optional AI operates behind bounded, schema-validated specialist adapters.

## Consequences

- Initial development, local operation, transactions, and audit are simpler.
- Python supports future forecast/data workloads; TypeScript supports the operator interface.
- Shared schemas require generation and compatibility checks across languages.
- Deployment contains multiple runtimes even though the business application remains one logical unit.
- Service extraction is deferred until measured scaling or organizational needs justify it.

