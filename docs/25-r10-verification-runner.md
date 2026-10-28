# Automated R10 verification runner

The runner collects current engineering evidence for R10. Each check is **PASS**, **FAIL** or
**NOT RUN**. It never promotes local/synthetic results into human, deployed-provider or pilot
acceptance. It runs existing repository checks; it does not provision resources or publish a site.

## Run

From the repository root, with the repository Python/Node dependencies installed:

```powershell
.venv/Scripts/python.exe scripts/verify_r10.py
```

On POSIX hosts, use `.venv/bin/python scripts/verify_r10.py` or `make verify-r10`.
`npm run verify:r10` also works when `python` is on PATH; child Python checks still use `.venv`.

The default run executes:

| Check | Evidence and acceptance scope |
| --- | --- |
| Generated contracts and credential scan | Repository consistency and high-confidence secret patterns. |
| Full Python suite | Domain/adapter, tenant, authority, idempotency, lineage, archive limits, connected 17-step scenario and queue-query regressions. JUnit retains counts and named skips. |
| Python lint, format and compilation | Repository-managed Ruff and Python checks. |
| Web lint, types and build | Existing Node workspace commands. A normal build follows the special OIDC build. |
| Full browser suite | All standard journeys, guided navigation and automated accessibility. JSON counts and failure traces are retained. |
| HTTPS identity | Synthetic issuer and production build over loopback TLS, including proxy/body fidelity, cookie/CSRF/sign-out and mobile checks. This does not test an actual identity provider. |
| PostgreSQL rehearsal and local load | Windows portable runtime: head upgrade, 0032 → 0031 → 0032, migrated API, authority/correction races, immutable history, connected scenario, logical database/artifact recovery and the 96-read local queue probe. |

The runner starts its own disposable browser services, waits for both API and web readiness,
then closes their process trees. It checks required ports before starting and never terminates an
unrelated service to claim those ports. Browser services use 8011/3011; HTTPS uses 8012/3012/3013;
PostgreSQL uses 55441. Do not run another browser harness against those ports simultaneously.

Default checks suppress optional AI credentials and external PostgreSQL test variables. The only
ordinary Python skips allowed are the separately executed isolated PostgreSQL profile and the
explicit live-AI profile. Missing real-PDF coverage is not silently accepted as a full suite pass.
On Windows, the bundled Poppler path and installed Chrome are detected when available. Otherwise
put `pdftotext` on PATH and install Playwright Chromium or set `PLAYWRIGHT_CHANNEL` explicitly.

The default Windows PostgreSQL runtime is
`dist/portable-smoke-final/vai-local-evaluation-windows-portable/runtime/postgresql/bin`.
Use `--postgres-bin PATH` to select another compatible portable runtime. The wrapper now accepts
absolute/relative runtime paths and writes JUnit plus stable evidence into the runner's directory.
PostgreSQL initializes a fresh loopback-only test cluster and stops it in `finally`; the runner
also attempts to stop that exact owned cluster if the wrapper is interrupted or times out.
On other hosts, this wrapper remains NOT RUN; documents 21–22 describe the separate database checks.

## Optional checks and exit codes

```powershell
.venv/Scripts/python.exe scripts/verify_r10.py --online-audits
.venv/Scripts/python.exe scripts/verify_r10.py --skip-browser --skip-postgres
.venv/Scripts/python.exe scripts/verify_r10.py --require-complete
```

`--online-audits` queries advisory services using `npm audit --audit-level=high` and
`.venv`'s installed `pip_audit` against the pinned Python requirements. The Python command fails
on any advisory; npm uses the repository CI's high/critical blocking threshold. It does not install
missing audit tools. A requested unavailable tool is NOT RUN and produces an incomplete exit.

`--live-ai` separately opts into the potentially paid synthetic live-AI boundary smoke test and
requires `VAI_OPENAI_API_KEY` in the process environment. It does not enable live S3, ClamAV, identity
or deployment probes. Without explicit opt-in, advisory-network and live-AI checks remain NOT RUN.

Explicit skip flags leave the corresponding requirements visible as NOT RUN and deselect them
from the selected-check exit calculation. Do not describe such a run as complete local coverage.

- Exit **0**: all selected automated checks passed. This is not R10 acceptance.
- Exit **1**: at least one selected check failed, timed out or lacked valid required evidence.
- Exit **2**: a selected prerequisite/check was unavailable; or `--require-complete` was used while
  overall R10 acceptance remains incomplete.

`--require-complete` is intended for a release gate. This local runner deliberately leaves the
human and staging gates open, so a clean local run still returns 2 in that mode. No external
attestation can be supplied to turn those requirements green through this command.

## Report and limitations

Every invocation creates a new ignored `.test-tmp/r10-<UTC timestamp>-<unique suffix>/` directory:

- `report.md`: readable check table, explicit reasons for NOT RUN/FAIL, and log links;
- `report.json`: scope, selection, timestamps, durations, commands, test counts/skips and file hashes;
- command logs, browser JSON/traces, JUnit and PostgreSQL scenario/recovery/load manifests.

Reports identify the commit and a digest of tracked/candidate file contents captured at run start,
including an already dirty working tree. The source fingerprint is not a signature or independent
attestation. Preserve the directory before changing code if a review needs durable evidence;
reports from different invocations are never automatically merged into a passing result.
PostgreSQL data files are excluded from the report's file-hash inventory; the recovery manifest
provides logical database fingerprints. Known credential environment values are redacted in logs.

Successful exit codes alone cannot pass test checks: absent/empty reports, unexpected skips,
failed tests and flaky/retried browser tests are rejected. Timeouts terminate owned command trees
and count as failure. Required PostgreSQL manifests must exist after a successful rehearsal.

The current runner does not implement live-provider or deployed load/recovery probes and does not
claim the API scenario is a full browser execution of all 17 steps. Actual identity/S3/scanner and
TLS acceptance, representative staging load/soak and disaster recovery, PM/planner sessions,
manual assistive-technology acceptance and accountable pilot approval remain NOT RUN. Follow
documents 15 and 19–24 for their acceptance procedures. Phases 12–14 remain open.

## Executed evidence (2026-10-27)

The corrected default invocation completed with selected checks PASS and R10 acceptance NOT RUN.
It passed 323 Python tests plus four subtests, all 45 standard browser/accessibility checks, the
synthetic HTTPS identity journey, lint/types/build and the PostgreSQL migration/recovery/96-read
load rehearsal. The ordinary suite skipped only live AI and the PostgreSQL profile subsequently
run by the separate database check. The cluster stopped successfully. Network advisory audits and
live AI were not selected. The initial failed run was retained; results were not merged across runs.

Current complete-run artifacts: `.test-tmp/r10-20261027T125516Z-1f47a907/`.
