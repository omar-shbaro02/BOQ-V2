import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from app.database import Base, get_db
from app.main import app
from app.models import DecisionCaseShell, OutboxEvent, Signal, SignalDetectionRun
from app.storage import LocalEvidenceStore, get_evidence_store
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture
def signal_api(
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
    client = TestClient(app)
    try:
        yield client, sessions
    finally:
        client.close()
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)


def bootstrap(client: TestClient) -> tuple[str, str, dict[str, str], dict[str, str]]:
    marker = uuid.uuid4().hex[:8]
    actor = f"signal-admin-{marker}@example.test"
    organization = client.post(
        "/api/v1/organizations",
        headers={"X-VAI-Actor-ID": actor, "X-VAI-Roles": "ORGANIZATION_ADMIN"},
        json={"name": "Signal Org", "slug": f"signal-org-{marker}"},
    )
    organization_id = organization.json()["id"]
    headers = {"X-VAI-Actor-ID": actor, "X-VAI-Organization-ID": organization_id}
    project = client.post(
        f"/api/v1/organizations/{organization_id}/projects",
        headers=headers,
        json={
            "code": f"SIG-{marker}",
            "name": "Signal Pilot",
            "timezone": "Asia/Beirut",
            "currency": "USD",
            "delivery_model": "DESIGN_BID_BUILD",
            "reporting_cadence": "WEEKLY",
        },
    )
    project_id = project.json()["id"]
    objects: dict[str, str] = {}
    for code in ("WP-A", "WP-B"):
        response = client.post(
            f"/api/v1/projects/{project_id}/controlled-objects",
            headers=headers,
            json={"object_type": "WORK_PACKAGE", "code": code, "name": code},
        )
        objects[code] = response.json()["id"]
    return organization_id, project_id, headers, objects


