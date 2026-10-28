from __future__ import annotations

import uuid
from collections.abc import Generator
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from app.database import Base, get_db
from app.main import app
from app.models import (
    AuditEvent,
    AuthorizedContextVersion,
    EvidenceItem,
    ProgressMeasurement,
    Project,
    ProjectControlSnapshot,
)
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
    sessions = sessionmaker(bind=engine, expire_on_commit=False)

    def override_db() -> Generator[Session, None, None]:
        with sessions() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    try:
        yield client, sessions
    finally:
        client.close()
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)


def bootstrap_project(client: TestClient, suffix: str = "one") -> tuple[str, str, dict[str, str]]:
    actor_id = f"pm-{suffix}@example.test"
    organization = client.post(
        "/api/v1/organizations",
        headers={"X-VAI-Actor-ID": actor_id, "X-VAI-Roles": "ORGANIZATION_ADMIN"},
        json={"name": f"Organization {suffix}", "slug": f"organization-{suffix}"},
    )
    assert organization.status_code == 201, organization.text
    organization_id = organization.json()["id"]
    headers = {"X-VAI-Actor-ID": actor_id, "X-VAI-Organization-ID": organization_id}
    project = client.post(
        f"/api/v1/organizations/{organization_id}/projects",
        headers=headers,
        json={
            "code": f"PRJ-{suffix.upper()}",
            "name": f"Project {suffix}",
            "timezone": "Asia/Beirut",
            "currency": "USD",
            "delivery_model": "DESIGN_BID_BUILD",
            "reporting_cadence": "WEEKLY",
        },
    )
    assert project.status_code == 201, project.text
    return organization_id, project.json()["id"], headers


