import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from app.database import Base, get_db
from app.main import app
from app.models import (
    AuthorizedContextVersion,
    CaseLedgerEvent,
    CaseSnapshot,
    CaseSufficiencyAssessment,
    CostAssessment,
    ForecastProjection,
    ProgressEvaluation,
    ScheduleAssessment,
)
from app.storage import LocalEvidenceStore, get_evidence_store
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture
def case_api(
    tmp_path: Path,
) -> Generator[tuple[TestClient, sessionmaker[Session]], None, None]:
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
    app.dependency_overrides[get_evidence_store] = lambda: LocalEvidenceStore(tmp_path)
    with TestClient(app) as client:
        yield client, sessions
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)


def bootstrap(client: TestClient) -> tuple[str, str, dict[str, str], str]:
    marker = uuid.uuid4().hex[:8]
    actor = f"case-admin-{marker}@example.test"
    organization = client.post(
        "/api/v1/organizations",
        headers={"X-VAI-Actor-ID": actor, "X-VAI-Roles": "ORGANIZATION_ADMIN"},
        json={"name": "Case Org", "slug": f"case-org-{marker}"},
    )
    organization_id = organization.json()["id"]
    headers = {"X-VAI-Actor-ID": actor, "X-VAI-Organization-ID": organization_id}
    project = client.post(
        f"/api/v1/organizations/{organization_id}/projects",
        headers=headers,
        json={
            "code": f"CASE-{marker}",
            "name": "Case Pilot",
            "timezone": "Asia/Beirut",
            "currency": "USD",
            "delivery_model": "DESIGN_BID_BUILD",
            "reporting_cadence": "WEEKLY",
        },
    )
    project_id = project.json()["id"]
    controlled_object = client.post(
        f"/api/v1/projects/{project_id}/controlled-objects",
        headers=headers,
        json={"object_type": "WORK_PACKAGE", "code": "WP-CASE", "name": "Case package"},
    )
    return organization_id, project_id, headers, controlled_object.json()["id"]


def add_evidence(
    client: TestClient,
    project_id: str,
    headers: dict[str, str],
    object_id: str,
    *,
    field: str = "schedule_variance_days",
    value: Any = 8,
    expires_at: datetime | None = None,
    as_of: datetime | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "controlled_object_id": object_id,
        "field_name": field,
        "value": value,
        "semantic_state": "REPORTED",
        "truth_type": "REPORTED_CLAIM",
        "as_of": (as_of or datetime.now(UTC)).isoformat(),
        "confidence": "0.70",
    }
    if "progress" in field:
        payload["measurement_basis"] = "PHYSICAL_VERIFIED"
    if expires_at:
        payload["expires_at"] = expires_at.isoformat()
    response = client.post(
        f"/api/v1/projects/{project_id}/evidence/items", headers=headers, json=payload
    )
    assert response.status_code == 201, response.text
    return response.json()


