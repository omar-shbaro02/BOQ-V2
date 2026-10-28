import hashlib
import uuid
from datetime import datetime, timedelta

import pytest
from app.config import get_settings
from app.models import AuthorityGrant, PresentationArtifact, Project, ProjectContextRecord
from app.services.presentation_render import inspect_source
from sqlalchemy import select
from test_project_control_api import api as api
from test_project_control_api import bootstrap_project, seed_control_inputs
from test_project_health import POLICY


def setup_presentation_source(api, tmp_path, monkeypatch, approve=True, name="Client PM"):
    client, sessions = api
    monkeypatch.setenv("VAI_EVIDENCE_STORAGE_PATH", str(tmp_path))
    get_settings.cache_clear()
    _, project_id, headers = bootstrap_project(client)
    body = seed_control_inputs(client, sessions, project_id, headers)
    cutoff = datetime.fromisoformat(body["data_date"])
    recipient_id = uuid.uuid4()
    with sessions() as session:
        project = session.get(Project, uuid.UUID(project_id))
        session.add(
            ProjectContextRecord(
                id=recipient_id,
                organization_id=project.organization_id,
                project_id=project.id,
                record_type="STAKEHOLDER",
                record_key="CLIENT-PM",
                version_number=1,
                effective_from=cutoff - timedelta(days=1),
                initial_status="ACTIVE",
                payload={
                    "name": name,
                    "project_role": "CLIENT_PM",
                    "communication_rules": ["Approved weekly report only"],
                    "report_recipient": True,
                },
                evidence_item_ids=[],
                idempotency_key="recipient",
                request_hash="e" * 64,
                created_by=headers["X-VAI-Actor-ID"],
                created_at=cutoff - timedelta(hours=1),
            )
        )
        session.commit()
    body["health_policy"] = {**POLICY, "owner_actor_id": headers["X-VAI-Actor-ID"]}
    snapshot = client.post(
        f"/api/v1/projects/{project_id}/project-control/snapshots",
        headers={**headers, "Idempotency-Key": "presentation-control"},
        json=body,
    )
    assert snapshot.status_code == 201, snapshot.text
    base = f"/api/v1/projects/{project_id}/decision-center"
    report = client.post(
        f"{base}/report-snapshots",
        headers={**headers, "Idempotency-Key": "presentation-report"},
        json={
            "report_type": "ON_DEMAND_STATUS_REPORT",
            "project_control_snapshot_id": snapshot.json()["id"],
        },
    )
    assert report.status_code == 201, report.text
    report_id = report.json()["id"]
    grant = client.post(
        f"/api/v1/projects/{project_id}/authority-grants",
        headers=headers,
        json={"actor_id": headers["X-VAI-Actor-ID"], "authority_type": "REPORT_APPROVAL"},
    )
    assert grant.status_code == 201, grant.text
    if approve:
        for status in ("REVIEWED", "APPROVED"):
            event = client.post(
                f"{base}/report-snapshots/{report_id}/lifecycle-events",
                headers=headers,
                json={
                    "to_status": status,
                    "reason": "Explicit human source report review",
                    "authority_grant_id": grant.json()["id"] if status == "APPROVED" else None,
                },
            )
            assert event.status_code == 201, event.text
    return base, headers, report_id, str(recipient_id), grant.json()["id"], snapshot.json()