def seed_control_inputs(
    client: TestClient,
    sessions: sessionmaker[Session],
    project_id: str,
    headers: dict[str, str],
) -> dict[str, Any]:
    package_ids: list[str] = []
    for code in ("WP-01", "WP-02"):
        response = client.post(
            f"/api/v1/projects/{project_id}/controlled-objects",
            headers=headers,
            json={"object_type": "WORK_PACKAGE", "code": code, "name": code},
        )
        assert response.status_code == 201, response.text
        package_ids.append(response.json()["id"])

    data_date = datetime.now(UTC).replace(microsecond=0) - timedelta(days=1)
    authorized_at = data_date - timedelta(days=30)
    weighting_id = uuid.uuid4()
    schedule_id = uuid.uuid4()
    planned_ids: list[uuid.UUID] = []
    actual_ids: list[uuid.UUID] = []
    with sessions() as session:
        project = session.get(Project, uuid.UUID(project_id))
        assert project is not None
        session.add_all(
            [
                AuthorizedContextVersion(
                    id=weighting_id,
                    organization_id=project.organization_id,
                    project_id=project.id,
                    context_type="PROGRESS_WEIGHTING",
                    version_number=1,
                    semantic_state="CURRENT_AUTHORIZED",
                    effective_from=authorized_at,
                    payload={
                        "data_date": authorized_at.date().isoformat(),
                        "weighting_basis": "BOQ_VALUE",
                        "measurement_basis": "PHYSICAL_VERIFIED",
                        "source_reference": "Approved BOQ allocation",
                        "entries": [
                            {"controlled_object_code": "WP-01", "weight": "0.6"},
                            {"controlled_object_code": "WP-02", "weight": "0.4"},
                        ],
                    },
                    created_by=headers["X-VAI-Actor-ID"],
                    approval_reference="APP-WEIGHTS-1",
                    activation_reason="Approved progress weighting",
                    activated_by=headers["X-VAI-Actor-ID"],
                    activated_at=authorized_at,
                ),
                AuthorizedContextVersion(
                    id=schedule_id,
                    organization_id=project.organization_id,
                    project_id=project.id,
                    context_type="SCHEDULE",
                    version_number=1,
                    semantic_state="CURRENT_AUTHORIZED",
                    effective_from=authorized_at,
                    payload={
                        "data_date": authorized_at.date().isoformat(),
                        "activities": [
                            {
                                "code": f"A{index + 1}",
                                "name": f"Package {index + 1}",
                                "controlled_object_code": f"WP-0{index + 1}",
                                "planned_start": authorized_at.date().isoformat(),
                                "planned_finish": data_date.date().isoformat(),
                                "progress_basis": "PHYSICAL_VERIFIED",
                                "responsible_owner": headers["X-VAI-Actor-ID"],
                                "progress_plan": [
                                    {
                                        "as_of": data_date.date().isoformat(),
                                        "measurement_basis": "PHYSICAL_VERIFIED",
                                        "numerator": numerator,
                                        "denominator": "100",
                                        "unit": "percent",
                                    }
                                ],
                            }
                            for index, numerator in enumerate(("50", "25"))
                        ],
                    },
                    created_by=headers["X-VAI-Actor-ID"],
                    approval_reference="APP-SCHEDULE-1",
                    activation_reason="Approved schedule",
                    activated_by=headers["X-VAI-Actor-ID"],
                    activated_at=authorized_at,
                ),
            ]
        )
        session.flush()
        ratios = ((Decimal("0.50"), Decimal("0.40")), (Decimal("0.25"), Decimal("0.10")))
        for index, (planned_ratio, actual_ratio) in enumerate(ratios):
            object_id = uuid.UUID(package_ids[index])
            planned_id = uuid.uuid4()
            actual_id = uuid.uuid4()
            planned_ids.append(planned_id)
            actual_ids.append(actual_id)
            planned_evidence_id, actual_evidence_id = uuid.uuid4(), uuid.uuid4()
            for evidence_id, ratio, state, truth, confidence in (
                (planned_evidence_id, planned_ratio, "CURRENT_AUTHORIZED", "ASSUMPTION", "1"),
                (
                    actual_evidence_id,
                    actual_ratio,
                    "VERIFIED",
                    "VERIFIED_FACT",
                    "0.8" if index == 0 else "0.9",
                ),
            ):
                session.add(
                    EvidenceItem(
                        id=evidence_id,
                        organization_id=project.organization_id,
                        project_id=project.id,
                        controlled_object_id=object_id,
                        field_name="package_progress",
                        value=str(ratio * 100),
                        unit="percent",
                        measurement_basis="PHYSICAL_VERIFIED",
                        semantic_state=state,
                        truth_type=truth,
                        as_of=data_date,
                        confidence=Decimal(confidence),
                        status="ACTIVE",
                        created_by=headers["X-VAI-Actor-ID"],
                    )
                )
            session.flush()
            session.add_all(
                [
                    ProgressMeasurement(
                        id=planned_id,
                        organization_id=project.organization_id,
                        project_id=project.id,
                        controlled_object_id=object_id,
                        evidence_item_id=planned_evidence_id,
                        authorized_context_id=schedule_id,
                        measurement_kind="PLANNED_AUTHORIZED",
                        measurement_basis="PHYSICAL_VERIFIED",
                        numerator=planned_ratio * 100,
                        denominator=Decimal("100"),
                        completion_ratio=planned_ratio,
                        unit="percent",
                        as_of=data_date,
                        semantic_state="CURRENT_AUTHORIZED",
                        truth_type="ASSUMPTION",
                        confidence=Decimal("1"),
                        recorded_by=headers["X-VAI-Actor-ID"],
                    ),
                    ProgressMeasurement(
                        id=actual_id,
                        organization_id=project.organization_id,
                        project_id=project.id,
                        controlled_object_id=object_id,
                        evidence_item_id=actual_evidence_id,
                        authorized_context_id=None,
                        measurement_kind="VERIFIED",
                        measurement_basis="PHYSICAL_VERIFIED",
                        numerator=actual_ratio * 100,
                        denominator=Decimal("100"),
                        completion_ratio=actual_ratio,
                        unit="percent",
                        as_of=data_date,
                        semantic_state="VERIFIED",
                        truth_type="VERIFIED_FACT",
                        confidence=Decimal("0.8") if index == 0 else Decimal("0.9"),
                        recorded_by=headers["X-VAI-Actor-ID"],
                    ),
                ]
            )
        session.commit()
    return {
        "data_date": data_date.isoformat().replace("+00:00", "Z"),
        "progress_weighting_context_id": str(weighting_id),
        "schedule_context_id": str(schedule_id),
        "packages": [
            {
                "controlled_object_id": package_ids[index],
                "planned_measurement_id": str(planned_ids[index]),
                "actual_measurement_id": str(actual_ids[index]),
            }
            for index in range(2)
        ],
    }


