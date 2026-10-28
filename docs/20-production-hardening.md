# Production hardening and verification

R10 is in progress. This document records implementation and remaining deployment evidence;
it does not authorize a pilot or replace representative human-operator acceptance.

## Selected adapters

Use **Auth0 RS256 access tokens**, **Amazon S3**, and a private **ClamAV daemon**. The adapters use
standard OIDC/JWKS and S3 contracts so compatible existing infrastructure can be configured.
There are no vendor controls or scanner screens in the application. No accounts, paid resources,
or production services have been provisioned.

```text
VAI_ENVIRONMENT=production
VAI_OIDC_ISSUER=https://YOUR-TENANT.auth0.com/
VAI_OIDC_AUDIENCE=YOUR-VAI-API-IDENTIFIER
VAI_OIDC_JWKS_URL=https://YOUR-TENANT.auth0.com/.well-known/jwks.json
VAI_OIDC_ORGANIZATION_CLAIM=https://vai.example/organization_id
VAI_OIDC_PRINCIPAL_TYPE_CLAIM=https://vai.example/principal_type
VAI_OIDC_JWKS_CACHE_SECONDS=300
VAI_OIDC_CLIENT_ID=YOUR-REGULAR-WEB-APPLICATION-CLIENT
VAI_OIDC_AUTHORIZATION_URL=https://YOUR-TENANT.auth0.com/authorize
VAI_OIDC_TOKEN_URL=https://YOUR-TENANT.auth0.com/oauth/token
VAI_SESSION_PUBLIC_ORIGIN=https://YOUR-APPLICATION-ORIGIN
VAI_SESSION_MAX_AGE_SECONDS=900
VAI_ADAPTER_TIMEOUT_SECONDS=5
VAI_EVIDENCE_STORAGE_BACKEND=s3
VAI_S3_BUCKET=YOUR-PRIVATE-EVIDENCE-BUCKET
VAI_S3_REGION=YOUR-AWS-REGION
VAI_S3_PREFIX=vai/
VAI_MALWARE_SCANNER_BACKEND=clamd
VAI_CLAMD_HOST=YOUR-PRIVATE-CLAMD-HOST
VAI_CLAMD_PORT=3310
VAI_CLAMD_MAX_SIGNATURE_AGE_HOURS=48
```

## Identity and browser deployment

The API requires the exact issuer/API audience, RS256 signature, key ID, expiry, issued-at time,
stable subject, and organization UUID claim. Development actor/role headers cannot impersonate a
production user. A conflicting organization-selection header is denied. The signed subject maps
to `Membership.actor_id`; membership and authority remain database-owned. Token roles cannot
create an admin or approval grant. Initial organization/subject membership provisioning requires
an audited deployment process; development role-header bootstrap remains unavailable.

For bearer clients, set the principal-type claim from trusted provider configuration to `HUMAN`
or `SERVICE`; never derive it from editable user metadata. Client-credentials `gty` always makes
the principal SERVICE, overriding a conflicting HUMAN label. An absent/unrecognized classification
is UNKNOWN and cannot issue human-reserved commands. A fully verified interactive browser login
can establish human identity through its ID-token/nonce binding; a SERVICE access token cannot
create that browser session. Database `SYSTEM_SERVICE` membership independently prohibits human
commands even alongside admin roles. Taxonomy 1.10.0 adds this role; stored role columns already
support it, so this addition requires no schema migration.

All 157 scoped API operations now enforce tenant and active membership before payload/resource
handling. The production-token matrix verifies 939 denials across foreign tenants, nonmembers,
inactive members, forged development headers, expired tokens, and other-project administrators.
All 31 human-reserved commands deny three service/unknown identity variants (93 checks), including
identities owning admin roles and grants. Denials preserve database row counts and cannot reach
storage/scanning adapters. Four local preview operations are unavailable in production.

Additional semantic tests cover exact case authority, whole-case package scope, atomic mixed
reported/verified import rejection, and explicit context activation grants/idempotency/predecessor
checks. Existing historical approvals are not assigned invented grant provenance. The API contract
documents the stricter activation inputs. ORM metadata now mirrors the existing PostgreSQL
single-current constraint; no new migration is necessary. A real isolated PostgreSQL rehearsal
upgrades, downgrades to 0029, re-upgrades to head, denies duplicate current contexts and immutable
updates/deletes, and preserves populated-history rollback protections. Concurrent initial budget
approvals produce one 201 and one 409; retry returns the winner's exact original ID. This focused
race check is not a full concurrency or throughput benchmark.

Recovery verification exposed missing database enforcement on audit rows. Migration
`0031_audit_append_only` adds UPDATE/DELETE and TRUNCATE rejection without rewriting history.
Downgrading this revision only removes the triggers. Runtime database credentials must remain
least-privilege and cannot own schemas, disable triggers, or issue DDL; row triggers are not a
boundary against a database owner. The deployment must deny TRUNCATE and destructive privileges
across governed tables, including those whose existing protection is a row trigger.

