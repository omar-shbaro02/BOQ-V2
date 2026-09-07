import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
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
    ProgressEvaluation,
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
