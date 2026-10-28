"""Run against a freshly migrated disposable cluster; never create tables from ORM metadata."""

import json
import os
import subprocess
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from app.database import get_db
from app.main import app
from fastapi.testclient import TestClient
from postgres_load_probe import exercise_queue_read_load
from postgres_recovery import exercise_logical_recovery
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, sessionmaker
from test_bootstrap_controls import exercise_bootstrap_controls
from test_bootstrap_corrections import exercise_material_correction
from test_connected_acceptance import exercise_connected_acceptance
from test_governed_workbook_api import setup_import
from test_presentations_api import setup_presentation_source
from test_project_control_api import seed_control_inputs
from test_project_health import POLICY


def exercise_concurrent_context_activation(client, project_id, headers, tmp_path):
    base = f"/api/v1/projects/{project_id}"
    grant = client.post(
        f"{base}/authority-grants",
        headers=headers,
        json={"actor_id": headers["X-VAI-Actor-ID"], "authority_type": "BUDGET_APPROVAL"},
    )
    assert grant.status_code == 201, grant.text
    requests = []
    for number in (1, 2):
        source = client.post(
            f"{base}/authorized-context/versions",
            headers=headers,
            json={
                "context_type": "BUDGET",
                "semantic_state": "PROPOSED",
                "effective_from": "2026-01-01T00:00:00Z",
                "payload": {"currency": "USD", "approved_budget": str(number * 1000)},
            },
        )
        assert source.status_code == 201, source.text
        requests.append(
            {
                "source_version_id": source.json()["id"],
                "authority_grant_id": grant.json()["id"],
                "expected_current_context_id": None,
                "approval_reference": f"CONCURRENT-BUDGET-{number}",
                "reason": "Concurrent explicit human approval must preserve one current version.",
            }
        )
    barrier = threading.Barrier(2)

    def activate(index):
        barrier.wait(timeout=10)
        started = time.perf_counter()
        response = client.post(
            f"{base}/authorized-context/activate",
            headers={**headers, "Idempotency-Key": f"concurrent-budget-{index}"},
            json=requests[index],
        )
        return index, response, time.perf_counter() - started

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(activate, (0, 1)))
    assert sorted(response.status_code for _, response, _ in results) == [201, 409], [
        response.text for _, response, _ in results
    ]
    winner, approved, _ = next(item for item in results if item[1].status_code == 201)
    current = client.get(f"{base}/authorized-context/current/BUDGET", headers=headers)
    assert current.json()["id"] == approved.json()["id"]
    replay = client.post(
        f"{base}/authorized-context/activate",
        headers={**headers, "Idempotency-Key": f"concurrent-budget-{winner}"},
        json=requests[winner],
    )
    assert replay.status_code == 201, replay.text
    assert replay.json()["id"] == approved.json()["id"]
    (tmp_path / "context-concurrency.json").write_text(
        json.dumps(
            [
                {"request": index, "status": response.status_code, "seconds": elapsed}
                for index, response, elapsed in results
            ],
            indent=2,
        ),
        encoding="utf-8",
    )


