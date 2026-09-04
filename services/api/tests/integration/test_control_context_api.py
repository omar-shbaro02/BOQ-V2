from collections.abc import Generator
from typing import Any

import pytest
from app.database import Base, get_db
from app.main import app
from app.models import AuditEvent, AuthorizedContextVersion
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture
def api() -> Generator[tuple[TestClient, sessionmaker[Session]], None, None]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    test_sessions = sessionmaker(bind=engine, expire_on_commit=False)

    def override_db() -> Generator[Session, None, None]:
        with test_sessions() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        yield client, test_sessions
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)


def bootstrap_project(client: TestClient) -> tuple[str, str, dict[str, str]]:
    actor_id = "pm@example.test"
    organization = client.post(
        "/api/v1/organizations",
        headers={"X-VAI-Actor-ID": actor_id, "X-VAI-Roles": "ORGANIZATION_ADMIN"},
        json={"name": "VAI Contractor", "slug": "vai-contractor"},
    )
    assert organization.status_code == 201, organization.text
    organization_id = organization.json()["id"]
    headers = {"X-VAI-Actor-ID": actor_id, "X-VAI-Organization-ID": organization_id}
    project = client.post(
        f"/api/v1/organizations/{organization_id}/projects",
        headers=headers,
        json={
            "code": "PRJ-001",
            "name": "Pilot Project",
            "timezone": "Asia/Beirut",
            "currency": "USD",
            "delivery_model": "DESIGN_BID_BUILD",
            "reporting_cadence": "WEEKLY",
        },
    )
    assert project.status_code == 201, project.text
    return organization_id, project.json()["id"], headers


def test_project_boundary_and_controlled_object_graph(api: tuple[TestClient, Any]) -> None:
    client, _ = api
    _, project_id, headers = bootstrap_project(client)

    package = client.post(
        f"/api/v1/projects/{project_id}/controlled-objects",
        headers=headers,
        json={"object_type": "WORK_PACKAGE", "code": "WP-01", "name": "Blockwork"},
    )
    activity = client.post(
        f"/api/v1/projects/{project_id}/controlled-objects",
        headers=headers,
        json={"object_type": "ACTIVITY", "code": "ACT-010", "name": "Install blockwork"},
    )
    assert package.status_code == activity.status_code == 201

    relation = client.post(
        f"/api/v1/projects/{project_id}/relations",
        headers=headers,
        json={
            "source_id": package.json()["id"],
            "target_id": activity.json()["id"],
            "relation_type": "CONTAINS",
        },
    )
    assert relation.status_code == 201, relation.text
    objects = client.get(f"/api/v1/projects/{project_id}/controlled-objects", headers=headers)
    assert [item["code"] for item in objects.json()] == ["ACT-010", "WP-01"]

    grant = client.post(
        f"/api/v1/projects/{project_id}/authority-grants",
        headers=headers,
        json={
            "actor_id": "package-manager@example.test",
            "authority_type": "PACKAGE_DECISION",
            "controlled_object_id": package.json()["id"],
            "max_amount": "25000.00",
            "currency": "USD",
            "escalation_level": 1,
            "escalates_to_actor_id": "project-manager@example.test",
        },
    )
    assert grant.status_code == 201, grant.text
    assert grant.json()["escalation_level"] == 1


