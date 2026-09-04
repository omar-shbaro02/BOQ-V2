import uuid
from collections.abc import Generator
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest
from app.database import Base, get_db
from app.main import app
from app.models import EvidenceArtifact, EvidenceItem, EvidenceRelation, VerificationEvent
from app.storage import LocalEvidenceStore, get_evidence_store
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture
def evidence_api(
    tmp_path: Path,
) -> Generator[tuple[TestClient, sessionmaker[Session]], None, None]:
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
    app.dependency_overrides[get_evidence_store] = lambda: LocalEvidenceStore(tmp_path)
    with TestClient(app) as client:
        yield client, test_sessions
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)


def bootstrap(client: TestClient) -> tuple[str, str, dict[str, str], str]:
    actor = "evidence-admin@example.test"
    organization = client.post(
        "/api/v1/organizations",
        headers={"X-VAI-Actor-ID": actor, "X-VAI-Roles": "ORGANIZATION_ADMIN"},
        json={"name": "Evidence Org", "slug": "evidence-org"},
    )
    assert organization.status_code == 201, organization.text
    organization_id = organization.json()["id"]
    headers = {"X-VAI-Actor-ID": actor, "X-VAI-Organization-ID": organization_id}
    project = client.post(
        f"/api/v1/organizations/{organization_id}/projects",
        headers=headers,
        json={
            "code": "EVD-001",
            "name": "Evidence Pilot",
            "timezone": "Asia/Beirut",
            "currency": "USD",
            "delivery_model": "DESIGN_BID_BUILD",
            "reporting_cadence": "WEEKLY",
        },
    )
    assert project.status_code == 201, project.text
    project_id = project.json()["id"]
    controlled_object = client.post(
        f"/api/v1/projects/{project_id}/controlled-objects",
        headers=headers,
        json={"object_type": "BOQ_ITEM", "code": "BOQ-100", "name": "Concrete"},
    )
    assert controlled_object.status_code == 201, controlled_object.text
    return organization_id, project_id, headers, controlled_object.json()["id"]


def evidence_item(
    *,
    controlled_object_id: str,
    field_name: str = "installed_quantity",
    value: Any = 12,
    measurement_basis: str | None = None,
    supersedes_item_id: str | None = None,
) -> dict[str, Any]:
    return {
        "controlled_object_id": controlled_object_id,
        "field_name": field_name,
        "value": value,
        "unit": "m3",
        "measurement_basis": measurement_basis,
        "semantic_state": "REPORTED",
        "truth_type": "REPORTED_CLAIM",
        "as_of": "2026-09-04T08:00:00Z",
        "confidence": "0.65",
        "supersedes_item_id": supersedes_item_id,
    }


