# 14 — Pre-Build Decisions and Assumption Register

The handoff freezes product meaning but intentionally leaves engineering choices and project-specific policies open. These decisions must be made explicitly; implementation must not conceal them inside code, prompts, or UI defaults.

## 1. Decisions already proposed by this plan

| Decision | Proposed default | Change mechanism |
|---|---|---|
| Delivery architecture | modular monolith | ADR before bootstrap changes |
| Web/API/data stack | Next.js, FastAPI, PostgreSQL | ADR with migration/skills impact |
| Analytical strategy | deterministic-first; governed optional AI | architecture and model-risk review |
| MVP autonomy | A0–A2 only; no execution | product/governance approval |
| Initial tenancy | organization and project scoped | security ADR |
| Stored dispositions | `NO_ACTION`, `MONITOR`, `VERIFY`, `INTERVENE`, `ESCALATE` | frozen product review |
| “Verify urgently” | `VERIFY` plus urgency attribute | schema contract |
| Times and arithmetic | UTC storage, project calendar display, decimal money/quantities | engineering standard |

## 2. Required project/product decisions before relevant phase

| Decision | Needed by | Owner | Safe behavior until decided |
|---|---|---|---|
| Pilot project, packages, reporting cadence, timezone/calendars | Phase 1 | pilot sponsor + PM | use synthetic project only |
| Identity provider and organization/user source | Phase 1 | security/product | local development identity only; no live data |
| Delivery model and authority hierarchy | Phase 1 | accountable PM/governance | block protected workflows |
| Source file/API formats and field mappings | Phase 2 | project controls/data owner | manual structured entry and rejected ambiguous imports |
| Evidence verification methods per evidence class | Phase 2 | project controls/quality authority | retain as reported claim |
| Source reliability policy and review cadence | Phase 2 | governance/data owner | neutral prior; show limitation |
| Signal thresholds and trend-persistence windows | Phase 3/5 | PM + project controls | create candidates for review, do not auto-strengthen disposition |
| Schedule-quality minimum and dependency rules | Phase 6 | planner/project controls | limit or block schedule conclusion |
| Cost recognition, earned-value/BOQ mapping, currency rules | Phase 7 | commercial controller | omit unsupported cost conclusion |
| Forecast methods, horizons, ranges, expiry triggers | Phase 8 | project controls | no forecast beyond supported deterministic basis |
| Materiality, consequence, confidence, priority bands | Phase 9 | accountable PM/sponsor | transparent conservative policy marked provisional |
| Escalation thresholds, response/service deadlines | Phase 11 | authority owner | human review required |
| KPI formulas, ground truth, counterfactual and adjudication | before pilot | sponsor + evaluator | collect timestamps but do not claim measured value |
| Data classification, residency, retention, recovery objectives | before live data | security/legal/sponsor | synthetic/non-sensitive data only |
| AI provider, model policy, retention and redaction | Phase 10 if used | security/product | deterministic/manual path only |

## 3. Methodology gaps that must not be guessed

The source record does not prescribe numerical thresholds, weights, confidence formulae, source-precedence rules, intervention cost/benefit logic, project calendars, evidence expiry, KPI counterfactuals, or pilot acceptance targets. These are configurable policies or product decisions. Every chosen value needs an owner, rationale, version, effective date, test, and replay-impact statement.

The source benchmark defines five outcomes but not full machine-readable fixtures. Fixture construction therefore requires product-owner review to ensure added numbers do not accidentally redefine the intended cases. Freeze fixture v1 before engine tuning to prevent answer leakage.

## 4. Decision record template

For every ADR or policy decision record:

- ID, title, status, owner, date, and effective version;
- context and frozen requirements affected;
- options considered and decision;
- security, governance, data, operator, and benchmark consequences;
- migration/replay/backward-compatibility impact;
- validation and rollback/replacement path;
- linked implementation and tests.

## 5. Start-build rule

Phase 0 may start using the proposed technical defaults. Live-project ingestion cannot start until identity, authority, data classification, retention, source mapping, and authorized-context ownership are decided. Decision performance cannot be claimed until benchmark fixtures and KPI/adjudication definitions are frozen independently of engine tuning.

