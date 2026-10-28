import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from app.database import Base, get_db
from app.main import app
from app.models import AuditEvent, AuthorizedContextVersion, ProjectContextRecord
from context_helpers import activate_with_authority
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture
def context_api() -> Generator[tuple[TestClient, Any, str, dict[str, str]], None, None]:
    engine = create_engine(
        "sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)

    def override_db():
        with sessions() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        org = client.post(
            "/api/v1/organizations",
            headers={"X-VAI-Actor-ID": "pm@test", "X-VAI-Roles": "ORGANIZATION_ADMIN"},
            json={"name": "Context tests", "slug": "context-tests"},
        )
        assert org.status_code == 201, org.text
        headers = {"X-VAI-Actor-ID": "pm@test", "X-VAI-Organization-ID": org.json()["id"]}
        project = client.post(
            f"/api/v1/organizations/{org.json()['id']}/projects",
            headers=headers,
            json={
                "code": "CTX",
                "name": "Context test",
                "timezone": "Asia/Beirut",
                "currency": "USD",
                "delivery_model": "DESIGN_BID_BUILD",
                "reporting_cadence": "WEEKLY",
            },
        )
        assert project.status_code == 201, project.text
        yield client, sessions, project.json()["id"], headers
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()


def record_payload(kind="CHARTER", **extra):
    payloads = {
        "CHARTER": {
            "objectives": ["Deliver school"],
            "constraints": ["Occupied site"],
            "milestones": [{"name": "Handover", "date": "2027-06-01"}],
            "success_criteria": ["Accepted building"],
            "delivery_strategy": "Phased construction",
            "authority_reference": "Board charter 001",
        },
        "STAKEHOLDER": {
            "name": "Client PM",
            "project_role": "CLIENT",
            "communication_rules": ["Weekly approved report only"],
            "report_recipient": True,
        },
        "RISK": {
            "title": "Long lead",
            "description": "Reported procurement exposure",
            "owner_actor_id": "pm@test",
        },
        "ISSUE": {
            "title": "Access blocked",
            "description": "Reported access restriction",
            "owner_actor_id": "pm@test",
        },
        "CHANGE_REQUEST": {
            "title": "Revised sequence",
            "description": "Proposed work sequence",
            "rationale": "Maintain safe access",
            "affected_context_type": "SCHEDULE",
        },
        "DAILY_UPDATE": {
            "data_date": "2026-09-04",
            "reporting_cutoff": "2026-09-04T18:00:00+03:00",
            "weather": {"condition": "Reported dry"},
            "labor": [{"trade": "masonry", "count": 4}],
            "equipment": [],
            "quantities": [{"quantity": "12", "unit": "m3"}],
            "blockers": ["Access"],
            "safety_quality_observations": ["Inspection pending"],
        },
    }
    return {
        "record_type": kind,
        "record_key": "PROJECT_CHARTER" if kind == "CHARTER" else f"{kind}-001",
        "effective_from": "2026-09-04T00:00:00Z",
        "payload": payloads[kind],
        **extra,
    }


def evidence(client, project_id, headers, **extra):
    response = client.post(
        f"/api/v1/projects/{project_id}/evidence/items",
        headers=headers,
        json={
            "field_name": "site_report",
            "value": "Observed access",
            "semantic_state": "REPORTED",
            "truth_type": "REPORTED_CLAIM",
            "as_of": "2026-09-04T08:00:00Z",
            "confidence": "0.6",
            **extra,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def post_record(client, project_id, headers, data, key="record-1"):
    return client.post(
        f"/api/v1/projects/{project_id}/project-context/records",
        headers={**headers, "Idempotency-Key": key},
        json=data,
    )


def transition(client, project_id, record_id, headers, status, version=0, key="review-1", **extra):
    return client.post(
        f"/api/v1/projects/{project_id}/project-context/records/{record_id}/transitions",
        params={"expected_version": version},
        headers={**headers, "Idempotency-Key": key},
        json={"to_status": status, "reason": "Explicit human review", **extra},
    )


def grant(client, project_id, headers, kind, **extra):
    response = client.post(
        f"/api/v1/projects/{project_id}/authority-grants",
        headers=headers,
        json={"actor_id": headers["X-VAI-Actor-ID"], "authority_type": kind, **extra},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_charter_versioning_review_approval_idempotency_and_tenant_boundary(context_api):
    client, sessions, project_id, headers = context_api
    data = record_payload()
    created = post_record(client, project_id, headers, data)
    assert created.status_code == 201, created.text
    record_id = created.json()["id"]
    assert created.json()["current_status"] == "DRAFT"
    assert post_record(client, project_id, headers, data).json()["id"] == record_id
    changed = {**data, "effective_from": "2026-09-05T00:00:00Z"}
    assert post_record(client, project_id, headers, changed).status_code == 409
    assert transition(client, project_id, record_id, headers, "APPROVED").status_code == 409
    reviewed = transition(client, project_id, record_id, headers, "REVIEWED")
    assert reviewed.status_code == 201, reviewed.text
    assert (
        transition(client, project_id, record_id, headers, "REVIEWED").json()["id"]
        == reviewed.json()["id"]
    )
    assert (
        transition(client, project_id, record_id, headers, "REJECTED", key="stale").status_code
        == 409
    )
    assert (
        transition(
            client, project_id, record_id, headers, "APPROVED", version=1, key="approve"
        ).status_code
        == 403
    )
    authority = grant(client, project_id, headers, "CHARTER_APPROVAL")
    approved = transition(
        client,
        project_id,
        record_id,
        headers,
        "APPROVED",
        version=1,
        key="approve",
        authority_grant_id=authority,
        approval_reference="Signed charter 001",
    )
    assert approved.status_code == 201, approved.text
    assert approved.json()["authorized_context_id"] is None
    assert (
        post_record(client, project_id, headers, data, key="missing-predecessor").status_code == 409
    )
    second = post_record(
        client, project_id, headers, {**data, "supersedes_record_id": record_id}, key="record-2"
    )
    assert second.status_code == 201, second.text
    assert second.json()["version_number"] == 2
    assert second.json()["current_status"] == "DRAFT"
    assert (
        transition(
            client, project_id, record_id, headers, "REVIEWED", version=2, key="old-version"
        ).status_code
        == 409
    )
    path = f"/api/v1/projects/{project_id}/project-context/records/{record_id}"
    assert (
        client.get(
            path, headers={**headers, "X-VAI-Organization-ID": str(uuid.uuid4())}
        ).status_code
        == 403
    )
    assert client.get(path, headers={**headers, "X-VAI-Actor-ID": "outsider"}).status_code == 403
    assert client.get(path, headers=headers).json()["payload"] == data["payload"]
    with sessions() as session:
        assert len(list(session.scalars(select(ProjectContextRecord)))) == 2
        actions = list(session.scalars(select(AuditEvent.action)))
        assert actions.count("PROJECT_CONTEXT_RECORDED") == 2
        assert actions.count("PROJECT_CONTEXT_TRANSITIONED") == 2


@pytest.mark.parametrize(
    "override",
    [
        {"actor_id": "someone-else"},
        {"authority_type": "REPORT_APPROVAL"},
        {"valid_until": "2020-01-01"},
        {"max_amount": "100", "currency": "USD"},
        {"valid_from": (datetime.now(UTC) + timedelta(days=30)).date().isoformat()},
    ],
)
def test_charter_authority_denials(context_api, override):
    client, _, project_id, headers = context_api
    created = post_record(client, project_id, headers, record_payload()).json()
    assert transition(client, project_id, created["id"], headers, "REVIEWED").status_code == 201
    authority = (
        grant(client, project_id, headers, "CHARTER_APPROVAL", **override)
        if "authority_type" not in override
        else grant(client, project_id, headers, override["authority_type"])
    )
    response = transition(
        client,
        project_id,
        created["id"],
        headers,
        "APPROVED",
        version=1,
        key="approve",
        authority_grant_id=authority,
        approval_reference="Signed charter",
    )
    assert response.status_code == 403, response.text


@pytest.mark.parametrize(
    "kind,following", [("DAILY_UPDATE", "REVIEWED"), ("RISK", "MITIGATING"), ("ISSUE", "RESOLVED")]
)
def test_operational_context_requires_evidence_and_review_does_not_verify(
    context_api, kind, following
):
    client, _, project_id, headers = context_api
    data = record_payload(kind)
    assert post_record(client, project_id, headers, data).status_code == 422
    item_id = evidence(client, project_id, headers)
    data["evidence_item_ids"] = [item_id]
    created = post_record(client, project_id, headers, data)
    assert created.status_code == 201, created.text
    reviewed = transition(client, project_id, created.json()["id"], headers, following)
    assert reviewed.status_code == 201, reviewed.text
    items = client.get(f"/api/v1/projects/{project_id}/evidence/items", headers=headers)
    item = next(value for value in items.json() if value["id"] == item_id)
    assert item["truth_type"] == "REPORTED_CLAIM"
    assert item["semantic_state"] == "REPORTED"


def test_daily_update_cutoff_and_evidence_date_gates(context_api):
    client, _, project_id, headers = context_api
    item_id = evidence(client, project_id, headers, as_of="2026-09-05T08:00:00Z")
    data = record_payload("DAILY_UPDATE", evidence_item_ids=[item_id])
    assert post_record(client, project_id, headers, data).status_code == 422
    data["payload"]["reporting_cutoff"] = "2026-09-04T23:30:00Z"
    assert post_record(client, project_id, headers, data).status_code == 422


def test_stakeholder_recipient_registry_preserves_versions(context_api):
    client, _, project_id, headers = context_api
    data = record_payload("STAKEHOLDER")
    first = post_record(client, project_id, headers, data)
    assert first.status_code == 201, first.text
    assert first.json()["payload"]["report_recipient"] is True
    retired = transition(client, project_id, first.json()["id"], headers, "RETIRED")
    assert retired.status_code == 201, retired.text
    records = client.get(f"/api/v1/projects/{project_id}/project-context/records", headers=headers)
    assert records.json()[0]["current_status"] == "RETIRED"


def test_approved_change_creates_new_authorized_context_without_rewriting_source(context_api):
    client, sessions, project_id, headers = context_api
    item_id = evidence(client, project_id, headers)
    created = post_record(
        client, project_id, headers, record_payload("CHANGE_REQUEST", evidence_item_ids=[item_id])
    )
    assert created.status_code == 201, created.text
    record_id = created.json()["id"]
    assert transition(client, project_id, record_id, headers, "REVIEWED").status_code == 201
    proposed = client.post(
        f"/api/v1/projects/{project_id}/authorized-context/versions",
        headers=headers,
        json={
            "context_type": "SCHEDULE",
            "semantic_state": "PROPOSED",
            "effective_from": "2026-09-04T00:00:00Z",
            "payload": {
                "data_date": "2026-09-04",
                "activities": [
                    {
                        "code": "A1",
                        "name": "Access works",
                        "planned_start": "2026-09-04",
                        "planned_finish": "2026-09-05",
                        "progress_basis": "PHYSICAL_EXECUTED",
                        "responsible_owner": "pm@test",
                    }
                ],
            },
        },
    )
    assert proposed.status_code == 201, proposed.text
    authority = grant(client, project_id, headers, "CHANGE_APPROVAL")
    approved = transition(
        client,
        project_id,
        record_id,
        headers,
        "APPROVED",
        version=1,
        key="approve",
        authority_grant_id=authority,
        authorized_context_source_version_id=proposed.json()["id"],
        approval_reference="Signed change 001",
    )
    assert approved.status_code == 201, approved.text
    assert approved.json()["authorized_context_id"] != proposed.json()["id"]
    with sessions() as session:
        source = session.get(AuthorizedContextVersion, uuid.UUID(proposed.json()["id"]))
        authorized = session.get(
            AuthorizedContextVersion, uuid.UUID(approved.json()["authorized_context_id"])
        )
        assert source.semantic_state == "PROPOSED"
        assert source.payload == authorized.payload
        assert authorized.source_version_id == source.id
        assert authorized.semantic_state == "CURRENT_AUTHORIZED"


def test_change_approval_rejects_stale_authorized_context(context_api):
    client, _, project_id, headers = context_api
    item_id = evidence(client, project_id, headers)
    created = post_record(
        client, project_id, headers, record_payload("CHANGE_REQUEST", evidence_item_ids=[item_id])
    )
    record_id = created.json()["id"]
    assert transition(client, project_id, record_id, headers, "REVIEWED").status_code == 201
    source = client.post(
        f"/api/v1/projects/{project_id}/authorized-context/versions",
        headers=headers,
        json={
            "context_type": "SCHEDULE",
            "semantic_state": "PROPOSED",
            "effective_from": "2026-09-04T00:00:00Z",
            "payload": {
                "data_date": "2026-09-04",
                "activities": [
                    {
                        "code": "A1",
                        "name": "Access",
                        "planned_start": "2026-09-04",
                        "planned_finish": "2026-09-05",
                        "progress_basis": "PHYSICAL_EXECUTED",
                        "responsible_owner": "pm@test",
                    }
                ],
            },
        },
    )
    assert source.status_code == 201, source.text
    activated = activate_with_authority(
        client,
        f"/api/v1/projects/{project_id}/authorized-context/activate",
        headers=headers,
        json={
            "source_version_id": source.json()["id"],
            "approval_reference": "Other approval",
            "reason": "Independent approved context",
        },
    )
    assert activated.status_code == 201, activated.text
    authority = grant(client, project_id, headers, "CHANGE_APPROVAL")
    response = transition(
        client,
        project_id,
        record_id,
        headers,
        "APPROVED",
        version=1,
        key="approve",
        authority_grant_id=authority,
        authorized_context_source_version_id=source.json()["id"],
        approval_reference="Stale change",
    )
    assert response.status_code == 409, response.text


def test_context_rejects_unknown_or_cross_project_evidence_and_analyst_approval(context_api):
    client, _, project_id, headers = context_api
    assert (
        post_record(
            client,
            project_id,
            headers,
            record_payload("RISK", evidence_item_ids=[str(uuid.uuid4())]),
        ).status_code
        == 422
    )
    assert (
        post_record(
            client, project_id, headers, {**record_payload(), "record_key": "OTHER_CHARTER"}
        ).status_code
        == 422
    )
    membership = client.post(
        f"/api/v1/projects/{project_id}/memberships",
        headers=headers,
        json={"actor_id": "analyst@test", "role": "ANALYST_CONTROLLER"},
    )
    assert membership.status_code == 201
    created = post_record(client, project_id, headers, record_payload())
    denied = transition(
        client,
        project_id,
        created.json()["id"],
        {**headers, "X-VAI-Actor-ID": "analyst@test"},
        "REVIEWED",
    )
    assert denied.status_code == 403