def progress_evidence(
    client: TestClient,
    project_id: str,
    headers: dict[str, str],
    object_id: str,
    *,
    value: str,
    as_of: datetime,
    basis: str,
    semantic_state: str,
    truth_type: str,
    field: str,
) -> dict[str, Any]:
    response = client.post(
        f"/api/v1/projects/{project_id}/evidence/items",
        headers=headers,
        json={
            "controlled_object_id": object_id,
            "field_name": field,
            "value": value,
            "unit": "%",
            "measurement_basis": basis,
            "semantic_state": semantic_state,
            "truth_type": truth_type,
            "as_of": as_of.isoformat(),
            "confidence": "0.90" if truth_type == "VERIFIED_FACT" else "0.65",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def normalize_progress(
    client: TestClient,
    project_id: str,
    headers: dict[str, str],
    evidence: dict[str, Any],
    *,
    kind: str,
    denominator: str = "100",
    context_id: str | None = None,
) -> dict[str, Any]:
    response = client.post(
        f"/api/v1/projects/{project_id}/progress/measurements",
        headers=headers,
        json={
            "evidence_item_id": evidence["id"],
            "authorized_context_id": context_id,
            "measurement_kind": kind,
            "numerator": evidence["value"],
            "denominator": denominator,
            "unit": "%",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def activate_progress_schedule(
    client: TestClient,
    project_id: str,
    headers: dict[str, str],
    points: list[tuple[datetime, str]],
) -> dict[str, Any]:
    source = client.post(
        f"/api/v1/projects/{project_id}/authorized-context/versions",
        headers=headers,
        json={
            "context_type": "SCHEDULE",
            "semantic_state": "BASELINE",
            "effective_from": (min(value[0] for value in points) - timedelta(days=1)).isoformat(),
            "payload": {
                "data_date": min(value[0] for value in points).date().isoformat(),
                "activities": [
                    {
                        "code": "A-PROGRESS",
                        "name": "Progress-controlled activity",
                        "planned_start": min(value[0] for value in points).date().isoformat(),
                        "planned_finish": (max(value[0] for value in points) + timedelta(days=30))
                        .date()
                        .isoformat(),
                        "progress_basis": "PHYSICAL_VERIFIED",
                        "responsible_owner": headers["X-VAI-Actor-ID"],
                        "controlled_object_code": "WP-CASE",
                        "progress_plan": [
                            {
                                "as_of": date.date().isoformat(),
                                "numerator": numerator,
                                "denominator": "100",
                                "unit": "%",
                                "measurement_basis": "PHYSICAL_VERIFIED",
                            }
                            for date, numerator in points
                        ],
                    }
                ],
            },
        },
    )
    assert source.status_code == 201, source.text
    activated = client.post(
        f"/api/v1/projects/{project_id}/authorized-context/activate",
        headers=headers,
        json={
            "source_version_id": source.json()["id"],
            "approval_reference": "PROGRESS-PLAN-APPROVAL",
            "reason": "Authorize the time-phased progress plan",
        },
    )
    assert activated.status_code == 201, activated.text
    return activated.json()


def schedule_delay_evidence(
    client: TestClient,
    project_id: str,
    headers: dict[str, str],
    object_id: str,
    *,
    delay_days: str,
    semantic_state: str = "VERIFIED",
    truth_type: str = "VERIFIED_FACT",
) -> dict[str, Any]:
    response = client.post(
        f"/api/v1/projects/{project_id}/evidence/items",
        headers=headers,
        json={
            "controlled_object_id": object_id,
            "field_name": "delay_days",
            "value": delay_days,
            "unit": "days",
            "semantic_state": semantic_state,
            "truth_type": truth_type,
            "as_of": datetime.now(UTC).isoformat(),
            "confidence": "0.92" if truth_type == "VERIFIED_FACT" else "0.60",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def activate_schedule_network(
    client: TestClient,
    project_id: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    *,
    state: str = "BASELINE",
    approval: str = "SCHEDULE-NETWORK-APPROVAL",
) -> dict[str, Any]:
    source = client.post(
        f"/api/v1/projects/{project_id}/authorized-context/versions",
        headers=headers,
        json={
            "context_type": "SCHEDULE",
            "semantic_state": state,
            "effective_from": (datetime.now(UTC) - timedelta(days=1)).isoformat(),
            "payload": payload,
        },
    )
    assert source.status_code == 201, source.text
    activated = client.post(
        f"/api/v1/projects/{project_id}/authorized-context/activate",
        headers=headers,
        json={
            "source_version_id": source.json()["id"],
            "approval_reference": approval,
            "reason": "Authorize validated schedule network for case assessment",
        },
    )
    assert activated.status_code == 201, activated.text
    return activated.json()


def schedule_payload(
    *,
    source_float: str | None = None,
    successor_gap_days: int | None = None,
    network_complete: bool = True,
    data_date: datetime | None = None,
) -> dict[str, Any]:
    origin = datetime.now(UTC).date()
    source_finish = origin + timedelta(days=5)
    activities: list[dict[str, Any]] = [
        {
            "code": "A-SOURCE",
            "name": "Source activity",
            "planned_start": origin.isoformat(),
            "planned_finish": source_finish.isoformat(),
            "progress_basis": "PHYSICAL_EXECUTED",
            "responsible_owner": "source-owner@example.test",
            "controlled_object_code": "WP-CASE",
            "calendar_id": "SITE-6D",
            "total_float_days": source_float,
        }
    ]
    dependencies: list[dict[str, Any]] = []
    milestones: list[dict[str, Any]] = []
    if successor_gap_days is None and source_float is not None:
        activities.append(
            {
                "code": "Z-INDEPENDENT-COMPLETION",
                "name": "Independent later completion path",
                "planned_start": (origin + timedelta(days=30)).isoformat(),
                "planned_finish": (origin + timedelta(days=40)).isoformat(),
                "progress_basis": "PHYSICAL_EXECUTED",
                "responsible_owner": "other-owner@example.test",
                "calendar_id": "SITE-6D",
            }
        )
    if successor_gap_days is not None:
        successor_start = source_finish + timedelta(days=successor_gap_days)
        activities.append(
            {
                "code": "B-MILESTONE",
                "name": "Downstream milestone activity",
                "planned_start": successor_start.isoformat(),
                "planned_finish": (successor_start + timedelta(days=5)).isoformat(),
                "progress_basis": "PHYSICAL_EXECUTED",
                "responsible_owner": "downstream-owner@example.test",
                "calendar_id": "SITE-6D",
            }
        )
        dependencies.append(
            {
                "predecessor_code": "A-SOURCE",
                "successor_code": "B-MILESTONE",
                "relation_type": "FINISH_TO_START",
                "lag_days": "0",
            }
        )
        milestones.append(
            {
                "code": "M-HANDOVER",
                "name": "Material handover milestone",
                "planned_date": (successor_start + timedelta(days=5)).isoformat(),
                "activity_code": "B-MILESTONE",
                "material": True,
            }
        )
    return {
        "data_date": (data_date or datetime.now(UTC)).date().isoformat(),
        "network_complete": network_complete,
        "calendars": [
            {
                "calendar_id": "SITE-6D",
                "name": "Six-day site calendar",
                "working_weekdays": [0, 1, 2, 3, 4, 5],
                "holidays": [],
            }
        ],
        "activities": activities,
        "dependencies": dependencies,
        "constraints": [
            {
                "activity_code": "A-SOURCE",
                "constraint_type": "START_NO_EARLIER_THAN",
                "constraint_date": origin.isoformat(),
            }
        ],
        "milestones": milestones,
    }


def assess_schedule_case(
    client: TestClient,
    project_id: str,
    headers: dict[str, str],
    case: dict[str, Any],
    frozen: dict[str, Any],
    object_id: str,
    evidence_id: str,
    key: str,
    policy_version: str = "SCHEDULE-DEFAULT-1.0.0",
) -> dict[str, Any]:
    response = client.post(
        f"/api/v1/projects/{project_id}/decision-cases/{case['id']}/schedule-assessments",
        headers={**headers, "Idempotency-Key": key},
        json={
            "expected_version": frozen["case"]["version"],
            "snapshot_id": frozen["snapshot"]["id"],
            "controlled_object_id": object_id,
            "activity_code": "A-SOURCE",
            "delay_evidence_item_id": evidence_id,
            "policy_version": policy_version,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def activate_budget(
    client: TestClient,
    project_id: str,
    headers: dict[str, str],
    *,
    approved: str = "100",
    changes: str = "0",
) -> dict[str, Any]:
    now = datetime.now(UTC)
    source = client.post(
        f"/api/v1/projects/{project_id}/authorized-context/versions",
        headers=headers,
        json={
            "context_type": "BUDGET",
            "semantic_state": "BASELINE",
            "effective_from": (now - timedelta(days=1)).isoformat(),
            "payload": {
                "currency": "USD",
                "approved_budget": approved,
                "authorized_changes": changes,
                "data_date": now.date().isoformat(),
                "reporting_period_start": now.date().replace(day=1).isoformat(),
                "reporting_period_end": now.date().isoformat(),
                "controlled_object_code": "WP-CASE",
                "measurement_basis": "COST_VALUE",
            },
        },
    )
    assert source.status_code == 201, source.text
    activated = client.post(
        f"/api/v1/projects/{project_id}/authorized-context/activate",
        headers=headers,
        json={
            "source_version_id": source.json()["id"],
            "approval_reference": "BUDGET-APPROVAL-1",
            "reason": "Authorize cost control budget",
        },
    )
    assert activated.status_code == 201, activated.text
    return activated.json()


def cost_record(
    client: TestClient,
    project_id: str,
    headers: dict[str, str],
    object_id: str,
    *,
    kind: str,
    amount: str,
    effect: str = "NONE",
    explanation: str | None = None,
    currency: str = "USD",
    truth_type: str = "VERIFIED_FACT",
    context_id: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    now = datetime.now(UTC)
    fields = {
        "ACTUAL": "actual_cost",
        "ACCRUAL": "accrual",
        "COMMITMENT": "commitment",
        "EARNED_VALUE": "earned_value",
        "PHYSICAL_VALUE": "physical_value",
        "BOQ_VALUE": "boq_value",
    }
    evidence = client.post(
        f"/api/v1/projects/{project_id}/evidence/items",
        headers=headers,
        json={
            "controlled_object_id": object_id,
            "field_name": fields[kind],
            "value": amount,
            "unit": currency,
            "measurement_basis": "COST_VALUE",
            "semantic_state": "VERIFIED" if truth_type == "VERIFIED_FACT" else "REPORTED",
            "truth_type": truth_type,
            "as_of": now.isoformat(),
            "confidence": "0.92" if truth_type == "VERIFIED_FACT" else "0.60",
        },
    )
    assert evidence.status_code == 201, evidence.text
    record = client.post(
        f"/api/v1/projects/{project_id}/cost/records",
        headers=headers,
        json={
            "evidence_item_id": evidence.json()["id"],
            "authorized_context_id": context_id,
            "record_kind": kind,
            "amount": amount,
            "currency": currency,
            "measurement_basis": "COST_VALUE",
            "reporting_period_start": now.date().replace(day=1).isoformat(),
            "reporting_period_end": now.date().isoformat(),
            "commercial_effect": effect,
            "effect_explanation": explanation,
        },
    )
    assert record.status_code == 201, record.text
    return evidence.json(), record.json()


def assess_cost_case(
    client: TestClient,
    project_id: str,
    headers: dict[str, str],
    case: dict[str, Any],
    frozen: dict[str, Any],
    object_id: str,
    record_ids: list[str],
    key: str,
) -> dict[str, Any]:
    response = client.post(
        f"/api/v1/projects/{project_id}/decision-cases/{case['id']}/cost-assessments",
        headers={**headers, "Idempotency-Key": key},
        json={
            "expected_version": frozen["case"]["version"],
            "snapshot_id": frozen["snapshot"]["id"],
            "controlled_object_id": object_id,
            "cost_record_ids": record_ids,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def prepare_production_forecast_case(
    client: TestClient,
    sessions: sessionmaker[Session],
    project_id: str,
    headers: dict[str, str],
    object_id: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], str]:
    current = datetime.now(UTC)
    prior = current - timedelta(days=7)
    context = activate_progress_schedule(
        client, project_id, headers, [(prior, "20"), (current, "40")]
    )
    with sessions() as session:
        stored = session.get(AuthorizedContextVersion, uuid.UUID(context["id"]))
        stored.activated_at = prior - timedelta(days=1)
        session.commit()
    planned_measurements = []
    actual_measurements = []
    evidence_ids = []
    for index, (as_of, planned_value, actual_value) in enumerate(
        [(prior, "20", "10"), (current, "40", "30")]
    ):
        planned_evidence = progress_evidence(
            client,
            project_id,
            headers,
            object_id,
            value=planned_value,
            as_of=as_of,
            basis="PHYSICAL_VERIFIED",
            semantic_state="CURRENT_AUTHORIZED",
            truth_type="VERIFIED_FACT",
            field=f"planned_progress_quantity_{index}",
        )
        actual_evidence = progress_evidence(
            client,
            project_id,
            headers,
            object_id,
            value=actual_value,
            as_of=as_of,
            basis="PHYSICAL_VERIFIED",
            semantic_state="VERIFIED",
            truth_type="VERIFIED_FACT",
            field=f"verified_progress_quantity_{index}",
        )
        planned_measurements.append(
            normalize_progress(
                client,
                project_id,
                headers,
                planned_evidence,
                kind="PLANNED_AUTHORIZED",
                context_id=context["id"],
            )
        )
        actual_measurements.append(
            normalize_progress(client, project_id, headers, actual_evidence, kind="VERIFIED")
        )
        evidence_ids.extend([planned_evidence["id"], actual_evidence["id"]])
    signal_source = add_evidence(client, project_id, headers, object_id)
    case = open_case(client, project_id, headers, signal_source, "production-forecast")
    case = attach(client, project_id, headers, case, evidence_ids)
    response = client.post(
        f"/api/v1/projects/{project_id}/decision-cases/{case['id']}/active-responses",
        headers=headers,
        json={
            "expected_version": case["version"],
            "response_type": "AUTHORIZED_PRODUCTIVITY_RECOVERY",
            "authorization_reference": "RECOVERY-RATE-1",
            "owner_actor_id": headers["X-VAI-Actor-ID"],
            "status": "ACTIVE",
            "effective_from": (prior - timedelta(days=1)).isoformat(),
            "details": {"productivity_multiplier": "1.5"},
        },
    )
    assert response.status_code == 200, response.text
    case = response.json()["case"]
    frozen = snapshot(
        client,
        project_id,
        headers,
        case,
        "production-forecast-snapshot",
        current + timedelta(seconds=2),
    )
    evaluated = client.post(
        f"/api/v1/projects/{project_id}/decision-cases/{case['id']}/progress-evaluations",
        headers={**headers, "Idempotency-Key": "production-forecast-evaluation"},
        json={
            "expected_version": frozen["case"]["version"],
            "snapshot_id": frozen["snapshot"]["id"],
            "planned_measurement_id": planned_measurements[1]["id"],
            "actual_measurement_id": actual_measurements[1]["id"],
            "prior_planned_measurement_id": planned_measurements[0]["id"],
            "prior_actual_measurement_id": actual_measurements[0]["id"],
        },
    )
    assert evaluated.status_code == 201, evaluated.text
    return (
        evaluated.json()["case"],
        frozen,
        evaluated.json()["evaluation"],
        response.json()["response"]["id"],
    )


def open_case(
    client: TestClient,
    project_id: str,
    headers: dict[str, str],
    source_evidence: dict[str, Any],
    marker: str,
) -> dict[str, Any]:
    detected = client.post(
        f"/api/v1/projects/{project_id}/signals/detect",
        headers={**headers, "Idempotency-Key": f"case-detect-{marker}"},
        json={"evidence_item_ids": [source_evidence["id"]], "contradiction_ids": []},
    )
    assert detected.status_code == 201, detected.text
    signal = detected.json()["signals"][0]
    screened = client.post(
        f"/api/v1/projects/{project_id}/signals/{signal['id']}/screen",
        headers=headers,
        json={
            "expected_version": signal["workflow_version"],
            "outcome": "RELEVANT",
            "reason_code": "MATERIAL_THRESHOLD_CROSSED",
            "rationale": "Create a governed evidence-assembly case",
            "materiality_candidate": signal["materiality_candidate"],
        },
    )
    signal = screened.json()["signal"]
    suggestion = client.post(
        f"/api/v1/projects/{project_id}/signals/{signal['id']}/correlation-suggestion",
        headers=headers,
    ).json()
    reviewed = client.post(
        f"/api/v1/projects/{project_id}/correlation-suggestions/{suggestion['id']}/review",
        headers=headers,
        json={
            "expected_signal_version": signal["workflow_version"],
            "status": "ACCEPTED",
            "selected_outcome": "OPEN_NEW",
            "case_title": f"Decision case {marker}",
            "case_owner_actor_id": headers["X-VAI-Actor-ID"],
            "rationale": "Reviewer confirmed a distinct management condition",
        },
    )
    assert reviewed.status_code == 200, reviewed.text
    return reviewed.json()["case"]


def activate_schedule(
    client: TestClient, project_id: str, headers: dict[str, str]
) -> dict[str, Any]:
    baseline = client.post(
        f"/api/v1/projects/{project_id}/authorized-context/versions",
        headers=headers,
        json={
            "context_type": "SCHEDULE",
            "semantic_state": "BASELINE",
            "effective_from": (datetime.now(UTC) - timedelta(days=1)).isoformat(),
            "payload": {
                "data_date": datetime.now(UTC).date().isoformat(),
                "activities": [
                    {
                        "code": "A-1",
                        "name": "Case activity",
                        "planned_start": datetime.now(UTC).date().isoformat(),
                        "planned_finish": (datetime.now(UTC) + timedelta(days=10))
                        .date()
                        .isoformat(),
                        "progress_basis": "PHYSICAL_EXECUTED",
                        "responsible_owner": "owner@example.test",
                    }
                ],
            },
        },
    )
    activated = client.post(
        f"/api/v1/projects/{project_id}/authorized-context/activate",
        headers=headers,
        json={
            "source_version_id": baseline.json()["id"],
            "approval_reference": "SCH-APPROVAL-1",
            "reason": "Approved schedule for sufficiency test",
        },
    )
    assert activated.status_code == 201, activated.text
    return activated.json()


def attach(
    client: TestClient,
    project_id: str,
    headers: dict[str, str],
    case: dict[str, Any],
    evidence_ids: list[str],
) -> dict[str, Any]:
    response = client.post(
        f"/api/v1/projects/{project_id}/decision-cases/{case['id']}/evidence",
        headers=headers,
        json={
            "expected_version": case["version"],
            "evidence_item_ids": evidence_ids,
            "attachment_reason": "Decision-critical case evidence",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["case"]


def snapshot(
    client: TestClient,
    project_id: str,
    headers: dict[str, str],
    case: dict[str, Any],
    key: str,
    data_date: datetime | None = None,
) -> dict[str, Any]:
    response = client.post(
        f"/api/v1/projects/{project_id}/decision-cases/{case['id']}/snapshots",
        headers={**headers, "Idempotency-Key": key},
        json={
            "expected_version": case["version"],
            "data_date": (data_date or datetime.now(UTC) + timedelta(seconds=2)).isoformat(),
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_snapshot_sufficiency_active_response_and_forward_lifecycle(
    case_api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, sessions = case_api
    _, project_id, headers, object_id = bootstrap(client)
    source = add_evidence(client, project_id, headers, object_id)
    case = open_case(client, project_id, headers, source, "complete")
    verified = client.post(
        f"/api/v1/projects/{project_id}/evidence/items/{source['id']}/verify",
        headers=headers,
        json={
            "method": "Planner validation",
            "outcome": "VERIFIED",
            "rationale": "Checked against current accepted programme",
            "verified_confidence": "0.95",
        },
    ).json()
    case = attach(client, project_id, headers, case, [verified["result_item_id"]])
    activated = activate_schedule(client, project_id, headers)
    response = client.post(
        f"/api/v1/projects/{project_id}/decision-cases/{case['id']}/active-responses",
        headers=headers,
        json={
            "expected_version": case["version"],
            "response_type": "RECOVERY_PLAN",
            "authorization_reference": "RECOVERY-AUTH-7",
            "owner_actor_id": headers["X-VAI-Actor-ID"],
            "effective_from": (datetime.now(UTC) - timedelta(minutes=1)).isoformat(),
            "details": {"note": "Approved recovery is already active"},
        },
    )
    assert response.status_code == 200, response.text
    case = response.json()["case"]
    snap = snapshot(client, project_id, headers, case, "complete-snapshot")
    assert snap["snapshot"]["baseline_validity"] == "VALID"
    assert snap["snapshot"]["authorized_context_refs"][0]["id"] == activated["id"]
    assert len(snap["snapshot"]["active_response_ids"]) == 1
    repeated = client.post(
        f"/api/v1/projects/{project_id}/decision-cases/{case['id']}/snapshots",
        headers={**headers, "Idempotency-Key": "complete-snapshot"},
        json={
            "expected_version": case["version"],
            "data_date": f"{snap['snapshot']['data_date']}Z",
        },
    )
    assert repeated.status_code == 201
    assert repeated.json()["snapshot"]["id"] == snap["snapshot"]["id"]

    case = snap["case"]
    sufficiency = client.post(
        f"/api/v1/projects/{project_id}/decision-cases/{case['id']}/sufficiency-assessments",
        headers=headers,
        json={
            "expected_version": case["version"],
            "snapshot_id": snap["snapshot"]["id"],
            "conclusion_type": "SCHEDULE_INTERVENTION",
            "gap_owner_actor_id": "planner@example.test",
            "gap_due_at": (datetime.now(UTC) + timedelta(days=2)).isoformat(),
        },
    )
    assert sufficiency.status_code == 201, sufficiency.text
    assert sufficiency.json()["assessment"]["readiness"] == "DECISION_READY_WITH_LIMITATIONS"
    assert sufficiency.json()["limitations"][0]["code"] == "ACTIVE_RESPONSE_UNASSESSED"
    case = sufficiency.json()["case"]
    for target in ("EVIDENCE_ASSEMBLY", "ANALYSIS", "REVIEW", "DECISION_READY"):
        moved = client.post(
            f"/api/v1/projects/{project_id}/decision-cases/{case['id']}/transition",
            headers=headers,
            json={
                "expected_version": case["version"],
                "target_lifecycle": target,
                "reason": f"Advance to {target}",
            },
        )
        assert moved.status_code == 200, moved.text
        case = moved.json()
    assert case["lifecycle"] == "DECISION_READY"
    ledger = client.get(
        f"/api/v1/projects/{project_id}/decision-cases/{case['id']}/ledger",
        headers=headers,
    ).json()
    assert ledger[0]["event_type"] == "CASE_OPENED"
    assert {event["event_type"] for event in ledger} >= {
        "EVIDENCE_ATTACHED",
        "RESPONSE_LINKED",
        "SNAPSHOT_CREATED",
        "SUFFICIENCY_ASSESSED",
        "LIFECYCLE_TRANSITIONED",
    }
    with sessions() as session:
        stored_snapshot = session.get(CaseSnapshot, uuid.UUID(snap["snapshot"]["id"]))
        assert len(stored_snapshot.snapshot_hash) == 64
        assert session.scalar(select(CaseSufficiencyAssessment.id)) is not None


def test_missing_context_and_weak_truth_stop_analysis_with_exact_gap(
    case_api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = case_api
    _, project_id, headers, object_id = bootstrap(client)
    evidence = add_evidence(client, project_id, headers, object_id)
    case = open_case(client, project_id, headers, evidence, "insufficient")
    case = attach(client, project_id, headers, case, [evidence["id"]])
    snap = snapshot(client, project_id, headers, case, "missing-context")
    assessed = client.post(
        f"/api/v1/projects/{project_id}/decision-cases/{case['id']}/sufficiency-assessments",
        headers=headers,
        json={
            "expected_version": snap["case"]["version"],
            "snapshot_id": snap["snapshot"]["id"],
            "conclusion_type": "SCHEDULE_INTERVENTION",
            "gap_owner_actor_id": "planner@example.test",
            "gap_due_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
        },
    )
    assert assessed.status_code == 201, assessed.text
    body = assessed.json()
    assert body["assessment"]["readiness"] == "INSUFFICIENT"
    assert body["assessment"]["maximum_supported_conclusion"] == "VERIFY_EVIDENCE"
    assert body["assessment"]["weak_evidence_ids"] == [evidence["id"]]
    assert "MISSING_AUTHORIZED_CONTEXT" in {
        limitation["code"] for limitation in body["limitations"]
    }
    assert body["evidence_requests"][0]["owner_actor_id"] == "planner@example.test"
    case = body["case"]
    opened_assembly = client.post(
        f"/api/v1/projects/{project_id}/decision-cases/{case['id']}/transition",
        headers=headers,
        json={
            "expected_version": case["version"],
            "target_lifecycle": "EVIDENCE_ASSEMBLY",
            "reason": "Begin gap closure",
        },
    ).json()
    blocked = client.post(
        f"/api/v1/projects/{project_id}/decision-cases/{case['id']}/transition",
        headers=headers,
        json={
            "expected_version": opened_assembly["version"],
            "target_lifecycle": "ANALYSIS",
            "reason": "Unsafe advance attempt",
        },
    )
    assert blocked.status_code == 409


def test_baseline_challenge_and_material_contradiction_require_verification(
    case_api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = case_api
    _, project_id, headers, object_id = bootstrap(client)
    left = add_evidence(client, project_id, headers, object_id, value=8)
    right = add_evidence(client, project_id, headers, object_id, value=14)
    contradiction = client.post(
        f"/api/v1/projects/{project_id}/evidence/contradictions",
        headers=headers,
        json={
            "left_item_id": left["id"],
            "right_item_id": right["id"],
            "field_name": "schedule_variance_days",
            "material": True,
        },
    )
    assert contradiction.status_code == 201
    case = open_case(client, project_id, headers, left, "challenge")
    case = attach(client, project_id, headers, case, [left["id"], right["id"]])
    activate_schedule(client, project_id, headers)
    snap = snapshot(client, project_id, headers, case, "challenged-baseline")
    challenged = client.post(
        f"/api/v1/projects/{project_id}/decision-cases/{case['id']}/baseline-assessments",
        headers=headers,
        json={
            "expected_version": snap["case"]["version"],
            "snapshot_id": snap["snapshot"]["id"],
            "validity": "DISPUTED",
            "rationale": "Planner disputes the logic quality at the case data date",
        },
    )
    assert challenged.status_code == 201, challenged.text
    assessed = client.post(
        f"/api/v1/projects/{project_id}/decision-cases/{case['id']}/sufficiency-assessments",
        headers=headers,
        json={
            "expected_version": challenged.json()["case"]["version"],
            "snapshot_id": snap["snapshot"]["id"],
            "conclusion_type": "SCHEDULE_INTERVENTION",
            "gap_owner_actor_id": "planner@example.test",
            "gap_due_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
        },
    )
    assert assessed.status_code == 201, assessed.text
    assert assessed.json()["assessment"]["readiness"] == "VERIFICATION_REQUIRED"
    assert assessed.json()["assessment"]["contradictory_evidence"][0]["material"] is True
    codes = {value["code"] for value in assessed.json()["limitations"]}
    assert {"INVALID_BASELINE", "UNRESOLVED_CONTRADICTION", "WEAK_TRUTH_SUPPORT"} <= codes


def test_block_resume_close_and_material_evidence_reopen_are_guarded(
    case_api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, sessions = case_api
    _, project_id, headers, object_id = bootstrap(client)
    evidence = add_evidence(client, project_id, headers, object_id)
    case = open_case(client, project_id, headers, evidence, "governance")
    blocked = client.post(
        f"/api/v1/projects/{project_id}/decision-cases/{case['id']}/block",
        headers=headers,
        json={
            "expected_version": case["version"],
            "blocker_code": "OWNER_UNAVAILABLE",
            "blocker_description": "Accountable owner unavailable for evidence review",
        },
    )
    assert blocked.json()["governance_state"] == "GOVERNANCE_BLOCKED"
    stale_resume = client.post(
        f"/api/v1/projects/{project_id}/decision-cases/{case['id']}/resume",
        headers=headers,
        json={"expected_version": case["version"], "reason": "Stale resume"},
    )
    assert stale_resume.status_code == 409
    resumed = client.post(
        f"/api/v1/projects/{project_id}/decision-cases/{case['id']}/resume",
        headers=headers,
        json={
            "expected_version": blocked.json()["version"],
            "reason": "Accountable owner is available",
        },
    )
    assert resumed.json()["lifecycle"] == "OPEN"
    missing_basis = client.post(
        f"/api/v1/projects/{project_id}/decision-cases/{case['id']}/close",
        headers=headers,
        json={"expected_version": resumed.json()["version"]},
    )
    assert missing_basis.status_code == 422
    closed = client.post(
        f"/api/v1/projects/{project_id}/decision-cases/{case['id']}/close",
        headers=headers,
        json={
            "expected_version": resumed.json()["version"],
            "administrative_rationale": "Duplicate pilot case closed by project administrator",
        },
    )
    assert closed.status_code == 200, closed.text
    denied_attachment = client.post(
        f"/api/v1/projects/{project_id}/decision-cases/{case['id']}/evidence",
        headers=headers,
        json={
            "expected_version": closed.json()["version"],
            "evidence_item_ids": [evidence["id"]],
            "attachment_reason": "Cannot alter closed evidence set",
        },
    )
    assert denied_attachment.status_code == 409
    unsupported_failure_reopen = client.post(
        f"/api/v1/projects/{project_id}/decision-cases/{case['id']}/reopen",
        headers=headers,
        json={
            "expected_version": closed.json()["version"],
            "trigger": "RESPONSE_FAILED",
            "reason": "Claimed response failure without a recorded failed response",
        },
    )
    assert unsupported_failure_reopen.status_code == 422
    new_evidence = add_evidence(
        client, project_id, headers, object_id, field="schedule_variance_days", value=18
    )
    reopened = client.post(
        f"/api/v1/projects/{project_id}/decision-cases/{case['id']}/reopen",
        headers=headers,
        json={
            "expected_version": closed.json()["version"],
            "trigger": "NEW_MATERIAL_EVIDENCE",
            "reason": "New evidence materially increases the delay",
            "new_evidence_item_id": new_evidence["id"],
        },
    )
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["lifecycle"] == "REOPENED"
    assert reopened.json()["readiness"] is None
    assembly = client.get(
        f"/api/v1/projects/{project_id}/decision-cases/{case['id']}/evidence-assembly",
        headers=headers,
    )
    assert new_evidence["id"] in {item["id"] for item in assembly.json()["evidence"]}
    with sessions() as session:
        event_types = set(session.scalars(select(CaseLedgerEvent.event_type)))
        assert {"CASE_BLOCKED", "CASE_RESUMED", "CASE_CLOSED", "CASE_REOPENED"} <= event_types


def test_case_access_and_policy_version_fail_closed(
    case_api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = case_api
    organization_id, project_id, headers, object_id = bootstrap(client)
    evidence = add_evidence(client, project_id, headers, object_id)
    case = open_case(client, project_id, headers, evidence, "access")
    unsupported = client.post(
        f"/api/v1/projects/{project_id}/decision-cases/{case['id']}/snapshots",
        headers={**headers, "Idempotency-Key": "unsupported-policy"},
        json={
            "expected_version": case["version"],
            "data_date": datetime.now(UTC).isoformat(),
            "policy_version": "UNREVIEWED-POLICY",
        },
    )
    assert unsupported.status_code == 422
    denied = client.get(
        f"/api/v1/projects/{project_id}/decision-cases/{case['id']}",
        headers={
            "X-VAI-Actor-ID": "outsider@example.test",
            "X-VAI-Organization-ID": organization_id,
        },
    )
    assert denied.status_code == 403


def test_progress_gates_reconcile_without_silent_truth_upgrade(
    case_api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = case_api
    _, project_id, headers, object_id = bootstrap(client)
    signal_source = add_evidence(client, project_id, headers, object_id)
    case = open_case(client, project_id, headers, signal_source, "progress-gates")
    plan_date = datetime.now(UTC)
    context = activate_progress_schedule(client, project_id, headers, [(plan_date, "60")])
    point_time = datetime.now(UTC)
    planned = progress_evidence(
        client,
        project_id,
        headers,
        object_id,
        value="60",
        as_of=point_time,
        basis="PHYSICAL_VERIFIED",
        semantic_state="CURRENT_AUTHORIZED",
        truth_type="VERIFIED_FACT",
        field="planned_progress_quantity",
    )
    gate_specs = [
        ("REPORTED", "55", "REPORTED_PERCENT_COMPLETE", "REPORTED", "REPORTED_CLAIM"),
        ("EXECUTED", "50", "PHYSICAL_EXECUTED", "ACTUAL", "REPORTED_CLAIM"),
        ("VERIFIED", "45", "PHYSICAL_VERIFIED", "VERIFIED", "VERIFIED_FACT"),
        ("ACCEPTED_RELEASED", "35", "ACCEPTED_RELEASED", "VERIFIED", "VERIFIED_FACT"),
    ]
    measurements: dict[str, dict[str, Any]] = {}
    evidence_ids = [planned["id"]]
    planned_measurement = normalize_progress(
        client,
        project_id,
        headers,
        planned,
        kind="PLANNED_AUTHORIZED",
        context_id=context["id"],
    )
    repeated_measurement = normalize_progress(
        client,
        project_id,
        headers,
        planned,
        kind="PLANNED_AUTHORIZED",
        context_id=context["id"],
    )
    assert repeated_measurement["id"] == planned_measurement["id"]
    for kind, value, basis, state, truth in gate_specs:
        item = progress_evidence(
            client,
            project_id,
            headers,
            object_id,
            value=value,
            as_of=point_time,
            basis=basis,
            semantic_state=state,
            truth_type=truth,
            field=f"{kind.lower()}_progress_quantity",
        )
        evidence_ids.append(item["id"])
        measurements[kind] = normalize_progress(client, project_id, headers, item, kind=kind)
    case = attach(client, project_id, headers, case, evidence_ids)
    frozen = snapshot(
        client,
        project_id,
        headers,
        case,
        "progress-gates-snapshot",
        point_time + timedelta(seconds=1),
    )
    payload = {
        "expected_version": frozen["case"]["version"],
        "snapshot_id": frozen["snapshot"]["id"],
        "planned_measurement_id": planned_measurement["id"],
        "actual_measurement_id": measurements["VERIFIED"]["id"],
    }
    evaluated = client.post(
        f"/api/v1/projects/{project_id}/decision-cases/{case['id']}/progress-evaluations",
        headers={**headers, "Idempotency-Key": "progress-gates-evaluation"},
        json=payload,
    )
    assert evaluated.status_code == 201, evaluated.text
    result = evaluated.json()["evaluation"]
    assert result["direction"] == "BEHIND"
    assert result["variance_ratio"] == "-0.15000000"
    assert result["persistence"] == "TRANSIENT"
    assert result["truth_type"] == "DERIVED_METRIC"
    assert result["reconciliation_status"] == "RECONCILED"
    assert set(result["reconciled_measurements"]) == {
        "PLANNED_AUTHORIZED:PHYSICAL_VERIFIED",
        "REPORTED",
        "EXECUTED",
        "VERIFIED",
        "ACCEPTED_RELEASED",
    }
    repeated = client.post(
        f"/api/v1/projects/{project_id}/decision-cases/{case['id']}/progress-evaluations",
        headers={**headers, "Idempotency-Key": "progress-gates-evaluation"},
        json=payload,
    )
    assert repeated.status_code == 201
    assert repeated.json()["evaluation"]["id"] == result["id"]
    incompatible = client.post(
        f"/api/v1/projects/{project_id}/decision-cases/{case['id']}/progress-evaluations",
        headers={**headers, "Idempotency-Key": "progress-incompatible"},
        json={
            **payload,
            "expected_version": evaluated.json()["case"]["version"],
            "actual_measurement_id": measurements["EXECUTED"]["id"],
        },
    )
    assert incompatible.status_code == 422

    policy = client.post(
        f"/api/v1/projects/{project_id}/progress/policies",
        headers=headers,
        json={
            "policy_version": "PROGRESS-HIGH-THRESHOLD-1",
            "deviation_threshold": "0.20",
            "on_plan_tolerance": "0.01",
            "persistence_min_observations": 3,
            "persistence_min_duration_days": 7,
            "rationale": "Test that evaluation records the selected visible policy",
        },
    )
    assert policy.status_code == 201, policy.text
    custom_policy_evaluation = client.post(
        f"/api/v1/projects/{project_id}/decision-cases/{case['id']}/progress-evaluations",
        headers={**headers, "Idempotency-Key": "progress-custom-policy"},
        json={
            **payload,
            "expected_version": evaluated.json()["case"]["version"],
            "policy_version": "PROGRESS-HIGH-THRESHOLD-1",
        },
    )
    assert custom_policy_evaluation.status_code == 201, custom_policy_evaluation.text
    assert custom_policy_evaluation.json()["evaluation"]["threshold_crossed"] is False
    assert (
        custom_policy_evaluation.json()["evaluation"]["policy_version"]
        == "PROGRESS-HIGH-THRESHOLD-1"
    )

    conflicting = progress_evidence(
        client,
        project_id,
        headers,
        object_id,
        value="48",
        as_of=point_time,
        basis="PHYSICAL_VERIFIED",
        semantic_state="VERIFIED",
        truth_type="VERIFIED_FACT",
        field="verified_progress_quantity",
    )
    contradiction = client.post(
        f"/api/v1/projects/{project_id}/evidence/contradictions",
        headers=headers,
        json={
            "left_item_id": measurements["VERIFIED"]["evidence_item_id"],
            "right_item_id": conflicting["id"],
            "field_name": "verified_progress_quantity",
            "material": True,
        },
    )
    assert contradiction.status_code == 201, contradiction.text
    case = attach(
        client,
        project_id,
        headers,
        custom_policy_evaluation.json()["case"],
        [conflicting["id"]],
    )
    contradicted_snapshot = snapshot(
        client,
        project_id,
        headers,
        case,
        "progress-contradicted-snapshot",
        datetime.now(UTC) + timedelta(seconds=2),
    )
    contradicted = client.post(
        f"/api/v1/projects/{project_id}/decision-cases/{case['id']}/progress-evaluations",
        headers={**headers, "Idempotency-Key": "progress-contradicted-evaluation"},
        json={
            **payload,
            "expected_version": contradicted_snapshot["case"]["version"],
            "snapshot_id": contradicted_snapshot["snapshot"]["id"],
        },
    )
    assert contradicted.status_code == 201, contradicted.text
    assert contradicted.json()["evaluation"]["truth_type"] == "CONTRADICTED"
    assert contradicted.json()["evaluation"]["reconciliation_status"] == "VERIFICATION_REQUIRED"
    assert contradicted.json()["evaluation"]["limitations"][0]["code"] == (
        "UNRESOLVED_PROGRESS_CONTRADICTION"
    )


def test_progress_persistence_requires_observations_across_duration(
    case_api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, sessions = case_api
    _, project_id, headers, object_id = bootstrap(client)
    first_date = datetime.now(UTC) - timedelta(days=14)
    dates = [first_date, first_date + timedelta(days=7), first_date + timedelta(days=14)]
    context = activate_progress_schedule(
        client, project_id, headers, list(zip(dates, ["40", "55", "70"], strict=True))
    )
    with sessions() as session:
        stored = session.get(AuthorizedContextVersion, uuid.UUID(context["id"]))
        stored.activated_at = first_date - timedelta(days=1)
        session.commit()
    signal_source = add_evidence(client, project_id, headers, object_id, as_of=first_date)
    case = open_case(client, project_id, headers, signal_source, "progress-persistence")
    planned_values = ["40", "55", "70"]
    actual_values = ["30", "42", "55"]
    planned_measurements: list[dict[str, Any]] = []
    actual_measurements: list[dict[str, Any]] = []
    evidence_ids: list[str] = []
    for index, date in enumerate(dates):
        planned = progress_evidence(
            client,
            project_id,
            headers,
            object_id,
            value=planned_values[index],
            as_of=date,
            basis="PHYSICAL_VERIFIED",
            semantic_state="CURRENT_AUTHORIZED",
            truth_type="VERIFIED_FACT",
            field="planned_progress_quantity",
        )
        actual = progress_evidence(
            client,
            project_id,
            headers,
            object_id,
            value=actual_values[index],
            as_of=date,
            basis="PHYSICAL_VERIFIED",
            semantic_state="VERIFIED",
            truth_type="VERIFIED_FACT",
            field="verified_progress_quantity",
        )
        evidence_ids.extend([planned["id"], actual["id"]])
        planned_measurements.append(
            normalize_progress(
                client,
                project_id,
                headers,
                planned,
                kind="PLANNED_AUTHORIZED",
                context_id=context["id"],
            )
        )
        actual_measurements.append(
            normalize_progress(client, project_id, headers, actual, kind="VERIFIED")
        )
    case = attach(client, project_id, headers, case, evidence_ids)
    results: list[dict[str, Any]] = []
    for index, date in enumerate(dates):
        frozen = snapshot(
            client,
            project_id,
            headers,
            case,
            f"progress-persistence-snapshot-{index}",
            date + timedelta(hours=1),
        )
        payload: dict[str, Any] = {
            "expected_version": frozen["case"]["version"],
            "snapshot_id": frozen["snapshot"]["id"],
            "planned_measurement_id": planned_measurements[index]["id"],
            "actual_measurement_id": actual_measurements[index]["id"],
        }
        if index:
            payload.update(
                {
                    "prior_planned_measurement_id": planned_measurements[index - 1]["id"],
                    "prior_actual_measurement_id": actual_measurements[index - 1]["id"],
                }
            )
        evaluated = client.post(
            f"/api/v1/projects/{project_id}/decision-cases/{case['id']}/progress-evaluations",
            headers={**headers, "Idempotency-Key": f"progress-persistence-{index}"},
            json=payload,
        )
        assert evaluated.status_code == 201, evaluated.text
        case = evaluated.json()["case"]
        results.append(evaluated.json()["evaluation"])
    assert [value["persistence"] for value in results] == [
        "TRANSIENT",
        "TRANSIENT",
        "PERSISTENT",
    ]
    assert results[-1]["supporting_observation_count"] == 3
    assert results[-1]["duration_days"] == 14
    assert results[-1]["trend_direction"] == "DETERIORATING"
    assert results[-1]["planned_productivity"] is not None
    assert results[-1]["actual_productivity"] is not None
    with sessions() as session:
        assert session.scalar(select(func.count(ProgressEvaluation.id))) == 3


def test_progress_policy_and_authorized_plan_lineage_fail_closed(
    case_api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = case_api
    _, project_id, headers, object_id = bootstrap(client)
    policies = client.get(f"/api/v1/projects/{project_id}/progress/policies", headers=headers)
    assert policies.status_code == 200
    assert policies.json()[0]["policy_version"] == "PROGRESS-DEFAULT-1.0.0"
    configured = client.post(
        f"/api/v1/projects/{project_id}/progress/policies",
        headers=headers,
        json={
            "policy_version": "PILOT-PROGRESS-1",
            "deviation_threshold": "0.08",
            "on_plan_tolerance": "0.02",
            "persistence_min_observations": 4,
            "persistence_min_duration_days": 10,
            "rationale": "Pilot controls threshold approved by project administration",
        },
    )
    assert configured.status_code == 201, configured.text
    duplicate = client.post(
        f"/api/v1/projects/{project_id}/progress/policies",
        headers=headers,
        json={
            "policy_version": "PILOT-PROGRESS-1",
            "deviation_threshold": "0.09",
            "on_plan_tolerance": "0.02",
            "persistence_min_observations": 4,
            "persistence_min_duration_days": 10,
            "rationale": "A version identifier cannot be silently overwritten",
        },
    )
    assert duplicate.status_code == 409

    plan_date = datetime.now(UTC)
    context = activate_progress_schedule(client, project_id, headers, [(plan_date, "60")])
    unapproved_value = progress_evidence(
        client,
        project_id,
        headers,
        object_id,
        value="70",
        as_of=datetime.now(UTC),
        basis="PHYSICAL_VERIFIED",
        semantic_state="CURRENT_AUTHORIZED",
        truth_type="VERIFIED_FACT",
        field="planned_progress_quantity",
    )
    rejected = client.post(
        f"/api/v1/projects/{project_id}/progress/measurements",
        headers=headers,
        json={
            "evidence_item_id": unapproved_value["id"],
            "authorized_context_id": context["id"],
            "measurement_kind": "PLANNED_AUTHORIZED",
            "numerator": "70",
            "denominator": "100",
            "unit": "%",
        },
    )
    assert rejected.status_code == 422
    assert "not present in the authorized schedule" in rejected.json()["detail"]


def test_large_schedule_delay_can_remain_local_when_float_absorbs_it(
    case_api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, sessions = case_api
    _, project_id, headers, object_id = bootstrap(client)
    delay = schedule_delay_evidence(client, project_id, headers, object_id, delay_days="15")
    case = open_case(client, project_id, headers, delay, "large-local-delay")
    context = activate_schedule_network(
        client,
        project_id,
        headers,
        schedule_payload(source_float="20", successor_gap_days=None),
    )
    network = client.get(f"/api/v1/projects/{project_id}/schedule/network", headers=headers)
    assert network.status_code == 200
    assert network.json()["context_id"] == context["id"]
    assert network.json()["calendar_count"] == 2
    case = attach(client, project_id, headers, case, [delay["id"]])
    frozen = snapshot(client, project_id, headers, case, "large-local-schedule")
    assessed = assess_schedule_case(
        client,
        project_id,
        headers,
        case,
        frozen,
        object_id,
        delay["id"],
        "large-local-assessment",
    )
    result = assessed["assessment"]
    assert result["timing_direction"] == "DELAYED"
    assert result["delay_days"] == "15.000"
    assert result["effective_float_days"] == "20.000"
    assert result["float_source"] == "SUPPLIED"
    assert result["exposure_level"] == "LOCAL"
    assert result["affected_activity_codes"] == []
    assert result["maximum_supported_conclusion"] == "LOCAL_TIMING_VARIANCE"
    repeated = assess_schedule_case(
        client,
        project_id,
        headers,
        case,
        frozen,
        object_id,
        delay["id"],
        "large-local-assessment",
    )
    assert repeated["assessment"]["id"] == result["id"]
    with sessions() as session:
        assert session.scalar(select(func.count(ScheduleAssessment.id))) == 1


def test_smaller_delay_reaches_explicit_material_milestone_path(
    case_api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = case_api
    _, project_id, headers, object_id = bootstrap(client)
    signal_source = add_evidence(client, project_id, headers, object_id)
    delay = schedule_delay_evidence(client, project_id, headers, object_id, delay_days="3")
    case = open_case(client, project_id, headers, signal_source, "small-consequential-delay")
    activate_schedule_network(
        client,
        project_id,
        headers,
        schedule_payload(successor_gap_days=0),
    )
    case = attach(client, project_id, headers, case, [delay["id"]])
    frozen = snapshot(client, project_id, headers, case, "small-consequential-schedule")
    assessed = assess_schedule_case(
        client,
        project_id,
        headers,
        case,
        frozen,
        object_id,
        delay["id"],
        "small-consequential-assessment",
    )
    result = assessed["assessment"]
    assert result["effective_float_days"] == "0.000"
    assert result["float_source"] == "CALCULATED"
    assert result["exposure_level"] == "MILESTONE"
    assert result["affected_activity_codes"] == ["B-MILESTONE"]
    assert result["milestone_exposures"][0]["milestone_code"] == "M-HANDOVER"
    assert result["milestone_exposures"][0]["activity_path"] == [
        "A-SOURCE",
        "B-MILESTONE",
    ]
    assert result["milestone_exposures"][0]["exposure_days"] == "3"
    assert result["maximum_supported_conclusion"] == "MILESTONE_EXPOSURE"
    assert result["assessment_status"] == "ASSESSED"
    data_date = datetime.fromisoformat(frozen["snapshot"]["data_date"]).date()
    forecast = client.post(
        f"/api/v1/projects/{project_id}/decision-cases/{case['id']}/forecasts",
        headers={**headers, "Idempotency-Key": "schedule-completion-forecast"},
        json={
            "expected_version": assessed["case"]["version"],
            "snapshot_id": frozen["snapshot"]["id"],
            "controlled_object_id": object_id,
            "target": "SCHEDULE_COMPLETION_DATE",
            "scenario_type": "CONTINUED_PERFORMANCE",
            "horizon_end": (data_date + timedelta(days=60)).isoformat(),
            "schedule_assessment_id": result["id"],
        },
    )
    assert forecast.status_code == 201, forecast.text
    projected = forecast.json()["forecast"]
    assert projected["method"] == "SCHEDULE_DELAY_PROPAGATION"
    assert (
        projected["result_point"]
        == (datetime.fromisoformat(result["planned_finish"]).date() + timedelta(days=3)).isoformat()
    )


def test_schedule_quality_limits_weak_stale_incomplete_network(
    case_api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = case_api
    _, project_id, headers, object_id = bootstrap(client)
    delay = schedule_delay_evidence(
        client,
        project_id,
        headers,
        object_id,
        delay_days="8",
        semantic_state="REPORTED",
        truth_type="REPORTED_CLAIM",
    )
    case = open_case(client, project_id, headers, delay, "limited-schedule")
    activate_schedule_network(
        client,
        project_id,
        headers,
        schedule_payload(
            source_float=None,
            successor_gap_days=0,
            network_complete=False,
            data_date=datetime.now(UTC) - timedelta(days=30),
        ),
    )
    case = attach(client, project_id, headers, case, [delay["id"]])
    frozen = snapshot(client, project_id, headers, case, "limited-schedule-snapshot")
    assessed = assess_schedule_case(
        client,
        project_id,
        headers,
        case,
        frozen,
        object_id,
        delay["id"],
        "limited-schedule-assessment",
    )
    result = assessed["assessment"]
    assert result["assessment_status"] == "VERIFICATION_REQUIRED"
    assert result["schedule_quality"] == "VALID_WITH_LIMITATIONS"
    assert result["maximum_supported_conclusion"] == "LOCAL_TIMING_VARIANCE"
    assert {value["code"] for value in result["limitations"]} >= {
        "STALE_AUTHORIZED_SCHEDULE",
        "NETWORK_COMPLETENESS_UNCONFIRMED",
        "WEAK_DELAY_EVIDENCE",
    }
    policies = client.get(f"/api/v1/projects/{project_id}/schedule/policies", headers=headers)
    assert policies.status_code == 200
    assert policies.json()[0]["policy_version"] == "SCHEDULE-DEFAULT-1.0.0"
    custom_policy = client.post(
        f"/api/v1/projects/{project_id}/schedule/policies",
        headers=headers,
        json={
            "policy_version": "SCHEDULE-60-DAY-1",
            "on_time_tolerance_days": "0.5",
            "maximum_schedule_age_days": 60,
            "require_dependency_for_consequence": True,
            "allow_calculated_float": True,
            "rationale": "Explicit pilot policy accepts monthly schedule status",
        },
    )
    assert custom_policy.status_code == 201, custom_policy.text
    custom_snapshot = {**frozen, "case": assessed["case"]}
    reassessed = assess_schedule_case(
        client,
        project_id,
        headers,
        assessed["case"],
        custom_snapshot,
        object_id,
        delay["id"],
        "limited-schedule-custom-policy",
        "SCHEDULE-60-DAY-1",
    )
    assert reassessed["assessment"]["policy_version"] == "SCHEDULE-60-DAY-1"
    assert "STALE_AUTHORIZED_SCHEDULE" not in {
        value["code"] for value in reassessed["assessment"]["limitations"]
    }


def test_approved_schedule_change_removes_apparent_milestone_exposure(
    case_api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, sessions = case_api
    _, project_id, headers, object_id = bootstrap(client)
    delay = schedule_delay_evidence(client, project_id, headers, object_id, delay_days="5")
    case = open_case(client, project_id, headers, delay, "approved-change")
    original_context = activate_schedule_network(
        client,
        project_id,
        headers,
        schedule_payload(successor_gap_days=0),
        approval="ORIGINAL-SCHEDULE",
    )
    case = attach(client, project_id, headers, case, [delay["id"]])
    original_snapshot = snapshot(client, project_id, headers, case, "original-schedule-snapshot")
    original = assess_schedule_case(
        client,
        project_id,
        headers,
        case,
        original_snapshot,
        object_id,
        delay["id"],
        "original-schedule-assessment",
    )
    assert original["assessment"]["exposure_level"] == "MILESTONE"

    changed_context = activate_schedule_network(
        client,
        project_id,
        headers,
        schedule_payload(successor_gap_days=14),
        state="PROPOSED",
        approval="APPROVED-CHANGE-17",
    )
    changed_snapshot = snapshot(
        client,
        project_id,
        headers,
        original["case"],
        "changed-schedule-snapshot",
        datetime.now(UTC) + timedelta(seconds=2),
    )
    changed = assess_schedule_case(
        client,
        project_id,
        headers,
        original["case"],
        changed_snapshot,
        object_id,
        delay["id"],
        "changed-schedule-assessment",
    )
    assert changed["assessment"]["schedule_context_id"] == changed_context["id"]
    assert changed["assessment"]["exposure_level"] == "LOCAL"
    assert changed["assessment"]["milestone_exposures"] == []
    assert original["assessment"]["schedule_context_id"] == original_context["id"]
    with sessions() as session:
        stored = list(
            session.scalars(
                select(ScheduleAssessment).order_by(ScheduleAssessment.assessment_number)
            )
        )
        assert [value.schedule_context_id for value in stored] == [
            uuid.UUID(original_context["id"]),
            uuid.UUID(changed_context["id"]),
        ]


def test_invalid_schedule_cycle_and_constraint_are_rejected(
    case_api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = case_api
    _, project_id, headers, _ = bootstrap(client)
    payload = schedule_payload(successor_gap_days=0)
    payload["dependencies"].append(
        {
            "predecessor_code": "B-MILESTONE",
            "successor_code": "A-SOURCE",
            "relation_type": "FINISH_TO_START",
            "lag_days": "0",
        }
    )
    cycle = client.post(
        f"/api/v1/projects/{project_id}/authorized-context/versions",
        headers=headers,
        json={
            "context_type": "SCHEDULE",
            "semantic_state": "BASELINE",
            "effective_from": datetime.now(UTC).isoformat(),
            "payload": payload,
        },
    )
    assert cycle.status_code == 422
    constrained = schedule_payload()
    constrained["constraints"][0]["constraint_date"] = (
        datetime.now(UTC).date() + timedelta(days=2)
    ).isoformat()
    invalid_constraint = client.post(
        f"/api/v1/projects/{project_id}/authorized-context/versions",
        headers=headers,
        json={
            "context_type": "SCHEDULE",
            "semantic_state": "BASELINE",
            "effective_from": datetime.now(UTC).isoformat(),
            "payload": constrained,
        },
    )
    assert invalid_constraint.status_code == 422


def test_cost_only_case_stays_incomparable_without_progress_basis(
    case_api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = case_api
    _, project_id, headers, object_id = bootstrap(client)
    signal_source = add_evidence(client, project_id, headers, object_id)
    actual_evidence, actual = cost_record(
        client, project_id, headers, object_id, kind="ACTUAL", amount="25"
    )
    case = open_case(client, project_id, headers, signal_source, "cost-only")
    budget = activate_budget(client, project_id, headers)
    projection = client.get(f"/api/v1/projects/{project_id}/cost/budget", headers=headers)
    assert projection.status_code == 200
    assert projection.json()["context_id"] == budget["id"]
    assert projection.json()["current_authorized_budget"] == "100"
    policies = client.get(f"/api/v1/projects/{project_id}/cost/policies", headers=headers)
    assert policies.status_code == 200
    assert policies.json()[0]["policy_version"] == "COST-DEFAULT-1.0.0"
    custom = client.post(
        f"/api/v1/projects/{project_id}/cost/policies",
        headers=headers,
        json={
            "policy_version": "COST-PILOT-1",
            "alignment_tolerance": "0.08",
            "minimum_earned_ratio_for_forecast": "0.15",
            "include_accruals_in_recognized_cost": True,
            "rationale": "Pilot commercial controller thresholds",
        },
    )
    assert custom.status_code == 201, custom.text
    case = attach(client, project_id, headers, case, [actual_evidence["id"]])
    frozen = snapshot(client, project_id, headers, case, "cost-only-snapshot")
    assessed = assess_cost_case(
        client, project_id, headers, case, frozen, object_id, [actual["id"]], "cost-only"
    )
    result = assessed["assessment"]
    assert result["alignment_status"] == "NOT_COMPARABLE"
    assert result["assessment_status"] == "INSUFFICIENT"
    assert result["forecast_status"] == "NOT_SUPPORTED"
    assert result["maximum_supported_conclusion"] == "COST_ONLY_VARIANCE"


def test_prepayment_explains_apparent_cost_progress_divergence(
    case_api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, sessions = case_api
    _, project_id, headers, object_id = bootstrap(client)
    signal_source = add_evidence(client, project_id, headers, object_id)
    evidence_a, ordinary_actual = cost_record(
        client, project_id, headers, object_id, kind="ACTUAL", amount="30"
    )
    evidence_b, prepaid_actual = cost_record(
        client,
        project_id,
        headers,
        object_id,
        kind="ACTUAL",
        amount="20",
        effect="PREPAYMENT",
        explanation="Verified advance payment precedes physical earning",
    )
    evidence_c, earned = cost_record(
        client, project_id, headers, object_id, kind="EARNED_VALUE", amount="30"
    )
    case = open_case(client, project_id, headers, signal_source, "explained-cost")
    activate_budget(client, project_id, headers)
    case = attach(
        client,
        project_id,
        headers,
        case,
        [evidence_a["id"], evidence_b["id"], evidence_c["id"]],
    )
    frozen = snapshot(client, project_id, headers, case, "explained-cost-snapshot")
    record_ids = [ordinary_actual["id"], prepaid_actual["id"], earned["id"]]
    assessed = assess_cost_case(
        client, project_id, headers, case, frozen, object_id, record_ids, "explained-cost"
    )
    result = assessed["assessment"]
    assert result["alignment_status"] == "COST_AHEAD"
    assert result["alignment_variance_ratio"] == "0.20000000"
    assert result["unexplained_variance_ratio"] == "0E-8"
    assert result["maximum_supported_conclusion"] == "EXPLAINED_DIVERGENCE"
    assert result["explained_effects"][0]["type"] == "PREPAYMENT"
    assert "no contractual liability" in result["explained_effects"][0]["boundary"]
    repeated = assess_cost_case(
        client, project_id, headers, case, frozen, object_id, record_ids, "explained-cost"
    )
    assert repeated["assessment"]["id"] == result["id"]
    with sessions() as session:
        assert session.scalar(select(func.count(CostAssessment.id))) == 1


def test_eac_requires_verified_earned_basis_and_compatible_dimensions(
    case_api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = case_api
    _, project_id, headers, object_id = bootstrap(client)
    signal_source = add_evidence(client, project_id, headers, object_id)
    actual_evidence, actual = cost_record(
        client, project_id, headers, object_id, kind="ACTUAL", amount="50"
    )
    earned_evidence, earned = cost_record(
        client, project_id, headers, object_id, kind="EARNED_VALUE", amount="25"
    )
    case = open_case(client, project_id, headers, signal_source, "cost-forecast")
    activate_budget(client, project_id, headers)
    case = attach(
        client,
        project_id,
        headers,
        case,
        [actual_evidence["id"], earned_evidence["id"]],
    )
    frozen = snapshot(client, project_id, headers, case, "cost-forecast-snapshot")
    assessed = assess_cost_case(
        client,
        project_id,
        headers,
        case,
        frozen,
        object_id,
        [actual["id"], earned["id"]],
        "cost-forecast",
    )
    result = assessed["assessment"]
    assert result["forecast_status"] == "CALCULATED"
    assert result["estimate_at_completion"] == "200.0000"
    assert result["forecast_to_complete"] == "150.0000"
    assert result["maximum_supported_conclusion"] == "FORECAST_EXPOSURE"
    data_date = datetime.fromisoformat(frozen["snapshot"]["data_date"]).date()
    versioned_forecast = client.post(
        f"/api/v1/projects/{project_id}/decision-cases/{case['id']}/forecasts",
        headers={**headers, "Idempotency-Key": "versioned-cost-forecast"},
        json={
            "expected_version": assessed["case"]["version"],
            "snapshot_id": frozen["snapshot"]["id"],
            "controlled_object_id": object_id,
            "target": "ESTIMATE_AT_COMPLETION",
            "scenario_type": "CONTINUED_PERFORMANCE",
            "horizon_end": (data_date + timedelta(days=90)).isoformat(),
            "cost_assessment_id": result["id"],
        },
    )
    assert versioned_forecast.status_code == 201, versioned_forecast.text
    projection = versioned_forecast.json()["forecast"]
    assert projection["result_point"] == "200.0000"
    assert projection["result_lower"] == "180.0000"
    assert projection["result_upper"] == "220.0000"
    assert projection["semantic_state"] == "FORECAST"

    eur_evidence, eur_record = cost_record(
        client,
        project_id,
        headers,
        object_id,
        kind="COMMITMENT",
        amount="10",
        currency="EUR",
    )
    updated_case = attach(
        client, project_id, headers, versioned_forecast.json()["case"], [eur_evidence["id"]]
    )
    mixed_snapshot = snapshot(client, project_id, headers, updated_case, "mixed-currency-snapshot")
    rejected = client.post(
        f"/api/v1/projects/{project_id}/decision-cases/{case['id']}/cost-assessments",
        headers={**headers, "Idempotency-Key": "mixed-currency"},
        json={
            "expected_version": mixed_snapshot["case"]["version"],
            "snapshot_id": mixed_snapshot["snapshot"]["id"],
            "controlled_object_id": object_id,
            "cost_record_ids": [actual["id"], earned["id"], eur_record["id"]],
        },
    )
    assert rejected.status_code == 422
    assert "incompatible currencies" in rejected.json()["detail"]


def test_boq_value_requires_exact_authorized_revision_lineage(
    case_api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = case_api
    _, project_id, headers, object_id = bootstrap(client)
    source = client.post(
        f"/api/v1/projects/{project_id}/authorized-context/versions",
        headers=headers,
        json={
            "context_type": "BOQ",
            "semantic_state": "BASELINE",
            "effective_from": (datetime.now(UTC) - timedelta(days=1)).isoformat(),
            "payload": {
                "items": [
                    {
                        "code": "BOQ-1",
                        "description": "Controlled package quantity",
                        "quantity": "10",
                        "unit": "m3",
                        "rate": "2",
                        "currency": "USD",
                        "controlled_object_code": "WP-CASE",
                    }
                ]
            },
        },
    )
    assert source.status_code == 201, source.text
    activated = client.post(
        f"/api/v1/projects/{project_id}/authorized-context/activate",
        headers=headers,
        json={
            "source_version_id": source.json()["id"],
            "approval_reference": "BOQ-REVISION-1",
            "reason": "Authorize measured BOQ revision",
        },
    )
    assert activated.status_code == 201, activated.text
    _, record = cost_record(
        client,
        project_id,
        headers,
        object_id,
        kind="BOQ_VALUE",
        amount="20",
        context_id=activated.json()["id"],
    )
    assert record["amount"] == "20.0000"
    assert record["authorized_context_id"] == activated.json()["id"]


def test_production_forecast_branches_ranges_confidence_and_history(
    case_api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, sessions = case_api
    _, project_id, headers, object_id = bootstrap(client)
    case, frozen, evaluation, response_id = prepare_production_forecast_case(
        client, sessions, project_id, headers, object_id
    )
    data_date = datetime.fromisoformat(frozen["snapshot"]["data_date"]).date()
    horizon = (data_date + timedelta(days=60)).isoformat()
    policies = client.get(f"/api/v1/projects/{project_id}/forecast/policies", headers=headers)
    assert policies.status_code == 200
    assert policies.json()[0]["policy_version"] == "FORECAST-DEFAULT-1.0.0"
    custom_policy = client.post(
        f"/api/v1/projects/{project_id}/forecast/policies",
        headers=headers,
        json={
            "policy_version": "FORECAST-PILOT-1",
            "lower_rate_factor": "0.75",
            "upper_rate_factor": "1.25",
            "lower_cost_factor": "0.85",
            "upper_cost_factor": "1.15",
            "confidence_decay_per_30_days": "0.10",
            "confidence_floor": "0.20",
            "maximum_horizon_days": 365,
            "validity_days": 7,
            "rationale": "Explicit pilot forecast range and decay policy",
        },
    )
    assert custom_policy.status_code == 201, custom_policy.text
    base = {
        "expected_version": case["version"],
        "snapshot_id": frozen["snapshot"]["id"],
        "controlled_object_id": object_id,
        "target": "PRODUCTION_COMPLETION_DATE",
        "scenario_type": "CONTINUED_PERFORMANCE",
        "horizon_end": horizon,
        "progress_evaluation_id": evaluation["id"],
        "assumptions": ["No material resource constraint enters the workfront"],
    }
    continued = client.post(
        f"/api/v1/projects/{project_id}/decision-cases/{case['id']}/forecasts",
        headers={**headers, "Idempotency-Key": "continued-production"},
        json=base,
    )
    assert continued.status_code == 201, continued.text
    continued_result = continued.json()["forecast"]
    assert continued_result["semantic_state"] == "FORECAST"
    assert continued_result["truth_type"] == "SCENARIO_ESTIMATE"
    assert continued_result["method"] == "LINEAR_PRODUCTION_RATE"
    assert continued_result["result_lower"] <= continued_result["result_point"]
    assert continued_result["result_point"] <= continued_result["result_upper"]
    assert Decimal(continued_result["horizon_confidence"]) < Decimal(
        continued_result["upstream_confidence"]
    )
    assert continued_result["validity"] == "CURRENT"
    repeated = client.post(
        f"/api/v1/projects/{project_id}/decision-cases/{case['id']}/forecasts",
        headers={**headers, "Idempotency-Key": "continued-production"},
        json=base,
    )
    assert repeated.status_code == 201
    assert repeated.json()["forecast"]["id"] == continued_result["id"]

    active = client.post(
        f"/api/v1/projects/{project_id}/decision-cases/{case['id']}/forecasts",
        headers={**headers, "Idempotency-Key": "active-production"},
        json={
            **base,
            "expected_version": continued.json()["case"]["version"],
            "scenario_type": "ACTIVE_RESPONSE",
            "active_response_id": response_id,
        },
    )
    assert active.status_code == 201, active.text
    active_result = active.json()["forecast"]
    assert active_result["result_point"] < continued_result["result_point"]
    assert active_result["scenario_parameters"] == {"productivity_multiplier": "1.5"}
    assert "ACTIVE_RESPONSE_CHANGED" in active_result["recalculation_triggers"]

    hypothetical = client.post(
        f"/api/v1/projects/{project_id}/decision-cases/{case['id']}/forecasts",
        headers={**headers, "Idempotency-Key": "hypothetical-production"},
        json={
            **base,
            "expected_version": active.json()["case"]["version"],
            "scenario_type": "HYPOTHETICAL",
            "scenario_parameters": {"productivity_multiplier": "0.5"},
            "assumptions": ["Illustrative labor constraint only; not authorized"],
            "policy_version": "FORECAST-PILOT-1",
        },
    )
    assert hypothetical.status_code == 201, hypothetical.text
    hypothetical_result = hypothetical.json()["forecast"]
    assert hypothetical_result["semantic_state"] == "SCENARIO"
    assert hypothetical_result["policy_version"] == "FORECAST-PILOT-1"
    assert hypothetical_result["result_point"] > continued_result["result_point"]

    history = client.get(
        f"/api/v1/projects/{project_id}/decision-cases/{case['id']}/forecasts",
        headers=headers,
    )
    assert history.status_code == 200, history.text
    assert [item["scenario_type"] for item in history.json()] == [
        "CONTINUED_PERFORMANCE",
        "ACTIVE_RESPONSE",
        "HYPOTHETICAL",
    ]
    newer = snapshot(
        client,
        project_id,
        headers,
        hypothetical.json()["case"],
        "forecast-input-change-snapshot",
        datetime.now(UTC) + timedelta(seconds=4),
    )
    assert newer["snapshot"]["id"] != frozen["snapshot"]["id"]
    stale_history = client.get(
        f"/api/v1/projects/{project_id}/decision-cases/{case['id']}/forecasts",
        headers=headers,
    )
    assert {item["validity"] for item in stale_history.json()} == {"RECALCULATION_REQUIRED"}
    with sessions() as session:
        assert session.scalar(select(func.count(ForecastProjection.id))) == 3
