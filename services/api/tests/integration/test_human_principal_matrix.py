import time
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import jwt
from app.config import get_settings
from app.database import Base
from app.human_commands import HUMAN_COMMANDS
from app.main import app
from app.models import AuditEvent, EvidenceItem, ImportBatch, Membership
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy import func, select
from test_control_context_api import api as api
from test_project_control_api import bootstrap_project


def test_machine_and_unclassified_principals_cannot_use_human_commands_even_with_admin_grants(
    api, monkeypatch, tmp_path
):
    client, sessions = api
    organization, project, headers = bootstrap_project(client, "human-boundary")
    with sessions() as session:
        for actor, role in (
            ("machine-admin", "PROJECT_ADMIN"),
            ("classified-service", "PROJECT_ADMIN"),
            ("classified-service", "SYSTEM_SERVICE"),
            ("human-contributor", "DATA_CONTRIBUTOR"),
        ):
            session.add(
                Membership(
                    organization_id=uuid.UUID(organization),
                    project_id=uuid.UUID(project),
                    actor_id=actor,
                    role=role,
                )
            )
        session.commit()
    for authority in (
        "CASE_DISPOSITION",
        "RESPONSE_AUTHORIZATION",
        "REPORT_APPROVAL",
        "CHARTER_APPROVAL",
        "CHANGE_APPROVAL",
    ):
        created = client.post(
            f"/api/v1/projects/{project}/authority-grants",
            headers=headers,
            json={"actor_id": "machine-admin", "authority_type": authority},
        )
        assert created.status_code == 201, created.text
    monkeypatch.setenv("VAI_EVIDENCE_STORAGE_PATH", str(tmp_path))
    get_settings.cache_clear()
    content = (
        b"field_name,value,semantic_state,truth_type,as_of\n"
        b"inspection_result,reported,REPORTED,REPORTED_CLAIM,2026-01-01T00:00:00Z\n"
        b"inspection_result,accepted,VERIFIED,VERIFIED_FACT,2026-01-01T00:00:00Z\n"
    )
    artifact = client.post(
        f"/api/v1/projects/{project}/evidence/artifacts",
        headers=headers,
        files={"upload": ("mixed.csv", content, "text/csv")},
        data={"source_type": "SITE_REPORT", "source_id": "principal-matrix"},
    )
    assert artifact.status_code == 201, artifact.text
    preview = client.post(
        f"/api/v1/projects/{project}/evidence/imports/preview",
        headers={**headers, "Idempotency-Key": "mixed-preview"},
        json={"artifact_id": artifact.json()["id"], "mapping": {}},
    )
    assert preview.status_code == 201, preview.text
    assert preview.json()["status"] == "PREVIEW", preview.text

    def counts():
        with sessions() as session:
            return {
                table.name: session.scalar(select(func.count()).select_from(table))
                for table in Base.metadata.tables.values()
            }

    before = counts()
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    values = {
        "VAI_ENVIRONMENT": "production",
        "VAI_OIDC_ISSUER": "https://issuer.example/",
        "VAI_OIDC_AUDIENCE": "principal-matrix",
        "VAI_OIDC_JWKS_URL": "https://issuer.example/keys",
        "VAI_RATE_LIMIT_PER_MINUTE": "10000",
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    monkeypatch.setattr(
        "app.oidc.signing_keys",
        lambda *args: SimpleNamespace(
            get_signing_key_from_jwt=lambda token: SimpleNamespace(key=private.public_key())
        ),
    )
    now = int(time.time())

    def token(subject, **claims):
        return jwt.encode(
            {
                "iss": values["VAI_OIDC_ISSUER"],
                "aud": "principal-matrix",
                "sub": subject,
                "iat": now - 1,
                "exp": now + 600,
                "https://vai.example/organization_id": organization,
                **claims,
            },
            private,
            algorithm="RS256",
            headers={"kid": "principal-key"},
        )

    scenarios = {
        "MACHINE_WITH_HUMAN_LABEL": token(
            "machine-admin",
            gty="client-credentials",
            **{"https://vai.example/principal_type": "HUMAN"},
        ),
        "UNCLASSIFIED": token("machine-admin"),
        "SERVICE_MEMBERSHIP_WITH_HUMAN_TOKEN": token(
            "classified-service", **{"https://vai.example/principal_type": "HUMAN"}
        ),
    }
    paths = app.openapi()["paths"]
    assert all(template in paths and "post" in paths[template] for template in HUMAN_COMMANDS)
    schemas = app.openapi()["components"]["schemas"]
    for template, operations in paths.items():
        operation = operations.get("post", {})
        schema = (
            operation.get("requestBody", {})
            .get("content", {})
            .get("application/json", {})
            .get("schema", {})
        )
        if "$ref" in schema:
            schema = schemas[schema["$ref"].rsplit("/", 1)[-1]]
        if {"authority_grant_id", "approval_reference", "approved_confidence"}.intersection(
            schema.get("properties", {})
        ):
            assert template in HUMAN_COMMANDS, f"Unclassified authority-bearing route: {template}"
    for template in sorted(HUMAN_COMMANDS):
        import re

        parameters = {name: str(uuid.uuid4()) for name in re.findall(r"{(\w+)}", template)}
        parameters.update(project_id=project, organization_id=organization)
        for scenario, credential in scenarios.items():
            response = client.post(
                template.format(**parameters),
                headers={
                    **headers,
                    "Authorization": "Bearer " + credential,
                    "Idempotency-Key": "no-human-impersonation",
                },
                json={},
            )
            assert response.status_code == 403, (
                f"{scenario} {template}: {response.status_code} {response.text}"
            )
            assert response.json()["detail"] == "Human principal required for this reserved command"
    assert counts() == before
    rejected_import = client.post(
        f"/api/v1/projects/{project}/evidence/imports/{preview.json()['id']}/commit",
        headers={**headers, "Authorization": "Bearer " + scenarios["MACHINE_WITH_HUMAN_LABEL"]},
    )
    assert rejected_import.status_code == 403, rejected_import.text
    assert counts() == before
    with sessions() as session:
        assert session.get(ImportBatch, uuid.UUID(preview.json()["id"])).status == "PREVIEW"
        assert session.scalar(select(func.count()).select_from(EvidenceItem)) == 0
    # The same machine role can prepare analytical scope; it cannot approve or verify it.
    prepared = client.post(
        f"/api/v1/projects/{project}/controlled-objects",
        headers={**headers, "Authorization": "Bearer " + scenarios["MACHINE_WITH_HUMAN_LABEL"]},
        json={
            "object_type": "WORK_PACKAGE",
            "code": "WP-SERVICE",
            "name": "Service-prepared scope",
        },
    )
    assert prepared.status_code == 201, prepared.text
    assertion = {
        "controlled_object_id": prepared.json()["id"],
        "field_name": "inspection_result",
        "value": "accepted",
        "as_of": datetime.now(UTC).isoformat(),
        "confidence": "0.9",
        "semantic_state": "VERIFIED",
        "truth_type": "VERIFIED_FACT",
    }
    service_headers = {
        **headers,
        "Authorization": "Bearer " + scenarios["MACHINE_WITH_HUMAN_LABEL"],
    }
    forbidden_fact = client.post(
        f"/api/v1/projects/{project}/evidence/items", headers=service_headers, json=assertion
    )
    assert forbidden_fact.status_code == 403
    contributor = token("human-contributor", **{"https://vai.example/principal_type": "HUMAN"})
    forbidden_contributor = client.post(
        f"/api/v1/projects/{project}/evidence/items",
        headers={**headers, "Authorization": "Bearer " + contributor},
        json=assertion,
    )
    assert forbidden_contributor.status_code == 403
    reported = client.post(
        f"/api/v1/projects/{project}/evidence/items",
        headers=service_headers,
        json={**assertion, "semantic_state": "REPORTED", "truth_type": "REPORTED_CLAIM"},
    )
    assert reported.status_code == 201, reported.text
    with sessions() as session:
        audit = session.scalar(
            select(AuditEvent).where(
                AuditEvent.object_id == prepared.json()["id"],
                AuditEvent.action == "CONTROLLED_OBJECT_CREATED",
            )
        )
        assert audit.actor_id == "machine-admin" and audit.actor_type == "SERVICE"
    human = token(headers["X-VAI-Actor-ID"], **{"https://vai.example/principal_type": "HUMAN"})
    permitted = client.post(
        f"/api/v1/projects/{project}/authority-grants",
        headers={**headers, "Authorization": "Bearer " + human},
        json={"actor_id": "reviewer", "authority_type": "CASE_DISPOSITION"},
    )
    assert permitted.status_code == 201, permitted.text
    verified_fact = client.post(
        f"/api/v1/projects/{project}/evidence/items",
        headers={**headers, "Authorization": "Bearer " + human},
        json=assertion,
    )
    assert verified_fact.status_code == 201, verified_fact.text
    print(f"Verified {len(HUMAN_COMMANDS)} reserved commands against three principal types.")