def test_presentation_fidelity_replay_and_independent_external_approval(api, tmp_path, monkeypatch):
    client, sessions = api
    base, headers, report_id, recipient_id, grant_id, snapshot = setup_presentation_source(
        api, tmp_path, monkeypatch
    )
    data = {"report_snapshot_id": report_id, "recipient_record_ids": [recipient_id]}
    created = client.post(
        f"{base}/presentations", headers={**headers, "Idempotency-Key": "deck-1"}, json=data
    )
    assert created.status_code == 201, created.text
    record = created.json()
    assert record["lifecycle_status"] == "DRAFT"
    assert record["fidelity_manifest"]["shared_metrics"] == snapshot["shared_metrics"]
    assert record["recipients"][0]["id"] == recipient_id
    content = client.get(f"{base}/presentations/{record['id']}/content", headers=headers)
    assert content.status_code == 200, content.text
    assert hashlib.sha256(content.content).hexdigest() == record["content_hash"]
    source = inspect_source(content.content)
    report = client.get(f"{base}/report-snapshots/{report_id}", headers=headers).json()
    assert source["report"]["payload"] == report["payload"]
    assert (
        source["shared_metrics"]
        == snapshot["shared_metrics"]
        == report["payload"]["project_control"]["shared_metrics"]
    )
    project_id = record["project_id"]
    assistant = client.post(
        f"/api/v1/projects/{project_id}/project-control/snapshots/{snapshot['id']}/assistant",
        headers=headers,
        json={"topic": "COMPLETION"},
    ).json()
    assert (
        next(item for item in assistant["facts"] if item["key"] == "completion.actual")["value"]
        == source["shared_metrics"]["actual"]["percent"]
    )
    assert (
        client.post(
            f"{base}/presentations", headers={**headers, "Idempotency-Key": "deck-1"}, json=data
        ).json()["id"]
        == record["id"]
    )
    assert (
        client.post(
            f"{base}/presentations",
            headers={**headers, "Idempotency-Key": "deck-1"},
            json={**data, "recipient_record_ids": [str(uuid.uuid4())]},
        ).status_code
        == 409
    )
    external = f"{base}/approved-presentations/{record['id']}/content"
    assert client.get(external, headers=headers).status_code == 409
    review = client.post(
        f"{base}/presentations/{record['id']}/lifecycle-events",
        headers={**headers, "Idempotency-Key": "review"},
        json={
            "to_status": "REVIEWED",
            "expected_version": 1,
            "reason": "Reviewed exact deck and recipients",
        },
    )
    assert review.status_code == 201, review.text
    denied = client.post(
        f"{base}/presentations/{record['id']}/lifecycle-events",
        headers={**headers, "Idempotency-Key": "approval"},
        json={
            "to_status": "APPROVED",
            "expected_version": 2,
            "reason": "Approve external presentation",
        },
    )
    assert denied.status_code == 403
    approval = client.post(
        f"{base}/presentations/{record['id']}/lifecycle-events",
        headers={**headers, "Idempotency-Key": "approval"},
        json={
            "to_status": "APPROVED",
            "expected_version": 2,
            "reason": "Approve external presentation",
            "authority_grant_id": grant_id,
        },
    )
    assert approval.status_code == 201, approval.text
    approved = client.get(external, headers=headers)
    assert approved.content == content.content
    assert (
        client.post(
            f"{base}/presentations/{record['id']}/lifecycle-events",
            headers={**headers, "Idempotency-Key": "approval"},
            json={
                "to_status": "APPROVED",
                "expected_version": 2,
                "reason": "Approve external presentation",
                "authority_grant_id": grant_id,
            },
        ).json()["id"]
        == approval.json()["id"]
    )
    with sessions() as session:
        assert len(list(session.scalars(select(PresentationArtifact)))) == 1


def test_unapproved_source_foreign_recipient_and_tenant_denied(api, tmp_path, monkeypatch):
    client, _ = api
    base, headers, report_id, recipient_id, _, _ = setup_presentation_source(
        api, tmp_path, monkeypatch, approve=False
    )
    data = {"report_snapshot_id": report_id, "recipient_record_ids": [recipient_id]}
    assert (
        client.post(
            f"{base}/presentations", headers={**headers, "Idempotency-Key": "bad"}, json=data
        ).status_code
        == 409
    )
    assert (
        client.post(
            f"{base}/presentations",
            headers={
                **headers,
                "Idempotency-Key": "bad",
                "X-VAI-Organization-ID": str(uuid.uuid4()),
            },
            json=data,
        ).status_code
        == 403
    )
    assert (
        client.post(
            f"{base}/presentations",
            headers={**headers, "Idempotency-Key": "bad", "X-VAI-Actor-ID": "outsider"},
            json=data,
        ).status_code
        == 403
    )


