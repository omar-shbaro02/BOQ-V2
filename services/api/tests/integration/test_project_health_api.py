import uuid
from datetime import UTC, datetime, timedelta

from app.models import AuditEvent, CaseSnapshot, DecisionCaseShell, Project, ProjectContextRecord
from test_project_control_api import api as api
from test_project_control_api import bootstrap_project, seed_control_inputs
from test_project_health import POLICY


def test_health_and_context_are_frozen_and_shared_with_report(api):
    client, sessions = api
    _, project_id, headers = bootstrap_project(client)
    body = seed_control_inputs(client, sessions, project_id, headers)
    cutoff = datetime.fromisoformat(body["data_date"])
    case_id = uuid.uuid4()
    with sessions() as session:
        project = session.get(Project, uuid.UUID(project_id))
        session.add(
            DecisionCaseShell(
                id=case_id,
                organization_id=project.organization_id,
                project_id=project.id,
                case_number="DC-HEALTH-1",
                title="Progress review",
                case_type="PROGRESS",
                lifecycle="OPEN",
                owner_actor_id=headers["X-VAI-Actor-ID"],
                created_by=headers["X-VAI-Actor-ID"],
                governance_state="GOVERNANCE_BLOCKED",
                opened_at=cutoff - timedelta(days=2),
            )
        )
        session.flush()
        session.add(
            CaseSnapshot(
                organization_id=project.organization_id,
                project_id=project.id,
                case_id=case_id,
                snapshot_number=1,
                case_version=1,
                data_date=cutoff - timedelta(hours=2),
                controlled_object_ids=[body["packages"][0]["controlled_object_id"]],
                signal_ids=[],
                evidence_item_ids=[],
                contradiction_ids=[],
                authorized_context_refs=[],
                active_response_ids=[],
                baseline_validity="VALID",
                policy_version="TEST-1",
                snapshot_hash="a" * 64,
                idempotency_key="case-snapshot",
                request_hash="b" * 64,
                created_by=headers["X-VAI-Actor-ID"],
                created_at=cutoff - timedelta(hours=1),
            )
        )
        for version, time, state in (
            (1, cutoff - timedelta(minutes=5), "HUMAN_REVIEW_REQUIRED"),
            (2, cutoff + timedelta(minutes=5), "GOVERNANCE_BLOCKED"),
        ):
            session.add(
                AuditEvent(
                    organization_id=project.organization_id,
                    project_id=project.id,
                    occurred_at=time,
                    actor_id=headers["X-VAI-Actor-ID"],
                    actor_type="HUMAN",
                    action="CASE_TEST_STATE",
                    object_type="DECISION_CASE",
                    object_id=str(case_id),
                    object_version=version,
                    authority_result="AUTHORIZED",
                    details={"governance_state": state},
                )
            )
        session.add(
            ProjectContextRecord(
                organization_id=project.organization_id,
                project_id=project.id,
                record_type="RISK",
                record_key="RISK-1",
                version_number=1,
                effective_from=cutoff - timedelta(days=1),
                initial_status="OPEN",
                payload={"title": "Stored risk", "description": "Reported lead-time risk"},
                evidence_item_ids=[],
                idempotency_key="risk1",
                request_hash="c" * 64,
                created_by=headers["X-VAI-Actor-ID"],
                created_at=cutoff - timedelta(hours=1),
            )
        )
        session.commit()
    body["health_policy"] = {**POLICY, "owner_actor_id": headers["X-VAI-Actor-ID"]}
    url = f"/api/v1/projects/{project_id}/project-control/snapshots"
    response = client.post(url, headers={**headers, "Idempotency-Key": "health-1"}, json=body)
    assert response.status_code == 201, response.text
    record = response.json()
    assert record["health"]["policy"]["version"] == POLICY["version"]
    assert record["health"]["status"] == "RED"
    assert (
        record["supporting_context"]["governance"][0]["governance_state"] == "HUMAN_REVIEW_REQUIRED"
    )
    assert record["supporting_context"]["project_context"][0]["payload"]["title"] == "Stored risk"
    report = client.post(
        f"/api/v1/projects/{project_id}/decision-center/report-snapshots",
        headers={**headers, "Idempotency-Key": "health-report"},
        json={
            "report_type": "ON_DEMAND_STATUS_REPORT",
            "project_control_snapshot_id": record["id"],
        },
    )
    assert report.status_code == 201, report.text
    assert report.json()["payload"]["project_control"]["health"] == record["health"]
    detail = client.get(f"{url}/{record['id']}", headers=headers).json()
    assert detail["health"] == record["health"]
    changed = {**body, "health_policy": {**body["health_policy"], "progress_red_deficit": "0.2"}}
    assert (
        client.post(
            url, headers={**headers, "Idempotency-Key": "other-version"}, json=changed
        ).status_code
        == 409
    )
    assert (
        client.post(url, headers={**headers, "Idempotency-Key": "health-1"}, json=body).json()["id"]
        == record["id"]
    )


def test_health_policy_ownership_and_role_gates(api):
    client, sessions = api
    _, project_id, headers = bootstrap_project(client)
    body = seed_control_inputs(client, sessions, project_id, headers)
    body["health_policy"] = POLICY
    url = f"/api/v1/projects/{project_id}/project-control/snapshots"
    assert (
        client.post(
            url, headers={**headers, "Idempotency-Key": "wrong-owner"}, json=body
        ).status_code
        == 422
    )
    membership = client.post(
        f"/api/v1/projects/{project_id}/memberships",
        headers=headers,
        json={"actor_id": "analyst@test", "role": "ANALYST_CONTROLLER"},
    )
    assert membership.status_code == 201
    body["health_policy"] = {**POLICY, "owner_actor_id": "analyst@test"}
    assert (
        client.post(
            url,
            headers={**headers, "X-VAI-Actor-ID": "analyst@test", "Idempotency-Key": "analyst"},
            json=body,
        ).status_code
        == 403
    )
    body["health_policy"] = {
        **POLICY,
        "owner_actor_id": headers["X-VAI-Actor-ID"],
        "effective_from": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
    }
    assert (
        client.post(
            url, headers={**headers, "Idempotency-Key": "future-policy"}, json=body
        ).status_code
        == 422
    )