Set the organization UUID claim from trusted provider application metadata, never editable user
metadata or an email-address match. Configure MFA and token lifetimes at the provider. Register
the exact callback `https://YOUR-APPLICATION-ORIGIN/api/v1/auth/callback`, enable authorization-code
flow with PKCE, and configure client-secret POST authentication. Supply `VAI_OIDC_CLIENT_SECRET`
and `VAI_SESSION_ENCRYPTION_KEYS` through a secret manager. The latter is a JSON list of one to
three Fernet keys (32 random bytes encoded as URL-safe base64); the first encrypts new cookies,
and retained keys permit bounded rotation. No default encryption key exists.

The existing API implements `/api/v1/auth/login`, `/callback`, `/session`, and POST `/logout`.
Login binds a ten-minute encrypted transaction cookie to state, nonce, and S256 PKCE. The server
exchanges the code, verifies the access token and the separate client ID token, checks subject,
nonce, authorized party, and optional access-token hash binding, then creates a short-lived
encrypted `__Host-vai-session` cookie. It is Secure, HttpOnly, SameSite=Lax, host-only, and scoped
to `/`. Tokens never enter browser JavaScript storage. Every API request still verifies access
token validity and database authority. Browser-session commands require the exact public Origin;
cross-origin or missing-Origin commands are denied. Explicit bearer API clients remain supported.

Build the web with `NEXT_PUBLIC_VAI_API_URL` empty and server-only `VAI_API_INTERNAL_URL` set to
the trusted internal API origin. Next proxies `/api/v1/*` under the application's HTTPS origin;
no separate authentication gateway is required. Terminate TLS at a maintained reverse proxy or
load balancer, keep the API private, and configure trusted forwarding addresses explicitly.
Do not accept arbitrary client-supplied forwarded IP/identity headers. The account control
supports sign-in/out; workspace identity comes from the verified session rather than saved
development fields. The local workspace bootstrap remains available only in development/test.

Sign-out clears browser cookies and client workspace state. Sessions are stateless and bounded
by configured age and token validity; a copied credential is not globally revoked by clearing a
browser cookie. Provider SSO sessions are separate. Real provider MFA, expiry/rotation/revocation,
shared-device logout policy, and deployed TLS/forwarding still require staging acceptance.
Never put tokens, client secrets, encryption keys, or AWS credentials in `NEXT_PUBLIC_*`, source
files, local storage, or logs. Callback query parameters are redacted from API access logs;
configure equivalent redaction at the TLS edge.