def test_weighted_project_control_snapshot_is_immutable_exact_and_idempotent(
    api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, sessions = api
    _, project_id, headers = bootstrap_project(client)
    body = seed_control_inputs(client, sessions, project_id, headers)
    url = f"/api/v1/projects/{project_id}/project-control/snapshots"
    request_headers = {**headers, "Idempotency-Key": "project-status-1"}

    created = client.post(url, headers=request_headers, json=body)
    assert created.status_code == 201, created.text
    payload = created.json()
    assert payload["snapshot_number"] == 1
    assert Decimal(payload["planned_ratio"]) == Decimal("0.4")
    assert Decimal(payload["actual_ratio"]) == Decimal("0.28")
    assert Decimal(payload["variance_ratio"]) == Decimal("-0.12")
    assert payload["progress_status"] == "BEHIND"
    assert payload["progress_policy_version"] == "PROGRESS-DEFAULT-1.0.0"
    assert Decimal(payload["confidence"]) == Decimal("0.8")
    assert payload["truth_type"] == "DERIVED_METRIC"
    assert payload["formula_version"] == "PROJECT-WEIGHTED-PROGRESS-1.1.0"
    assert {
        item["controlled_object_id"]
        for item in payload["limitations"]
        if item["code"] == "VERIFIED_NOT_ACCEPTED_RELEASED"
    } == {item["controlled_object_id"] for item in body["packages"]}
    assert len(payload["limitations"]) == 4
    assert payload["limitations"][-2:] == [
        {"code": "COST_POSITION_UNKNOWN"},
        {"code": "FORECAST_POSITION_UNKNOWN"},
    ]
    assert payload["cost_assessment_refs"] == []
    assert payload["forecast_projection_refs"] == []
    assert payload["package_exclusions"] == []
    assert payload["policy_versions"]["progress_weighting_context_version"] == 1

    replay = client.post(url, headers=request_headers, json=body)
    assert replay.status_code == 201
    assert replay.json()["id"] == payload["id"]
    changed = {**body, "packages": body["packages"][:-1]}
    mismatch = client.post(url, headers=request_headers, json=changed)
    assert mismatch.status_code == 409

    listed = client.get(url, headers=headers)
    detail = client.get(f"{url}/{payload['id']}", headers=headers)
    assert listed.status_code == detail.status_code == 200
    assert len(listed.json()) == 1
    assert detail.json()["request_hash"] == payload["request_hash"]
    with sessions() as session:
        assert session.scalar(select(ProjectControlSnapshot)) is not None
        assert "PROJECT_CONTROL_SNAPSHOT_CREATED" in set(session.scalars(select(AuditEvent.action)))

    reports_url = f"/api/v1/projects/{project_id}/decision-center/report-snapshots"
    report = client.post(
        reports_url,
        headers={**headers, "Idempotency-Key": "status-report-1"},
        json={
            "report_type": "ON_DEMAND_STATUS_REPORT",
            "project_control_snapshot_id": payload["id"],
        },
    )
    assert report.status_code == 201, report.text
    report_payload = report.json()
    assert report_payload["lifecycle_status"] == "DRAFT"
    assert report_payload["data_date"] == payload["data_date"]
    assert report_payload["payload"]["project_control"]["actual_ratio"] == "0.28000000"
    assert report_payload["fidelity_manifest"]["immutable_source_snapshot"] is True
    replay = client.post(
        reports_url,
        headers={**headers, "Idempotency-Key": "status-report-1"},
        json={
            "report_type": "ON_DEMAND_STATUS_REPORT",
            "project_control_snapshot_id": payload["id"],
        },
    )
    assert replay.status_code == 201
    assert replay.json()["id"] == report_payload["id"]
    approved_url = reports_url.replace("report-snapshots", "approved-report-snapshots")
    assert client.get(f"{approved_url}/{report_payload['id']}", headers=headers).status_code == 409

    lifecycle_url = f"{reports_url}/{report_payload['id']}/lifecycle-events"
    reviewed = client.post(
        lifecycle_url,
        headers=headers,
        json={"to_status": "REVIEWED", "reason": "Controller review complete"},
    )
    assert reviewed.status_code == 201, reviewed.text
    denied = client.post(
        lifecycle_url,
        headers=headers,
        json={"to_status": "APPROVED", "reason": "External issue"},
    )
    assert denied.status_code == 403
    grant = client.post(
        f"/api/v1/projects/{project_id}/authority-grants",
        headers=headers,
        json={"actor_id": headers["X-VAI-Actor-ID"], "authority_type": "REPORT_APPROVAL"},
    )
    assert grant.status_code == 201, grant.text
    approved = client.post(
        lifecycle_url,
        headers=headers,
        json={
            "to_status": "APPROVED",
            "reason": "Approved for external issue",
            "authority_grant_id": grant.json()["id"],
        },
    )
    assert approved.status_code == 201, approved.text
    issued = client.get(f"{approved_url}/{report_payload['id']}", headers=headers)
    assert issued.status_code == 200
    assert issued.json()["content_hash"] == report_payload["content_hash"]
    _, _, outsider_headers = bootstrap_project(client, "report-outsider")
    assert (
        client.get(f"{reports_url}/{report_payload['id']}", headers=outsider_headers).status_code
        == 403
    )


def test_project_control_snapshot_fails_closed_for_partial_weak_and_cross_tenant_inputs(
    api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, sessions = api
    _, project_id, headers = bootstrap_project(client, "owner")
    body = seed_control_inputs(client, sessions, project_id, headers)
    url = f"/api/v1/projects/{project_id}/project-control/snapshots"

    partial = {**body, "packages": body["packages"][:-1]}
    response = client.post(
        url,
        headers={**headers, "Idempotency-Key": "partial"},
        json=partial,
    )
    assert response.status_code == 422
    assert response.json()["detail"]["message"].startswith("Snapshot packages must exactly")

    stale_schedule_id = uuid.uuid4()
    with sessions() as session:
        project = session.get(Project, uuid.UUID(project_id))
        assert project is not None
        data_date = datetime.fromisoformat(body["data_date"].replace("Z", "+00:00"))
        session.add(
            AuthorizedContextVersion(
                id=stale_schedule_id,
                organization_id=project.organization_id,
                project_id=project.id,
                context_type="SCHEDULE",
                version_number=2,
                semantic_state="SUPERSEDED",
                effective_from=data_date - timedelta(days=60),
                payload={"data_date": data_date.date().isoformat(), "activities": []},
                created_by=headers["X-VAI-Actor-ID"],
                approval_reference="OLD-SCHEDULE",
                activation_reason="Historic schedule",
                activated_by=headers["X-VAI-Actor-ID"],
                activated_at=data_date - timedelta(days=60),
                superseded_at=data_date - timedelta(days=30),
            )
        )
        session.commit()
    stale_body = {**body, "schedule_context_id": str(stale_schedule_id)}
    response = client.post(
        url,
        headers={**headers, "Idempotency-Key": "stale-context"},
        json=stale_body,
    )
    assert response.status_code == 422
    assert "not current authorized" in response.json()["detail"]

    weak_id = uuid.uuid4()
    with sessions() as session:
        source = session.get(
            ProgressMeasurement, uuid.UUID(body["packages"][0]["actual_measurement_id"])
        )
        assert source is not None
        session.add(
            ProgressMeasurement(
                id=weak_id,
                organization_id=source.organization_id,
                project_id=source.project_id,
                controlled_object_id=source.controlled_object_id,
                evidence_item_id=uuid.uuid4(),
                authorized_context_id=None,
                measurement_kind="REPORTED",
                measurement_basis=source.measurement_basis,
                numerator=source.numerator,
                denominator=source.denominator,
                completion_ratio=source.completion_ratio,
                unit=source.unit,
                as_of=source.as_of,
                semantic_state="REPORTED",
                truth_type="REPORTED_CLAIM",
                confidence=source.confidence,
                recorded_by=source.recorded_by,
            )
        )
        session.commit()
    weak_body = {
        **body,
        "packages": [
            {**body["packages"][0], "actual_measurement_id": str(weak_id)},
            body["packages"][1],
        ],
    }
    response = client.post(
        url,
        headers={**headers, "Idempotency-Key": "weak"},
        json=weak_body,
    )
    assert response.status_code == 422
    assert "verified or accepted" in response.json()["detail"]

    other_organization, _, other_headers = bootstrap_project(client, "outsider")
    assert other_organization != headers["X-VAI-Organization-ID"]
    denied = client.get(url, headers=other_headers)
    assert denied.status_code == 403


@pytest.mark.parametrize("condition", ["mismatched-time", "previous-project-day", "future"])
def test_project_control_requires_one_exact_observation_on_project_reporting_day(api, condition):
    client, sessions = api
    _, project_id, headers = bootstrap_project(client, "observation-cutoff")
    body = seed_control_inputs(client, sessions, project_id, headers)
    zone = ZoneInfo("Asia/Beirut")
    original = datetime.fromisoformat(body["data_date"])
    midnight = datetime.combine(original.astimezone(zone).date(), time.min, tzinfo=zone)
    cutoff = (midnight + timedelta(minutes=30)).astimezone(UTC)
    body["data_date"] = cutoff.isoformat()
    observation = cutoff - timedelta(minutes=5)
    if condition == "previous-project-day":
        observation = (midnight - timedelta(minutes=5)).astimezone(UTC)
        # A UTC-only day comparison would silently accept these as the same reporting day.
        assert observation.date() == cutoff.date()
    elif condition == "future":
        observation = cutoff + timedelta(seconds=1)
    with sessions() as session:
        for package in body["packages"]:
            for kind in ("planned", "actual"):
                measurement = session.get(
                    ProgressMeasurement, uuid.UUID(package[f"{kind}_measurement_id"])
                )
                measurement.as_of = observation + (
                    timedelta(seconds=1)
                    if condition == "mismatched-time" and kind == "actual"
                    else timedelta(0)
                )
        session.commit()
    response = client.post(
        f"/api/v1/projects/{project_id}/project-control/snapshots",
        headers={**headers, "Idempotency-Key": condition},
        json=body,
    )
    assert response.status_code == 422, response.text
    assert "exact observation time on the snapshot reporting day" in response.json()["detail"]
