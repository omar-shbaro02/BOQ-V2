import json
import re
import time
import uuid
from types import SimpleNamespace

import jwt
from app.config import get_settings
from app.database import Base
from app.main import app
from app.models import Membership
from app.security_scan import get_evidence_scanner
from app.storage import get_evidence_store
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy import func, select
from test_control_context_api import api as api
from test_project_control_api import bootstrap_project


def test_every_scoped_route_denies_foreign_unaffiliated_inactive_and_forged_identity(
    api, monkeypatch, tmp_path
):
    client, sessions = api
    victim_org, victim_project, victim_headers = bootstrap_project(client, "victim")
    attacker_org, _, attacker_headers = bootstrap_project(client, "attacker")
    other_project = client.post(
        f"/api/v1/organizations/{victim_org}/projects",
        headers=victim_headers,
        json={
            "code": "OTHER",
            "name": "Other project",
            "timezone": "UTC",
            "currency": "USD",
            "delivery_model": "DESIGN_BID_BUILD",
            "reporting_cadence": "WEEKLY",
        },
    )
    assert other_project.status_code == 201, other_project.text
    with sessions() as session:
        session.add(
            Membership(
                organization_id=uuid.UUID(victim_org),
                project_id=uuid.UUID(victim_project),
                actor_id="retired-subject",
                role="PROJECT_ADMIN",
                active=False,
            )
        )
        session.add(
            Membership(
                organization_id=uuid.UUID(victim_org),
                project_id=uuid.UUID(other_project.json()["id"]),
                actor_id="other-project-admin",
                role="PROJECT_ADMIN",
                active=True,
            )
        )
        session.commit()

    def row_counts():
        with sessions() as session:
            return {
                table.name: session.scalar(select(func.count()).select_from(table))
                for table in Base.metadata.tables.values()
            }

    before = row_counts()
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    issuer, audience = "https://issuer.example/", "security-matrix-api"
    for key, value in {
        "VAI_ENVIRONMENT": "production",
        "VAI_OIDC_ISSUER": issuer,
        "VAI_OIDC_AUDIENCE": audience,
        "VAI_OIDC_JWKS_URL": "https://issuer.example/keys",
        "VAI_RATE_LIMIT_PER_MINUTE": "10000",
    }.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    keys = SimpleNamespace(
        get_signing_key_from_jwt=lambda token: SimpleNamespace(key=private.public_key())
    )
    monkeypatch.setattr("app.oidc.signing_keys", lambda *args: keys)
    now = int(time.time())

    def token(subject, organization, expired=False):
        return jwt.encode(
            {
                "iss": issuer,
                "aud": audience,
                "sub": subject,
                "iat": now - 1,
                "exp": now - 1 if expired else now + 600,
                "https://vai.example/organization_id": organization,
                "roles": ["ORGANIZATION_ADMIN"],
            },
            private,
            algorithm="RS256",
            headers={"kid": "matrix-key"},
        )

    scenarios = {
        "FOREIGN_TENANT": (
            {
                "Authorization": "Bearer "
                + token(attacker_headers["X-VAI-Actor-ID"], attacker_org),
                "X-VAI-Organization-ID": attacker_org,
            },
            403,
        ),
        "SAME_TENANT_NO_MEMBERSHIP": (
            {
                "Authorization": "Bearer " + token("unaffiliated-subject", victim_org),
                **victim_headers,
                "X-VAI-Roles": "ORGANIZATION_ADMIN",
            },
            403,
        ),
        "INACTIVE_MEMBERSHIP": (
            {
                "Authorization": "Bearer " + token("retired-subject", victim_org),
                **victim_headers,
                "X-VAI-Roles": "ORGANIZATION_ADMIN",
            },
            403,
        ),
        "FORGED_DEVELOPMENT_IDENTITY": (
            {**victim_headers, "X-VAI-Roles": "ORGANIZATION_ADMIN"},
            401,
        ),
        "EXPIRED_TOKEN": (
            {
                "Authorization": "Bearer "
                + token(victim_headers["X-VAI-Actor-ID"], victim_org, expired=True),
                **victim_headers,
            },
            401,
        ),
        "OTHER_PROJECT_MEMBERSHIP": (
            {
                "Authorization": "Bearer " + token("other-project-admin", victim_org),
                **victim_headers,
            },
            403,
        ),
    }

    def deny_adapters():
        raise AssertionError("Unauthorized requests must stop before storage/scanner adapters")

    app.dependency_overrides[get_evidence_store] = deny_adapters
    app.dependency_overrides[get_evidence_scanner] = deny_adapters
    operations = [
        (method, path)
        for path, value in app.openapi()["paths"].items()
        if "{project_id}" in path or "{organization_id}" in path
        for method in value
    ]
    assert len(operations) >= 157
    results = []
    for method, template in operations:
        values = {name: str(uuid.uuid4()) for name in re.findall(r"{(\w+)}", template)}
        values.update(project_id=victim_project, organization_id=victim_org)
        path = template.format(**values)
        for scenario, (headers, expected) in scenarios.items():
            if scenario == "OTHER_PROJECT_MEMBERSHIP" and "{project_id}" not in template:
                continue
            response = client.request(
                method.upper(),
                path,
                headers={**headers, "Idempotency-Key": "denied-command"},
                json={} if method == "post" else None,
            )
            assert response.status_code == expected, (
                f"{scenario} {method.upper()} {template}: {response.status_code} {response.text}"
            )
            assert response.headers["Cache-Control"] == "private, no-store"
            assert response.headers["X-Content-Type-Options"] == "nosniff"
            results.append(
                {
                    "scenario": scenario,
                    "method": method.upper(),
                    "path": template,
                    "status": response.status_code,
                }
            )
    assert row_counts() == before
    report = tmp_path / "route-security-matrix.json"
    report.write_text(
        json.dumps(
            {
                "scoped_operations": len(operations),
                "denial_checks": len(results),
                "database_unchanged": True,
                "results": results,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(
        f"Verified {len(operations)} scoped operations / {len(results)} production denials; "
        "database unchanged."
    )


def test_local_preview_routes_are_unavailable_in_production_before_payload_validation(monkeypatch):
    from fastapi.testclient import TestClient

    monkeypatch.setenv("VAI_ENVIRONMENT", "production")
    monkeypatch.setenv("VAI_RATE_LIMIT_PER_MINUTE", "10000")
    get_settings.cache_clear()
    operations = [
        (method, path)
        for path, value in app.openapi()["paths"].items()
        if path.startswith("/api/v1/ms-project/")
        for method in value
    ]
    assert len(operations) == 4
    with TestClient(app) as client:
        for method, path in operations:
            response = client.request(method.upper(), path, json={})
            assert response.status_code == 403, f"{method.upper()} {path}: {response.text}"