The JWKS set has a finite TTL and unknown-key refresh cooldown; keys are not cached indefinitely.
Missing configuration or signing-key outages return 503; invalid credentials return 401. HTTPS
is required for identity and custom storage endpoints. See the
[PyJWT API reference](https://pyjwt.readthedocs.io/en/latest/api.html).
The transaction binding follows [OAuth security BCP](https://www.rfc-editor.org/info/rfc9700/)
and [Auth0's OIDC flow](https://auth0.com/intro-to-iam/what-is-openid-connect-oidc).

## Request and browser hardening

The API enforces declared and actual streamed request-body limits, including chunked requests,
before a domain command can accept the body. `VAI_MAX_REQUEST_BYTES` defaults to 64 MiB and must
match the web build and API settings. Next's proxy buffer uses that same limit; its default
10 MiB buffer otherwise truncates larger requests. The HTTPS production-browser test sends
12 MiB through the full proxy chain and proves the API receives every byte.

Production requests have a bounded per-peer-IP, per-process rate limiter (default 120/minute,
10,000 buckets maximum). Rejection returns 429/Retry-After. It is an application safety layer;
multi-replica deployments also require a coordinated edge limit and verified trusted client-IP
forwarding. TLS-edge request/read timeouts and maximum-body settings remain deployment controls.

API and web responses include framing, MIME-sniffing, referrer, and permissions restrictions;
production HTTPS responses use HSTS. API responses are private/no-store. Web CSP restricts
connections to self/configured API, forbids objects and framing, and limits forms/base URLs to
self. Static Next hydration currently requires inline scripts/styles; the policy is not a
claim of nonce-based XSS prevention. Development alone allows eval/WebSocket tooling. Production
API documentation routes are disabled.

`python scripts/check_secrets.py` (or `make check-secrets`) examines tracked and candidate source
files for high-confidence private key/API key patterns and credential/config files. Findings
report only location/type, never matched values. CI runs this check and both browser suites.
The check supplements secret-manager controls; it does not prove arbitrary files contain no
secrets. OAuth/session secrets use `SecretStr`, and no browser API exposes token material.

## Object storage

Use the AWS credential chain with a workload IAM role restricted to the private bucket/prefix.
Enable versioning, block public access, enforce TLS, and configure retention/backup outside the
runtime. The adapter requests AES256 encryption or KMS when `VAI_S3_KMS_KEY_ID` is set. An optional
HTTPS `VAI_S3_ENDPOINT_URL` supports a compatible store.

Writes use `If-None-Match: *`. A replay succeeds only when existing bytes match. SHA-256 metadata,
exact length, and bounded reads are verified; evidence/report consumers also check database-bound
hashes. Missing, altered, inaccessible, or oversized objects cannot become evidence. Deletion is
transaction-failure cleanup, not a public artifact-deletion command. Network timeouts/retries are
bounded. `VAI_MAX_ARTIFACT_BYTES` defaults to 64 MiB. See
[S3 conditional writes and encryption](https://docs.aws.amazon.com/boto3/latest/reference/services/s3/client/put_object.html).

## Malware scanning

Run maintained ClamAV/freshclam privately with `TZ=UTC` and an English/C time locale. Never expose
the unauthenticated daemon socket publicly. Match `StreamMaxLength` to accepted uploads; enable
archive scanning and `AlertExceedsMax`. The API checks database version/freshness, then streams
exact uploaded bytes in bounded INSTREAM chunks under one deadline. Only a complete exact
`stream: OK` permits CLEAN. Infection returns 422; stale signatures, timeout, malformed/truncated
responses, limit errors, and unavailable scanning return 503. There is no production fallback to
the development EICAR gate. Scanner/signature provenance is stored with the artifact. See the
[ClamD protocol](https://docs.clamav.net/manual/Usage/ClamdProtocol.html).

## Workbook resource limits

All XLSX/XLSM evidence uploads and all six workbook readers share this preflight:

| Resource | Limit |
| --- | --- |
| Compressed workbook | 25 MiB |
| Entries / ZIP directory | 2,048 / 2 MiB |
| Expanded total / entry | 64 MiB / 16 MiB |
| Per-entry compression ratio | 200 |
| Worksheets | 32 |
| Row / column index per sheet | 50,000 / 512 |
| Populated cells / XML elements | 200,000 / 1,000,000 |

ZIP64, multipart/encrypted archives, unsafe/duplicate names, malformed XML, DTDs, and entities are
rejected. XML roots are checked even with alternate paths/extensions. Sparse dimensions cannot
force enormous iteration. Oversized imports fail visibly; they are never silently truncated.

## Verification and remaining gates

The locked Python dependency audit found affected `certifi` and `pytest` versions. Pins now use
certifi 2026.10.23 and pytest 9.0.3; the dev dependency range permits the patched pytest major.
An isolated pip-audit 2.10.1 run against all 46 pinned packages reports no known vulnerabilities.
The full public-registry npm audit also reports zero findings across runtime/development packages.
CI has a separate dependency-audit job for both ecosystems; it has not been run remotely.
Advisory results are time-bound and do not prove absence of unknown vulnerabilities. The pytest
fix is documented in its [official changelog](https://pytest.org/en/stable/changelog.html).

See [recovery verification](21-recovery-verification.md) for the isolated logical backup/restore
rehearsal and the remaining staging disaster-recovery acceptance procedure.

Thirty focused tests cover signature/claim denial, JWKS caching/cooldown, encrypted conditional
storage and integrity/outages, real loopback ClamD framing, incomplete/infected/stale scan denial,
unsafe archives, XML/iteration bounds, and normal workbook compatibility. Default tests prohibit
HTTPX, urllib, and botocore network transports; live checks require explicit opt-in. These tests
do not prove a deployed Auth0 tenant, bucket IAM/retention, maintained scanner, or gateway session.

Browser sessions, request/rate/header limits, and credential checks are implemented. A production
Next build and production API passed the complete HTTPS code/JWKS/token/cookie/sign-out journey
against a disposable synthetic issuer, including foreign saved identity denial, cross-origin
command denial, 12 MiB proxy fidelity, and mobile layout checks. Run `npm run test:browser:oidc`
separately from `npm run test:browser`; the isolated harness builds the web and creates temporary
loopback certificates/database under ignored `.test-tmp`. It never uses developer credentials.
This is protocol evidence, not live Auth0, S3 IAM, or maintained malware-engine acceptance.

Local automated accessibility and queue-query/load evidence is recorded in
[nonfunctional verification](22-nonfunctional-verification.md). This includes the existing critical
journeys and populated governance/progress/health, not just empty pages. It preserves outstanding
manual-review findings and does not assert complete WCAG conformance or deployed capacity.

Still required: live adapter/deployment verification; manual accessibility and representative
staging load/soak; staging backup/restore and disaster recovery; BS-001–BS-010;
representative human sessions; findings closure;
and explicit pilot entry approval. Phase 12 acceptance and Phases 13–14 remain open.