def add_evidence(
    client: TestClient,
    project_id: str,
    headers: dict[str, str],
    object_id: str,
    field: str,
    value: Any,
    *,
    as_of: datetime | None = None,
) -> dict[str, Any]:
    response = client.post(
        f"/api/v1/projects/{project_id}/evidence/items",
        headers=headers,
        json={
            "controlled_object_id": object_id,
            "field_name": field,
            "value": value,
            "semantic_state": "REPORTED",
            "truth_type": "REPORTED_CLAIM",
            "as_of": (as_of or datetime.now(UTC)).isoformat(),
            "confidence": "0.70",
            **({"measurement_basis": "PHYSICAL_VERIFIED"} if "progress" in field else {}),
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def detect(
    client: TestClient,
    project_id: str,
    headers: dict[str, str],
    key: str,
    *,
    evidence_ids: list[str] | None = None,
    contradiction_ids: list[str] | None = None,
):
    return client.post(
        f"/api/v1/projects/{project_id}/signals/detect",
        headers={**headers, "Idempotency-Key": key},
        json={
            "evidence_item_ids": evidence_ids or [],
            "contradiction_ids": contradiction_ids or [],
        },
    )


def screen_relevant(client: TestClient, project_id: str, headers: dict[str, str], signal: dict):
    response = client.post(
        f"/api/v1/projects/{project_id}/signals/{signal['id']}/screen",
        headers=headers,
        json={
            "expected_version": signal["workflow_version"],
            "outcome": "RELEVANT",
            "reason_code": "MATERIAL_THRESHOLD_CROSSED",
            "rationale": "Candidate warrants case-correlation review",
            "materiality_candidate": signal["materiality_candidate"],
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["signal"]


def test_five_deterministic_detectors_dedupe_and_publish_outbox(
    signal_api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, sessions = signal_api
    _, project_id, headers, objects = bootstrap(client)
    duplicate_time = datetime.now(UTC)
    evidence = [
        add_evidence(
            client,
            project_id,
            headers,
            objects["WP-A"],
            "progress_variance",
            -0.15,
            as_of=duplicate_time,
        ),
        add_evidence(
            client,
            project_id,
            headers,
            objects["WP-A"],
            "progress_variance",
            -0.15,
            as_of=duplicate_time,
        ),
        add_evidence(client, project_id, headers, objects["WP-A"], "schedule_variance_days", 8),
        add_evidence(client, project_id, headers, objects["WP-A"], "cost_variance_pct", 0.07),
        add_evidence(client, project_id, headers, objects["WP-A"], "milestone_days_to_impact", 10),
    ]
    conflict_left = add_evidence(
        client, project_id, headers, objects["WP-A"], "installed_quantity", 10
    )
    conflict_right = add_evidence(
        client, project_id, headers, objects["WP-A"], "installed_quantity", 15
    )
    contradiction = client.post(
        f"/api/v1/projects/{project_id}/evidence/contradictions",
        headers=headers,
        json={
            "left_item_id": conflict_left["id"],
            "right_item_id": conflict_right["id"],
            "field_name": "installed_quantity",
            "material": True,
        },
    ).json()
    response = detect(
        client,
        project_id,
        headers,
        "detect-five",
        evidence_ids=[item["id"] for item in evidence],
        contradiction_ids=[contradiction["id"]],
    )
    assert response.status_code == 201, response.text
    result = response.json()
    assert {signal["signal_type"] for signal in result["signals"]} == {
        "PROGRESS_VARIANCE",
        "SCHEDULE_VARIANCE",
        "COST_VARIANCE",
        "MILESTONE_EXPOSURE",
        "EVIDENCE_CONFLICT",
    }
    progress_signal = next(
        signal for signal in result["signals"] if signal["signal_type"] == "PROGRESS_VARIANCE"
    )
    assert progress_signal["occurrence_count"] == 2
    assert len(progress_signal["source_evidence_ids"]) == 2
    assert all(
        signal["occurrence_count"] == 1
        for signal in result["signals"]
        if signal["signal_type"] != "PROGRESS_VARIANCE"
    )
    repeated = detect(
        client,
        project_id,
        headers,
        "detect-five",
        evidence_ids=[item["id"] for item in evidence],
        contradiction_ids=[contradiction["id"]],
    )
    assert repeated.json()["run"]["id"] == result["run"]["id"]
    mismatch = detect(
        client,
        project_id,
        headers,
        "detect-five",
        evidence_ids=[evidence[0]["id"]],
    )
    assert mismatch.status_code == 409
    with sessions() as session:
        assert len(list(session.scalars(select(Signal)))) == 5
        assert len(list(session.scalars(select(SignalDetectionRun)))) == 1
        assert (
            len(
                list(
                    session.scalars(
                        select(OutboxEvent).where(OutboxEvent.event_type == "SignalRaised")
                    )
                )
            )
            == 5
        )


def test_screening_uses_versions_reasons_defer_and_explicit_expiry(
    signal_api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, sessions = signal_api
    _, project_id, headers, objects = bootstrap(client)
    evidence = add_evidence(
        client, project_id, headers, objects["WP-A"], "schedule_variance_days", 9
    )
    signal = detect(
        client, project_id, headers, "screen-one", evidence_ids=[evidence["id"]]
    ).json()["signals"][0]
    defer_until = datetime.now(UTC) + timedelta(days=2)
    deferred = client.post(
        f"/api/v1/projects/{project_id}/signals/{signal['id']}/screen",
        headers=headers,
        json={
            "expected_version": 1,
            "outcome": "DEFER",
            "reason_code": "AWAITING_EVIDENCE",
            "rationale": "Awaiting the next accepted schedule update",
            "materiality_candidate": "MEDIUM",
            "defer_until": defer_until.isoformat(),
        },
    )
    assert deferred.json()["signal"]["status"] == "DEFERRED"
    stale = client.post(
        f"/api/v1/projects/{project_id}/signals/{signal['id']}/screen",
        headers=headers,
        json={
            "expected_version": 1,
            "outcome": "DISMISS",
            "reason_code": "TRANSIENT_NOISE",
            "rationale": "Stale reviewer attempted overwrite",
            "materiality_candidate": "LOW",
        },
    )
    assert stale.status_code == 409
    with sessions() as session:
        stored = session.get(Signal, uuid.UUID(signal["id"]))
        stored.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        session.commit()
    expired = client.post(f"/api/v1/projects/{project_id}/signals/expire-due", headers=headers)
    assert expired.status_code == 200, expired.text
    assert expired.json()["expired_signal_ids"] == [signal["id"]]
    history = client.get(
        f"/api/v1/projects/{project_id}/signals/{signal['id']}/screenings", headers=headers
    )
    assert history.json()[0]["reason_code"] == "AWAITING_EVIDENCE"


def test_reviewed_correlation_opens_then_links_without_forced_merge(
    signal_api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = signal_api
    _, project_id, headers, objects = bootstrap(client)
    now = datetime.now(UTC)
    first_evidence = add_evidence(
        client, project_id, headers, objects["WP-A"], "schedule_variance_days", 8, as_of=now
    )
    first = detect(
        client, project_id, headers, "correlate-1", evidence_ids=[first_evidence["id"]]
    ).json()["signals"][0]
    first = screen_relevant(client, project_id, headers, first)
    suggestion = client.post(
        f"/api/v1/projects/{project_id}/signals/{first['id']}/correlation-suggestion",
        headers=headers,
    )
    assert suggestion.json()["suggested_outcome"] == "OPEN_NEW"
    opened = client.post(
        f"/api/v1/projects/{project_id}/correlation-suggestions/{suggestion.json()['id']}/review",
        headers=headers,
        json={
            "expected_signal_version": first["workflow_version"],
            "status": "ACCEPTED",
            "selected_outcome": "OPEN_NEW",
            "case_title": "Package A schedule exposure",
            "case_owner_actor_id": "pm@example.test",
            "rationale": "No existing case covers this condition",
        },
    )
    assert opened.status_code == 200, opened.text
    case_id = opened.json()["case"]["id"]
    assert opened.json()["signal"]["status"] == "CORRELATED"

    related_evidence = add_evidence(
        client,
        project_id,
        headers,
        objects["WP-A"],
        "cost_variance_pct",
        0.08,
        as_of=now + timedelta(minutes=1),
    )
    related = detect(
        client, project_id, headers, "correlate-2", evidence_ids=[related_evidence["id"]]
    ).json()["signals"][0]
    related = screen_relevant(client, project_id, headers, related)
    related_suggestion = client.post(
        f"/api/v1/projects/{project_id}/signals/{related['id']}/correlation-suggestion",
        headers=headers,
    ).json()
    assert related_suggestion["suggested_outcome"] == "LINK_EXISTING"
    assert related_suggestion["target_case_id"] == case_id

    independent_evidence = add_evidence(
        client,
        project_id,
        headers,
        objects["WP-B"],
        "progress_variance",
        -0.18,
        as_of=now + timedelta(minutes=2),
    )
    independent = detect(
        client,
        project_id,
        headers,
        "correlate-independent",
        evidence_ids=[independent_evidence["id"]],
    ).json()["signals"][0]
    independent = screen_relevant(client, project_id, headers, independent)
    independent_suggestion = client.post(
        f"/api/v1/projects/{project_id}/signals/{independent['id']}/correlation-suggestion",
        headers=headers,
    ).json()
    assert independent_suggestion["suggested_outcome"] == "OPEN_NEW"
    assert independent_suggestion["target_case_id"] is None


def test_correlation_requires_review_and_project_membership(
    signal_api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, sessions = signal_api
    organization_id, project_id, headers, objects = bootstrap(client)
    evidence = add_evidence(
        client, project_id, headers, objects["WP-A"], "progress_variance", -0.12
    )
    signal = detect(
        client, project_id, headers, "review-boundary", evidence_ids=[evidence["id"]]
    ).json()["signals"][0]
    signal = screen_relevant(client, project_id, headers, signal)
    suggestion = client.post(
        f"/api/v1/projects/{project_id}/signals/{signal['id']}/correlation-suggestion",
        headers=headers,
    ).json()
    rejected = client.post(
        f"/api/v1/projects/{project_id}/correlation-suggestions/{suggestion['id']}/review",
        headers=headers,
        json={
            "expected_signal_version": signal["workflow_version"],
            "status": "REJECTED",
            "rationale": "Correlation logic needs more object context",
        },
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["case"] is None
    assert rejected.json()["signal"]["status"] == "SCREENED"
    with sessions() as session:
        assert session.scalar(select(DecisionCaseShell.id)) is None

    denied = client.get(
        f"/api/v1/projects/{project_id}/signals",
        headers={
            "X-VAI-Actor-ID": "outsider@example.test",
            "X-VAI-Organization-ID": organization_id,
        },
    )
    assert denied.status_code == 403


def test_cross_cutting_parent_requires_two_reviewed_child_cases(
    signal_api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, sessions = signal_api
    _, project_id, headers, objects = bootstrap(client)
    now = datetime.now(UTC)
    cases: list[str] = []
    for index, (field, value) in enumerate(
        (("schedule_variance_days", 8), ("cost_variance_pct", 0.08)), start=1
    ):
        evidence = add_evidence(
            client,
            project_id,
            headers,
            objects["WP-A"],
            field,
            value,
            as_of=now + timedelta(minutes=index),
        )
        signal = detect(
            client, project_id, headers, f"cross-child-{index}", evidence_ids=[evidence["id"]]
        ).json()["signals"][0]
        signal = screen_relevant(client, project_id, headers, signal)
        suggestion = client.post(
            f"/api/v1/projects/{project_id}/signals/{signal['id']}/correlation-suggestion",
            headers=headers,
        ).json()
        opened = client.post(
            f"/api/v1/projects/{project_id}/correlation-suggestions/{suggestion['id']}/review",
            headers=headers,
            json={
                "expected_signal_version": signal["workflow_version"],
                "status": "ACCEPTED",
                "selected_outcome": "OPEN_NEW",
                "case_title": f"Independent child case {index}",
                "case_owner_actor_id": "pm@example.test",
                "rationale": "Reviewer determined this condition needs an independent case",
            },
        )
        assert opened.status_code == 200, opened.text
        cases.append(opened.json()["case"]["id"])

    evidence = add_evidence(
        client,
        project_id,
        headers,
        objects["WP-A"],
        "progress_variance",
        -0.16,
        as_of=now + timedelta(minutes=3),
    )
    signal = detect(
        client, project_id, headers, "cross-parent", evidence_ids=[evidence["id"]]
    ).json()["signals"][0]
    signal = screen_relevant(client, project_id, headers, signal)
    suggestion = client.post(
        f"/api/v1/projects/{project_id}/signals/{signal['id']}/correlation-suggestion",
        headers=headers,
    ).json()
    assert suggestion["suggested_outcome"] == "CROSS_CUTTING_PARENT_CHILD"
    assert set(suggestion["child_case_ids"]) == set(cases)
    accepted = client.post(
        f"/api/v1/projects/{project_id}/correlation-suggestions/{suggestion['id']}/review",
        headers=headers,
        json={
            "expected_signal_version": signal["workflow_version"],
            "status": "ACCEPTED",
            "selected_outcome": "CROSS_CUTTING_PARENT_CHILD",
            "child_case_ids": cases,
            "case_title": "Cross-cutting package control condition",
            "case_owner_actor_id": "project-director@example.test",
            "rationale": "A shared package condition credibly spans both independent cases",
        },
    )
    assert accepted.status_code == 200, accepted.text
    parent_id = accepted.json()["case"]["id"]
    with sessions() as session:
        children = list(
            session.scalars(
                select(DecisionCaseShell).where(
                    DecisionCaseShell.id.in_([uuid.UUID(value) for value in cases])
                )
            )
        )
        assert all(str(child.parent_case_id) == parent_id for child in children)
