import io
import uuid
from datetime import UTC, datetime

import pytest
from app.config import get_settings
from app.models import AuthorizedContextVersion, ProgressMeasurement, Project
from app.services.openai_schedule import build_openai_schedule_workbook
from openpyxl import load_workbook
from sqlalchemy import select
from test_project_context_api import context_api as context_api


def setup_import(context_api, tmp_path, monkeypatch, mutate=None):
    client, sessions, project_id, headers = context_api
    monkeypatch.setenv("VAI_EVIDENCE_STORAGE_PATH", str(tmp_path))
    get_settings.cache_clear()
    obj = client.post(
        f"/api/v1/projects/{project_id}/controlled-objects",
        headers=headers,
        json={"object_type": "ACTIVITY", "code": "A1", "name": "Excavation"},
    )
    assert obj.status_code == 201, obj.text
    schedule_id = uuid.uuid4()
    with sessions() as session:
        project = session.get(Project, uuid.UUID(project_id))
        session.add(
            AuthorizedContextVersion(
                id=schedule_id,
                organization_id=project.organization_id,
                project_id=project.id,
                context_type="SCHEDULE",
                version_number=1,
                semantic_state="CURRENT_AUTHORIZED",
                effective_from=datetime(2026, 9, 1, tzinfo=UTC),
                activated_at=datetime(2026, 9, 1, tzinfo=UTC),
                created_by="pm@test",
                payload={
                    "data_date": "2026-10-05",
                    "activities": [
                        {
                            "code": "A1",
                            "name": "Excavation",
                            "planned_start": "2026-10-01",
                            "planned_finish": "2026-10-10",
                            "controlled_object_code": "A1",
                            "calendar_id": "SITE",
                            "progress_plan": [],
                        }
                    ],
                    "calendars": [
                        {
                            "calendar_id": "SITE",
                            "working_weekdays": [0, 1, 2, 3, 4],
                            "holidays": ["2026-10-02"],
                        }
                    ],
                    "dependencies": [],
                },
            )
        )
        session.commit()
    content = build_openai_schedule_workbook(
        [
            {
                "id": 1,
                "name": "Excavation",
                "duration_days": 7,
                "start": "2026-10-01",
                "finish": "2026-10-10",
                "dependency_ids": [],
                "boq_references": [],
            }
        ]
    )
    workbook = load_workbook(io.BytesIO(content))
    workbook["Progress Report"]["G5"] = 25
    workbook["Progress Report"]["H5"] = "2026-10-05"
    if mutate:
        mutate(workbook)
    output = io.BytesIO()
    workbook.save(output)
    response = client.post(
        f"/api/v1/projects/{project_id}/evidence/artifacts",
        headers=headers,
        files={
            "upload": (
                "progress.xlsx",
                output.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        data={"source_type": "PROGRESS_WORKBOOK", "source_id": "Daily workbook"},
    )
    assert response.status_code == 201, response.text
    return {
        "artifact_id": response.json()["id"],
        "schedule_context_id": str(schedule_id),
        "data_date": "2026-10-05T15:00:00Z",
        "reported_confidence": "0.6",
        "mappings": [
            {"task_id": 1, "activity_code": "A1", "controlled_object_id": obj.json()["id"]}
        ],
    }


def test_workbook_persists_reported_evidence_exact_schedule_calendar_and_unknowns(
    context_api, tmp_path, monkeypatch
):
    client, sessions, project_id, headers = context_api
    data = setup_import(context_api, tmp_path, monkeypatch)
    path = f"/api/v1/projects/{project_id}/progress/workbook-imports"
    response = client.post(path, headers={**headers, "Idempotency-Key": "import-one"}, json=data)
    assert response.status_code == 201, response.text
    record = response.json()
    row = record["rows"][0]
    assert row["reported_percent"] == "25"
    assert row["truth_type"] == "REPORTED_CLAIM"
    assert row["planned_percent"] is None
    assert row["authorized_working_days_elapsed"] == "2"  # Thursday + Monday; Friday holiday
    assert row["measurement_id"] and row["evidence_item_id"]
    assert record["network_basis"]["calendars"][0]["calendar_id"] == "SITE"
    assert any(item["code"] == "DEADLINE_EXPOSURE_UNKNOWN" for item in record["limitations"])
    assert client.get(path, headers=headers).json()[0]["id"] == record["id"]
    assert client.get(f"{path}/{record['id']}", headers=headers).json() == record
    assert (
        client.post(path, headers={**headers, "Idempotency-Key": "import-one"}, json=data).json()[
            "id"
        ]
        == record["id"]
    )
    assert (
        client.post(
            path, headers={**headers, "Idempotency-Key": "other-key"}, json=data
        ).status_code
        == 409
    )
    assert (
        client.post(
            path,
            headers={**headers, "Idempotency-Key": "import-one"},
            json={**data, "reported_confidence": "0.9"},
        ).status_code
        == 409
    )
    with sessions() as session:
        measurements = list(session.scalars(select(ProgressMeasurement)))
        assert len(measurements) == 1
        assert measurements[0].measurement_kind == "REPORTED"
        assert measurements[0].semantic_state == "REPORTED"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda w: setattr(w["Progress Report"]["G5"], "value", "=100"),
        lambda w: setattr(w["Progress Report"]["G5"], "value", 101),
        lambda w: setattr(w["Progress Report"]["H5"], "value", "2026-10-06"),
        lambda w: setattr(w["Progress Report"]["C5"], "value", "Other scope"),
        lambda w: setattr(w["Tasks"]["E2"], "value", "2026-10-11"),
        lambda w: setattr(w["Progress Report"]["B5"], "value", 1.5),
    ],
)
def test_workbook_rejects_formula_invalid_percent_dates_and_scope(
    context_api, tmp_path, monkeypatch, mutate
):
    client, sessions, project_id, headers = context_api
    data = setup_import(context_api, tmp_path, monkeypatch, mutate)
    response = client.post(
        f"/api/v1/projects/{project_id}/progress/workbook-imports",
        headers={**headers, "Idempotency-Key": "bad"},
        json=data,
    )
    assert response.status_code == 422, response.text
    with sessions() as session:
        assert list(session.scalars(select(ProgressMeasurement))) == []


