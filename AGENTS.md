# Repository Agent Instructions

## Start here

Before changing code:

1. Read `README.md` for the product boundary and local workflow.
2. Read `docs/IMPLEMENTATION_STATUS.md` for completed work, current verification evidence, and the exact resume point.
3. Read the relevant phase in `docs/10-delivery-roadmap.md` and the domain documents it references.
4. Inspect `git status`, `git diff`, and recent commits. Preserve existing user changes and do not redo completed phases.

The implementation status is the handoff source of truth. Earlier phase verification entries are historical evidence, not proof that a new checkout currently passes.

## Current delivery position

- Phases 0 through 10 are complete.
- Phase 11, Human governance and response lifecycle, is in progress.
- The first Phase 11 slice is complete: immutable human decisions, exact authority-grant validation, governance routing, audit/ledger provenance, API history, migration `0013_human_decisions`, and focused/live migration verification.
- Resume with response proposal/simulation, explicit authorization linkage, execution-status observation, and outcome evidence. Then implement close/reopen integration and learning/calibration records.
- Phases 12 through 14 remain after Phase 11.

Update `docs/IMPLEMENTATION_STATUS.md` whenever a meaningful slice is completed. Keep its remaining-phase count and next implementation order accurate.

## Product and governance invariants

- A Decision Case is the primary intelligence unit; this is not a generic dashboard, chatbot, ERP, BOQ editor, or replacement scheduling tool.
- Keep evidence, derived analysis, forecasts/scenarios, recommendations, human decisions, authorization, and execution state semantically separate.
- Never silently upgrade reported or derived information into verified fact or authorized state.
- System recommendations never constitute human decisions or execution authority.
- Human decisions require explicit actor identity and matching active authority grants. Approval, escalation, spend, contractual positions, baseline changes, and response execution must fail closed without authority.
- Preserve immutable history, exact source/version/snapshot lineage, idempotency, optimistic version checks, audit events, and case-ledger provenance.
- Unresolved material contradictions and insufficient or weak evidence must restrict conclusions visibly; do not invent missing values or infer unsupported causation, entitlement, or liability.
- Keep deterministic contracts and validation authoritative. Optional AI narrative output must pass fidelity validation and may not cross specialist or authority boundaries.
- Production identity, object storage, and malware scanning remain deliberately fail-closed until their external adapters are selected.

## Generated contracts and migrations

- `packages/contracts/source/taxonomies.json` is the canonical taxonomy source.
- Regenerate Python and TypeScript outputs with `make generate`; do not hand-edit generated taxonomy files.
- Run `make check-generated` after taxonomy changes.
- Add a reversible Alembic revision for persistent schema changes. Preserve append-only database protections for immutable/governed records.
- Use `.venv/bin/alembic -c services/api/alembic.ini upgrade head` for the local database. Any claimed migration completion must include an appropriate upgrade/downgrade/re-upgrade rehearsal, not only offline SQL generation.

## Validation

Use the repository-managed toolchains and run checks proportional to the change. Before calling a phase or substantial slice complete, run the full gate when dependencies are available:

```bash
make check-generated
make test
make lint
make typecheck
make build
```

For database work, also start PostgreSQL with `make up`, exercise the migration rehearsal and relevant API/database behavior, then stop it with `make down`. Never report a check as passing unless it ran successfully in the current checkout; document unavailable checks and their reason.

## Change discipline

- Keep changes within the active roadmap phase unless a prerequisite correction is required.
- Add regression tests for semantic gates, tenant and authority denial, idempotency mismatch, stale versions, lineage, and append-only behavior where applicable.
- Preserve backward compatibility unless the status/roadmap explicitly authorizes a breaking contract change.
- Do not commit secrets, `.env` files, local artifacts, credential caches, or `~/.codex/auth.json`.
- Do not discard or overwrite unrelated working-tree changes.