def test_recipient_and_artifact_integrity_gates(api, tmp_path, monkeypatch):
    client, sessions = api
    base, headers, report_id, recipient_id, _, _ = setup_presentation_source(
        api, tmp_path, monkeypatch, name="<script>window.exfiltrate=1</script> إدارة"
    )
    data = {"report_snapshot_id": report_id, "recipient_record_ids": [recipient_id]}
    assert (
        client.post(
            f"{base}/presentations",
            headers={**headers, "Idempotency-Key": "foreign"},
            json={**data, "recipient_record_ids": [str(uuid.uuid4())]},
        ).status_code
        == 422
    )
    created = client.post(
        f"{base}/presentations", headers={**headers, "Idempotency-Key": "deck"}, json=data
    )
    assert created.status_code == 201, created.text
    record = created.json()
    content = client.get(f"{base}/presentations/{record['id']}/content", headers=headers).content
    assert b"<script>window.exfiltrate" not in content
    assert b"&lt;script&gt;window.exfiltrate" in content
    with sessions() as session:
        stored = session.get(PresentationArtifact, uuid.UUID(record["id"]))
        artifact_path = tmp_path / stored.storage_key
    artifact_path.write_bytes(content + b"corrupt")
    assert (
        client.get(f"{base}/presentations/{record['id']}/content", headers=headers).status_code
        == 409
    )
    tampered = content.replace(
        b"Verified or accepted completion: 28.0%", b"Verified or accepted completion: 99.0%"
    )
    with pytest.raises(ValueError, match="Visible presentation metric"):
        inspect_source(tampered)


@pytest.mark.parametrize(
    "grant_changes",
    [
        {"actor_id": "another-human@example.test"},
        {"active": False},
        {"authority_type": "CHARTER_APPROVAL"},
        {"max_amount": "1000", "currency": "USD"},
        {"valid_until": "2020-01-01"},
        {"valid_from": "2099-01-01"},
    ],
)
def test_approval_exact_authority_and_stale_versions(api, tmp_path, monkeypatch, grant_changes):
    client, sessions = api
    base, headers, report_id, recipient_id, _, _ = setup_presentation_source(
        api, tmp_path, monkeypatch
    )
    created = client.post(
        f"{base}/presentations",
        headers={**headers, "Idempotency-Key": "gated-deck"},
        json={"report_snapshot_id": report_id, "recipient_record_ids": [recipient_id]},
    )
    assert created.status_code == 201, created.text
    path = f"{base}/presentations/{created.json()['id']}/lifecycle-events"
    review = {"to_status": "REVIEWED", "expected_version": 1, "reason": "Reviewed exact artifact"}
    assert (
        client.post(path, headers={**headers, "Idempotency-Key": "review"}, json=review).status_code
        == 201
    )
    assert (
        client.post(path, headers={**headers, "Idempotency-Key": "stale"}, json=review).status_code
        == 409
    )
    project_id = created.json()["project_id"]
    grant = client.post(
        f"/api/v1/projects/{project_id}/authority-grants",
        headers=headers,
        json={
            "actor_id": headers["X-VAI-Actor-ID"],
            "authority_type": "REPORT_APPROVAL",
            **grant_changes,
        },
    )
    assert grant.status_code == 201, grant.text
    if grant_changes.get("active") is False:
        with sessions() as session:
            session.get(AuthorityGrant, uuid.UUID(grant.json()["id"])).active = False
            session.commit()
    denied = client.post(
        path,
        headers={**headers, "Idempotency-Key": "deny"},
        json={
            "to_status": "APPROVED",
            "expected_version": 2,
            "reason": "Attempt with mismatched grant",
            "authority_grant_id": grant.json()["id"],
        },
    )
    assert denied.status_code == 403, denied.text
    assert (
        client.get(f"{base}/presentations/{created.json()['id']}", headers=headers).json()[
            "lifecycle_status"
        ]
        == "REVIEWED"
    )