@pytest.mark.skipif(
    not (os.getenv("VAI_TEST_POSTGRES_URL") and os.getenv("VAI_TEST_POSTGRES_BIN")),
    reason="Requires isolated PostgreSQL rehearsal and runtime tools",
)
def test_project_context_postgres_append_only_and_migrated_api(tmp_path, monkeypatch) -> None:
    engine = create_engine(os.environ["VAI_TEST_POSTGRES_URL"])
    assert engine.url.host == "127.0.0.1"
    assert engine.url.database == "vai_remediation"
    assert engine.url.password is None

    def override_db():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            suffix = uuid.uuid4().hex
            org = client.post(
                "/api/v1/organizations",
                headers={"X-VAI-Actor-ID": "migration@test", "X-VAI-Roles": "ORGANIZATION_ADMIN"},
                json={"name": "Migration rehearsal", "slug": suffix},
            )
            assert org.status_code == 201, org.text
            headers = {
                "X-VAI-Actor-ID": "migration@test",
                "X-VAI-Organization-ID": org.json()["id"],
            }
            project = client.post(
                f"/api/v1/organizations/{org.json()['id']}/projects",
                headers=headers,
                json={
                    "code": "R5",
                    "name": "Migration project",
                    "timezone": "Asia/Beirut",
                    "currency": "USD",
                    "delivery_model": "DESIGN_BID_BUILD",
                    "reporting_cadence": "WEEKLY",
                },
            )
            assert project.status_code == 201, project.text
            project_id = project.json()["id"]
            exercise_concurrent_context_activation(client, project_id, headers, tmp_path)
            created = client.post(
                f"/api/v1/projects/{project_id}/project-context/records",
                headers={**headers, "Idempotency-Key": "charter"},
                json={
                    "record_type": "CHARTER",
                    "record_key": "PROJECT_CHARTER",
                    "effective_from": "2026-09-04T00:00:00Z",
                    "payload": {
                        "objectives": ["Deliver"],
                        "success_criteria": ["Accepted"],
                        "delivery_strategy": "Phased",
                        "authority_reference": "Board",
                    },
                },
            )
            assert created.status_code == 201, created.text
            record_id = created.json()["id"]
            reviewed = client.post(
                f"/api/v1/projects/{project_id}/project-context/records/{record_id}/transitions?expected_version=0",
                headers={**headers, "Idempotency-Key": "review"},
                json={"to_status": "REVIEWED", "reason": "Human review"},
            )
            assert reviewed.status_code == 201, reviewed.text
            event_id = reviewed.json()["id"]
            workbook_data = setup_import(
                (client, sessionmaker(bind=engine), project_id, headers), tmp_path, monkeypatch
            )
            imported = client.post(
                f"/api/v1/projects/{project_id}/progress/workbook-imports",
                headers={**headers, "Idempotency-Key": "workbook"},
                json=workbook_data,
            )
            assert imported.status_code == 201, imported.text
            workbook_id = imported.json()["id"]
            health_project = client.post(
                f"/api/v1/organizations/{org.json()['id']}/projects",
                headers=headers,
                json={
                    "code": "R7",
                    "name": "Health migration project",
                    "timezone": "Asia/Beirut",
                    "currency": "USD",
                    "delivery_model": "DESIGN_BID_BUILD",
                    "reporting_cadence": "WEEKLY",
                },
            )
            assert health_project.status_code == 201, health_project.text
            health_project_id = health_project.json()["id"]
            body = seed_control_inputs(
                client, sessionmaker(bind=engine), health_project_id, headers
            )
            body["health_policy"] = {**POLICY, "owner_actor_id": headers["X-VAI-Actor-ID"]}
            health = client.post(
                f"/api/v1/projects/{health_project_id}/project-control/snapshots",
                headers={**headers, "Idempotency-Key": "health"},
                json=body,
            )
            assert health.status_code == 201, health.text
            assert health.json()["health"]["status"] == "RED"
            health_id = health.json()["id"]
        for table, row_id in (
            ("project_context_record", record_id),
            ("project_context_lifecycle_event", event_id),
            ("progress_workbook_import", workbook_id),
            ("project_control_snapshot", health_id),
        ):
            for command in (
                f"UPDATE {table} SET id = id WHERE id = :id",
                f"DELETE FROM {table} WHERE id = :id",
            ):
                with engine.connect() as connection:
                    with pytest.raises(DBAPIError, match="append.only|immutable"):
                        connection.execute(text(command), {"id": uuid.UUID(row_id)})
                    connection.rollback()
        with engine.connect() as connection:
            assert (
                connection.scalar(text("SELECT version_num FROM alembic_version"))
                == ScriptDirectory.from_config(
                    Config("services/api/alembic.ini")
                ).get_current_head()
            )
            context_count = connection.scalar(
                text("SELECT count(*) FROM authorized_context_version")
            )
            with pytest.raises(DBAPIError, match="uq_context_current_authorized"):
                connection.execute(
                    text(
                        "INSERT INTO authorized_context_version "
                        "(id, organization_id, project_id, context_type, version_number, "
                        "semantic_state, effective_from, payload, created_by) "
                        "SELECT :id, organization_id, project_id, context_type, "
                        "version_number + 100000, semantic_state, effective_from, payload, "
                        "created_by FROM authorized_context_version "
                        "WHERE semantic_state = 'CURRENT_AUTHORIZED' LIMIT 1"
                    ),
                    {"id": uuid.uuid4()},
                )
            connection.rollback()
        with engine.connect() as connection:
            assert (
                connection.scalar(text("SELECT count(*) FROM authorized_context_version"))
                == context_count
            )
        rollback = subprocess.run(
            [
                sys.executable,
                "-m",
                "alembic",
                "-c",
                "services/api/alembic.ini",
                "downgrade",
                "0028_progress_workbook_imports",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert rollback.returncode != 0
        assert "Cannot drop immutable health/context history" in rollback.stderr
        with engine.connect() as connection:
            assert (
                connection.scalar(
                    text("SELECT count(*) FROM project_control_snapshot WHERE id = :id"),
                    {"id": uuid.UUID(health_id)},
                )
                == 1
            )
        with TestClient(app) as client:
            base, deck_headers, report_id, recipient_id, _, _ = setup_presentation_source(
                (client, sessionmaker(bind=engine)), tmp_path, monkeypatch
            )
            deck = client.post(
                f"{base}/presentations",
                headers={**deck_headers, "Idempotency-Key": "postgres-deck"},
                json={"report_snapshot_id": report_id, "recipient_record_ids": [recipient_id]},
            )
            assert deck.status_code == 201, deck.text
            deck_id = deck.json()["id"]
            event_id = deck.json()["lifecycle_events"][0]["id"]
        for table, row_id in (
            ("presentation_artifact", deck_id),
            ("presentation_lifecycle_event", event_id),
        ):
            for command in (
                f"UPDATE {table} SET id = id WHERE id = :id",
                f"DELETE FROM {table} WHERE id = :id",
            ):
                with engine.connect() as connection:
                    with pytest.raises(DBAPIError, match="append.only|immutable"):
                        connection.execute(text(command), {"id": uuid.UUID(row_id)})
                    connection.rollback()
        rollback = subprocess.run(
            [
                sys.executable,
                "-m",
                "alembic",
                "-c",
                "services/api/alembic.ini",
                "downgrade",
                "0029_snapshot_health",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert rollback.returncode != 0
        assert "Cannot drop immutable presentation history" in rollback.stderr
        with engine.connect() as connection:
            assert (
                connection.scalar(
                    text("SELECT count(*) FROM presentation_artifact WHERE id = :id"),
                    {"id": uuid.UUID(deck_id)},
                )
                == 1
            )
        context_ids = exercise_bootstrap_controls((client, sessionmaker(bind=engine)))
        for context_id in context_ids:
            for statement in (
                "UPDATE authorized_context_version SET payload='{}' WHERE id=:id",
                "DELETE FROM authorized_context_version WHERE id=:id",
                "UPDATE authorized_context_version SET created_by='rewrite' WHERE id=:id",
            ):
                with (
                    pytest.raises(DBAPIError, match="immutable"),
                    engine.begin() as connection,
                ):
                    connection.execute(text(statement), {"id": uuid.UUID(context_id)})
        with (
            pytest.raises(DBAPIError, match="immutable"),
            engine.begin() as connection,
        ):
            connection.execute(text("TRUNCATE authorized_context_version CASCADE"))
        corrected_structure_id = exercise_material_correction(
            (client, sessionmaker(bind=engine)), concurrent=True
        )
        for statement in (
            "UPDATE boq_planning_structure_version SET reason='rewrite' WHERE id=:id",
            "DELETE FROM boq_planning_structure_version WHERE id=:id",
        ):
            with (
                pytest.raises(DBAPIError, match="append.only|immutable"),
                engine.begin() as connection,
            ):
                connection.execute(text(statement), {"id": uuid.UUID(corrected_structure_id)})
        with engine.connect() as connection:
            audit_count = connection.scalar(text("SELECT count(*) FROM audit_event"))
        for direction, target in (
            ("downgrade", "0030_presentation_artifacts"),
            ("upgrade", "head"),
        ):
            migration = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "alembic",
                    "-c",
                    "services/api/alembic.ini",
                    direction,
                    target,
                ],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            assert migration.returncode == 0, migration.stderr
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT count(*) FROM audit_event")) == audit_count
        exercise_connected_acceptance((client, sessionmaker(bind=engine)), tmp_path)
        exercise_connected_acceptance(
            (client, sessionmaker(bind=engine)), tmp_path / "five-package", 5
        )
        exercise_logical_recovery(engine, tmp_path, base, deck_headers, deck_id)
        if os.getenv("VAI_TEST_LOAD_PROFILE") == "1":
            exercise_queue_read_load(engine, tmp_path)
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
