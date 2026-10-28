# Recovery verification

The R10 local rehearsal proves recovery of synthetic database history and local artifact bytes.
It does not establish a production recovery point/time objective, point-in-time recovery, S3
version retention, regional failover, key availability, or an approved disaster-recovery service.

## Reproduce the isolated rehearsal

On Windows with the bundled PostgreSQL runtime:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/rehearse_remediation.ps1 -DowngradeTarget 0029_snapshot_health
```

The script creates a private disposable cluster bound to loopback, upgrades to head, downgrades
and re-upgrades, seeds governed synthetic records through the API, exercises concurrent approvals
and immutable-history guards, then runs logical recovery. It stops the cluster in `finally` and
restores the caller's database environment. No developer database is used. The recovery helper
rejects any source except the loopback `vai_remediation` database without a password; this is a
test harness, not a production backup command.

The rehearsal also runs source extraction, normalization, draft generation, material correction,
CPM, review and publication against enforcing PostgreSQL foreign keys. It verifies an existing
authorized schedule survives a later proposed correction, rejects stale reviews/approvals, and
serializes a two-writer correction race to one success and one stale-version conflict. Corrected
structure metadata rejects UPDATE/DELETE and is included in the recovered database fingerprint.
This path exposed a parent/child insertion-order defect masked by SQLite; finalized source,
normalization and generation parents now flush before their dependent rows without subsequent
append-only updates. Those ordering fixes did not require a migration.

The subsequent connected-scenario prerequisite adds migration `0032_context_history_guard`.
Rehearsal covers 0032 → 0031 → 0032, explicit planned control inputs, distinct authorized baseline
and current sources, preservation of that baseline across later current approval, and exact planned
measurement matching. Baseline, current and superseded contexts reject payload/actor updates and
deletion; the context table rejects TRUNCATE. Legitimate current supersession still succeeds.
All context rows and guard definitions are included in the full logical recovery fingerprint.
Current synthetic manifests are under
`.test-tmp/pg-remediation-768e153eb8ba43159bb8399a5e68d1ad/pytest/`; the cluster stopped successfully.

Recovery uses `pg_dump --format=custom` and `pg_restore --exit-on-error` into a separately named
disposable database. Artifact bytes are copied into a separate backup store and then a separate
restored store. The helper compares every public table's row count and deterministic row digest,
index definitions, trigger definitions, and trigger function bodies. It checks the restored deck
through the API: missing bytes return 503, changed bytes return 409, exact recovered bytes return
200, and a foreign tenant remains denied. Restored audit, project-context, and presentation rows
still reject UPDATE and DELETE. The source database's fingerprint must remain unchanged.
Audit history also rejects TRUNCATE. A successful recovered presentation download appends exactly
one new access-audit event; its actor, action, and deck ID are checked separately while the
original audit rows retain their exact digest.

The test directory contains `synthetic-recovery.dump`, `backup-objects`, `restored-objects`, and
`recovery-manifest.json` under ignored `.test-tmp/pg-remediation-*/pytest/`. The manifest records
all table digests/counts, object keys/digests, dump digest, observed elapsed times, and denial
results. These contain only synthetic fixtures. Timings are local observations with no production
SLO assertion. The restored database is dropped after verification; the stopped source cluster
and ignored files remain available for local inspection.

The fixture is quiescent while the database and object backup are captured. This does not prove
consistency of independently timed database/S3 backups during live writes. No synthetic recovery
changes report approval, human decisions, or execution authorization.

## Required staging disaster-recovery acceptance

Before pilot entry, the deployment owner must record the selected retention, legal-hold,
encryption/key-recovery policy, backup owner, recovery-point objective, recovery-time objective,
and independently accessible backup location. Do not infer these from local test timings.

1. Capture a consistent database checkpoint plus an inventory of the exact object versions and
   hashes referenced by that checkpoint. Include migrations, taxonomy/application versions,
   configuration references, and required KMS/secret-manager key versions; exclude secret values
   from the manifest. Verify monitored backups and PostgreSQL WAL/PITR retention.
2. Rehearse loss of the application/database host in an isolated staging environment. Restore
   the checkpoint and required WAL to the selected recovery point, and restore the matching
   private object versions. Recover keys and identity configuration through the approved secret
   manager. Keep mutation access closed until lineage and authorization checks pass.
3. Reconcile table/object counts and hashes, all foreign keys and immutable guards, exact
   approved/current context lineage, report/presentation approval history, outbox delivery state,
   and idempotency records. Missing or damaged artifacts must restrict availability visibly;
   never fabricate replacements or promote reported data to verified state.
4. Verify real OIDC membership, service/human separation, tenant denial, TLS/forwarding, storage
   IAM, scanner freshness, and protected API/browser journeys. Replaying an old idempotency key
   must return the original result without issuing new approval or execution authority.
5. Record the recovered checkpoint, actual data loss, elapsed outage and recovery times, failed
   checks, operator identity, and explicit release decision. Compare observed results with the
   selected objectives and resolve critical/high findings before reopening mutations.

Staging outage, WAL/PITR, cloud object-version recovery, key recovery, and an accountable operator's
release decision remain open. Local logical restoration does not close those gates or authorize
Phase 13/pilot entry.