def test_artifact_upload_hash_download_and_csv_import_are_idempotent(
    evidence_api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, sessions = evidence_api
    _, project_id, headers, _ = bootstrap(client)
    csv_content = (
        b"field_name,value,semantic_state,truth_type,as_of,object_code,unit,"
        b"measurement_basis,confidence\n"
        b"installed_quantity,0,REPORTED,REPORTED_CLAIM,2026-09-04T08:00:00Z,"
        b"BOQ-100,m3,,0.7\n"
    )
    uploaded = client.post(
        f"/api/v1/projects/{project_id}/evidence/artifacts",
        headers=headers,
        data={"source_type": "SITE_EXPORT", "source_id": "export-42"},
        files={"upload": ("evidence.csv", csv_content, "text/csv")},
    )
    assert uploaded.status_code == 201, uploaded.text
    artifact = uploaded.json()
    assert artifact["size_bytes"] == len(csv_content)
    assert len(artifact["sha256"]) == 64
    assert artifact["scan_result"] == "CLEAN"
    downloaded = client.get(
        f"/api/v1/projects/{project_id}/evidence/artifacts/{artifact['id']}/content",
        headers=headers,
    )
    assert downloaded.content == csv_content

    preview_url = f"/api/v1/projects/{project_id}/evidence/imports/preview"
    preview_headers = {**headers, "Idempotency-Key": "csv-run-001"}
    preview = client.post(
        preview_url,
        headers=preview_headers,
        json={"artifact_id": artifact["id"], "mapping": {}},
    )
    assert preview.status_code == 201, preview.text
    assert preview.json()["status"] == "PREVIEW"
    assert preview.json()["valid_rows"] == 1
    repeated = client.post(
        preview_url,
        headers=preview_headers,
        json={"artifact_id": artifact["id"], "mapping": {}},
    )
    assert repeated.json()["id"] == preview.json()["id"]

    commit_url = f"/api/v1/projects/{project_id}/evidence/imports/{preview.json()['id']}/commit"
    committed = client.post(commit_url, headers=headers)
    repeated_commit = client.post(commit_url, headers=headers)
    assert committed.status_code == repeated_commit.status_code == 200
    assert committed.json()["evidence_item_ids"] == repeated_commit.json()["evidence_item_ids"]
    with sessions() as session:
        assert len(list(session.scalars(select(EvidenceArtifact)))) == 1
        imported = list(session.scalars(select(EvidenceItem)))
        assert len(imported) == 1
        assert imported[0].value == 0


def test_artifact_type_and_malware_gates_reject_before_storage(
    evidence_api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, sessions = evidence_api
    _, project_id, headers, _ = bootstrap(client)
    url = f"/api/v1/projects/{project_id}/evidence/artifacts"
    metadata = {"source_type": "UNTRUSTED_UPLOAD", "source_id": "scan-test"}
    unsupported = client.post(
        url,
        headers=headers,
        data=metadata,
        files={"upload": ("payload.exe", b"not executable", "application/octet-stream")},
    )
    assert unsupported.status_code == 415
    eicar = client.post(
        url,
        headers=headers,
        data=metadata,
        files={
            "upload": (
                "eicar.txt",
                b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*",
                "text/plain",
            )
        },
    )
    assert eicar.status_code == 422
    with sessions() as session:
        assert session.scalar(select(EvidenceArtifact.id)) is None


def test_xlsx_preview_and_invalid_rows_are_reported_before_commit(
    evidence_api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = evidence_api
    _, project_id, headers, _ = bootstrap(client)
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(
        [
            "field_name",
            "value",
            "semantic_state",
            "truth_type",
            "as_of",
            "object_code",
            "confidence",
        ]
    )
    sheet.append(
        [
            "installed_quantity",
            21,
            "REPORTED",
            "REPORTED_CLAIM",
            "2026-09-04T08:00:00Z",
            "BOQ-100",
            0.75,
        ]
    )
    content = BytesIO()
    workbook.save(content)
    upload = client.post(
        f"/api/v1/projects/{project_id}/evidence/artifacts",
        headers=headers,
        data={"source_type": "QS_WORKBOOK", "source_id": "qs-8"},
        files={
            "upload": (
                "quantities.xlsx",
                content.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    preview = client.post(
        f"/api/v1/projects/{project_id}/evidence/imports/preview",
        headers={**headers, "Idempotency-Key": "xlsx-run-001"},
        json={"artifact_id": upload.json()["id"], "mapping": {}},
    )
    assert preview.status_code == 201, preview.text
    assert (preview.json()["status"], preview.json()["valid_rows"]) == ("PREVIEW", 1)

    invalid_csv = (
        b"field_name,value,semantic_state,truth_type,as_of,object_code,confidence\n"
        b"physical_progress,0,REPORTED,REPORTED_CLAIM,2026-09-04T08:00:00Z,"
        b"BOQ-100,0.5\n"
    )
    invalid_upload = client.post(
        f"/api/v1/projects/{project_id}/evidence/artifacts",
        headers=headers,
        data={"source_type": "SITE_EXPORT", "source_id": "invalid-progress"},
        files={"upload": ("invalid.csv", invalid_csv, "text/csv")},
    )
    rejected = client.post(
        f"/api/v1/projects/{project_id}/evidence/imports/preview",
        headers={**headers, "Idempotency-Key": "invalid-run-001"},
        json={"artifact_id": invalid_upload.json()["id"], "mapping": {}},
    )
    assert rejected.status_code == 201, rejected.text
    assert rejected.json()["status"] == "REJECTED"
    assert rejected.json()["validation_errors"][0]["row"] == 2
    denied_commit = client.post(
        f"/api/v1/projects/{project_id}/evidence/imports/{rejected.json()['id']}/commit",
        headers=headers,
    )
    assert denied_commit.status_code == 409


def test_verification_creates_a_derived_fact_without_truth_inflation(
    evidence_api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, sessions = evidence_api
    _, project_id, headers, object_id = bootstrap(client)
    created = client.post(
        f"/api/v1/projects/{project_id}/evidence/items",
        headers=headers,
        json=evidence_item(controlled_object_id=object_id),
    )
    assert created.status_code == 201, created.text
    source_id = created.json()["id"]
    verified = client.post(
        f"/api/v1/projects/{project_id}/evidence/items/{source_id}/verify",
        headers=headers,
        json={
            "method": "Quantity surveyor measurement",
            "outcome": "VERIFIED",
            "rationale": "Checked against signed measurement sheet",
            "verified_confidence": "0.95",
        },
    )
    assert verified.status_code == 201, verified.text
    result_id = verified.json()["result_item_id"]
    assert result_id != source_id
    verifications = client.get(
        f"/api/v1/projects/{project_id}/evidence/verifications",
        headers=headers,
        params={"item_id": source_id},
    )
    relations = client.get(
        f"/api/v1/projects/{project_id}/evidence/relations",
        headers=headers,
        params={"item_id": source_id},
    )
    assert [event["id"] for event in verifications.json()] == [verified.json()["id"]]
    assert relations.json()[0]["relation_type"] == "DERIVED_FROM"

    with sessions() as session:
        source = session.get(EvidenceItem, uuid.UUID(source_id))
        result = session.get(EvidenceItem, uuid.UUID(result_id))
        assert source is not None and result is not None
        assert (source.semantic_state, source.truth_type) == ("REPORTED", "REPORTED_CLAIM")
        assert (result.semantic_state, result.truth_type) == ("VERIFIED", "VERIFIED_FACT")
        assert result.derived_from_item_id == source.id
        assert session.scalar(
            select(VerificationEvent).where(
                VerificationEvent.id == uuid.UUID(verified.json()["id"])
            )
        )
        relation = session.scalar(
            select(EvidenceRelation).where(EvidenceRelation.from_item_id == result.id)
        )
        assert relation is not None and relation.relation_type == "DERIVED_FROM"


def test_contradictions_requests_reliability_and_supersession_preserve_history(
    evidence_api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, sessions = evidence_api
    _, project_id, headers, object_id = bootstrap(client)
    item_url = f"/api/v1/projects/{project_id}/evidence/items"
    left = client.post(
        item_url, headers=headers, json=evidence_item(controlled_object_id=object_id, value=12)
    )
    right = client.post(
        item_url, headers=headers, json=evidence_item(controlled_object_id=object_id, value=18)
    )
    contradiction = client.post(
        f"/api/v1/projects/{project_id}/evidence/contradictions",
        headers=headers,
        json={
            "left_item_id": left.json()["id"],
            "right_item_id": right.json()["id"],
            "field_name": "installed_quantity",
            "material": True,
        },
    )
    assert contradiction.status_code == 201, contradiction.text
    resolved = client.post(
        f"/api/v1/projects/{project_id}/evidence/contradictions/"
        f"{contradiction.json()['id']}/resolve",
        headers=headers,
        json={
            "chosen_item_id": right.json()["id"],
            "resolution_policy": "SIGNED_MEASUREMENT_PREVAILS",
            "resolution_reason": "Right item has signed measurement support",
        },
    )
    assert resolved.json()["status"] == "RESOLVED"

    request = client.post(
        f"/api/v1/projects/{project_id}/evidence/requests",
        headers=headers,
        json={
            "controlled_object_id": object_id,
            "requested_fields": ["installed_quantity"],
            "reason": "Close quantity variance",
            "urgency": "URGENT",
            "owner_actor_id": "qs@example.test",
            "due_at": "2026-09-06T12:00:00Z",
        },
    )
    satisfied = client.post(
        f"/api/v1/projects/{project_id}/evidence/requests/{request.json()['id']}/satisfy",
        headers=headers,
        json={"evidence_item_id": right.json()["id"]},
    )
    assert satisfied.json()["status"] == "SATISFIED"

    reliability_url = f"/api/v1/projects/{project_id}/evidence/reliability"
    for score, date in (("0.55", "2026-09-01T00:00:00Z"), ("0.80", "2026-09-04T00:00:00Z")):
        response = client.post(
            reliability_url,
            headers=headers,
            json={
                "source_type": "SITE_TEAM",
                "source_id": "team-a",
                "evidence_class": "FIELD_REPORT",
                "score": score,
                "rationale": "Periodic source review",
                "valid_from": date,
            },
        )
        assert response.status_code == 201, response.text
    history = client.get(reliability_url, headers=headers, params={"source_id": "team-a"})
    assert [entry["score"] for entry in history.json()] == ["0.8000", "0.5500"]

    replacement = client.post(
        item_url,
        headers=headers,
        json=evidence_item(
            controlled_object_id=object_id,
            value=20,
            supersedes_item_id=left.json()["id"],
        ),
    )
    assert replacement.status_code == 201, replacement.text
    with sessions() as session:
        assert session.get(EvidenceItem, uuid.UUID(left.json()["id"])).status == "SUPERSEDED"
        assert len(list(session.scalars(select(EvidenceItem)))) == 3


@pytest.mark.parametrize(
    ("payload", "expected_status"),
    [
        ({"value": None, "truth_type": "REPORTED_CLAIM"}, 422),
        ({"value": None, "truth_type": "UNKNOWN"}, 201),
        ({"field_name": "physical_progress", "value": 0}, 422),
        (
            {
                "field_name": "physical_progress",
                "value": 0,
                "measurement_basis": "PHYSICAL_VERIFIED",
            },
            201,
        ),
    ],
)
def test_semantic_null_unknown_zero_and_progress_basis(
    evidence_api: tuple[TestClient, sessionmaker[Session]],
    payload: dict[str, Any],
    expected_status: int,
) -> None:
    client, _ = evidence_api
    _, project_id, headers, object_id = bootstrap(client)
    data = evidence_item(controlled_object_id=object_id)
    data.update(payload)
    response = client.post(
        f"/api/v1/projects/{project_id}/evidence/items", headers=headers, json=data
    )
    assert response.status_code == expected_status, response.text


def test_project_membership_is_required_for_evidence_access(
    evidence_api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = evidence_api
    organization_id, project_id, _, _ = bootstrap(client)
    denied = client.get(
        f"/api/v1/projects/{project_id}/evidence/items",
        headers={
            "X-VAI-Actor-ID": "outsider@example.test",
            "X-VAI-Organization-ID": organization_id,
        },
    )
    assert denied.status_code == 403