def test_workbook_denies_missing_mapping_stale_schedule_and_cross_tenant(
    context_api, tmp_path, monkeypatch
):
    client, sessions, project_id, headers = context_api
    data = setup_import(context_api, tmp_path, monkeypatch)
    path = f"/api/v1/projects/{project_id}/progress/workbook-imports"
    assert (
        client.post(
            path, headers={**headers, "Idempotency-Key": "bad"}, json={**data, "mappings": []}
        ).status_code
        == 422
    )
    assert (
        client.post(
            path,
            headers={
                **headers,
                "Idempotency-Key": "bad",
                "X-VAI-Organization-ID": str(uuid.uuid4()),
            },
            json=data,
        ).status_code
        == 403
    )
    with sessions() as session:
        context = session.get(AuthorizedContextVersion, uuid.UUID(data["schedule_context_id"]))
        context.semantic_state = "SUPERSEDED"
        session.commit()
    assert (
        client.post(path, headers={**headers, "Idempotency-Key": "bad"}, json=data).status_code
        == 422
    )


def test_workbook_preserves_unreported_as_unknown_without_measurement(
    context_api, tmp_path, monkeypatch
):
    client, sessions, project_id, headers = context_api
    data = setup_import(
        context_api,
        tmp_path,
        monkeypatch,
        lambda w: setattr(w["Progress Report"]["G5"], "value", None),
    )
    response = client.post(
        f"/api/v1/projects/{project_id}/progress/workbook-imports",
        headers={**headers, "Idempotency-Key": "unknown"},
        json=data,
    )
    assert response.status_code == 201, response.text
    row = response.json()["rows"][0]
    assert row["reported_percent"] is None
    assert row["measurement_id"] is None
    assert row["truth_type"] == "UNKNOWN"
    with sessions() as session:
        assert list(session.scalars(select(ProgressMeasurement))) == []