def test_authorized_context_activation_preserves_baseline_and_history(
    api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, sessions = api
    _, project_id, headers = bootstrap_project(client)
    baseline = client.post(
        f"/api/v1/projects/{project_id}/authorized-context/versions",
        headers=headers,
        json={
            "context_type": "SCHEDULE",
            "semantic_state": "BASELINE",
            "effective_from": "2026-09-01T00:00:00Z",
            "payload": {
                "data_date": "2026-09-01",
                "activities": [
                    {
                        "code": "ACT-010",
                        "name": "Install blockwork",
                        "planned_start": "2026-09-01",
                        "planned_finish": "2026-10-01",
                        "progress_basis": "PHYSICAL_EXECUTED",
                        "responsible_owner": "site-manager@example.test",
                    }
                ],
            },
        },
    )
    assert baseline.status_code == 201, baseline.text
    activated = client.post(
        f"/api/v1/projects/{project_id}/authorized-context/activate",
        headers=headers,
        json={
            "source_version_id": baseline.json()["id"],
            "approval_reference": "APPROVAL-001",
            "reason": "Initial authorized schedule",
        },
    )
    assert activated.status_code == 201, activated.text
    assert activated.json()["semantic_state"] == "CURRENT_AUTHORIZED"
    assert activated.json()["source_version_id"] == baseline.json()["id"]

    proposal = client.post(
        f"/api/v1/projects/{project_id}/authorized-context/versions",
        headers=headers,
        json={
            "context_type": "SCHEDULE",
            "semantic_state": "PROPOSED",
            "effective_from": "2026-09-15T00:00:00Z",
            "payload": {
                "data_date": "2026-09-15",
                "activities": [
                    {
                        "code": "ACT-010",
                        "name": "Install blockwork",
                        "planned_start": "2026-09-01",
                        "planned_finish": "2026-10-08",
                        "progress_basis": "PHYSICAL_EXECUTED",
                        "responsible_owner": "site-manager@example.test",
                    }
                ],
            },
        },
    )
    replacement = client.post(
        f"/api/v1/projects/{project_id}/authorized-context/activate",
        headers=headers,
        json={
            "source_version_id": proposal.json()["id"],
            "approval_reference": "CHANGE-007",
            "reason": "Approved time extension",
        },
    )
    assert replacement.status_code == 201, replacement.text

    with sessions() as session:
        versions = list(
            session.scalars(
                select(AuthorizedContextVersion).order_by(AuthorizedContextVersion.version_number)
            )
        )
        assert [version.semantic_state for version in versions] == [
            "BASELINE",
            "SUPERSEDED",
            "PROPOSED",
            "CURRENT_AUTHORIZED",
        ]
        assert versions[1].superseded_at is not None
        assert versions[3].approval_reference == "CHANGE-007"
        audit_actions = set(session.scalars(select(AuditEvent.action)))
        assert "AUTHORIZED_CONTEXT_ACTIVATED" in audit_actions

    current = client.get(
        f"/api/v1/projects/{project_id}/authorized-context/current/SCHEDULE",
        headers=headers,
    )
    assert current.status_code == 200
    assert current.json()["approval_reference"] == "CHANGE-007"
    project = client.post(f"/api/v1/projects/{project_id}/activate", headers=headers)
    assert project.status_code == 200
    assert project.json()["status"] == "ACTIVE"
    ledger = client.get(f"/api/v1/projects/{project_id}/audit-events", headers=headers)
    assert ledger.status_code == 200
    assert "PROJECT_ACTIVATED" in {event["action"] for event in ledger.json()}


def test_analyst_can_propose_but_cannot_activate(api: tuple[TestClient, Any]) -> None:
    client, _ = api
    _, project_id, admin_headers = bootstrap_project(client)
    membership = client.post(
        f"/api/v1/projects/{project_id}/memberships",
        headers=admin_headers,
        json={"actor_id": "analyst@example.test", "role": "ANALYST_CONTROLLER"},
    )
    assert membership.status_code == 201

    analyst_headers = {
        "X-VAI-Actor-ID": "analyst@example.test",
        "X-VAI-Organization-ID": admin_headers["X-VAI-Organization-ID"],
    }
    proposal = client.post(
        f"/api/v1/projects/{project_id}/authorized-context/versions",
        headers=analyst_headers,
        json={
            "context_type": "BUDGET",
            "semantic_state": "PROPOSED",
            "effective_from": "2026-09-01T00:00:00Z",
            "payload": {"currency": "USD", "approved_budget": "1000000.00"},
        },
    )
    assert proposal.status_code == 201, proposal.text
    denied = client.post(
        f"/api/v1/projects/{project_id}/authorized-context/activate",
        headers=analyst_headers,
        json={
            "source_version_id": proposal.json()["id"],
            "approval_reference": "UNAUTHORIZED-001",
            "reason": "Analyst attempted activation",
        },
    )
    assert denied.status_code == 403


def test_cross_organization_access_is_denied(api: tuple[TestClient, Any]) -> None:
    client, _ = api
    _, project_id, _ = bootstrap_project(client)
    response = client.get(
        f"/api/v1/projects/{project_id}",
        headers={
            "X-VAI-Actor-ID": "intruder@example.test",
            "X-VAI-Organization-ID": "11111111-1111-1111-1111-111111111111",
        },
    )
    assert response.status_code == 403


def test_project_activation_requires_authorized_schedule(api: tuple[TestClient, Any]) -> None:
    client, _ = api
    _, project_id, headers = bootstrap_project(client)
    response = client.post(f"/api/v1/projects/{project_id}/activate", headers=headers)
    assert response.status_code == 409


def test_schedule_payload_rejects_unknown_dependency(api: tuple[TestClient, Any]) -> None:
    client, _ = api
    _, project_id, headers = bootstrap_project(client)
    response = client.post(
        f"/api/v1/projects/{project_id}/authorized-context/versions",
        headers=headers,
        json={
            "context_type": "SCHEDULE",
            "semantic_state": "BASELINE",
            "effective_from": "2026-09-01T00:00:00Z",
            "payload": {
                "data_date": "2026-09-01",
                "activities": [
                    {
                        "code": "A",
                        "name": "Known activity",
                        "planned_start": "2026-09-01",
                        "planned_finish": "2026-09-02",
                        "progress_basis": "PHYSICAL_EXECUTED",
                        "responsible_owner": "owner@example.test",
                    }
                ],
                "dependencies": [{"predecessor_code": "A", "successor_code": "MISSING"}],
            },
        },
    )
    assert response.status_code == 422


def test_invalid_project_calendar_is_rejected(api: tuple[TestClient, Any]) -> None:
    client, _ = api
    actor_id = "calendar-admin@example.test"
    organization = client.post(
        "/api/v1/organizations",
        headers={"X-VAI-Actor-ID": actor_id, "X-VAI-Roles": "ORGANIZATION_ADMIN"},
        json={"name": "Calendar Org", "slug": "calendar-org"},
    )
    organization_id = organization.json()["id"]
    response = client.post(
        f"/api/v1/organizations/{organization_id}/projects",
        headers={"X-VAI-Actor-ID": actor_id, "X-VAI-Organization-ID": organization_id},
        json={
            "code": "BAD-CALENDAR",
            "name": "Bad Calendar",
            "timezone": "Asia/Beirut",
            "currency": "USD",
            "delivery_model": "DESIGN_BID_BUILD",
            "reporting_cadence": "WEEKLY",
            "calendar_config": {"working_weekdays": [0, 0], "hours_per_day": 8},
        },
    )
    assert response.status_code == 422
