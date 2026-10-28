"""BOQ review inputs remain proposed until exact human schedule approval."""

import uuid
from copy import deepcopy
from datetime import UTC, datetime

from app.models import AuthorizedContextVersion
from sqlalchemy import select
from test_bootstrap_corrections import setup_correction
from test_evidence_api import evidence_api as evidence_api


def exercise_bootstrap_controls(api):
    client, sessions = api
    base, headers, draft, _, _, correction, create = setup_correction(
        api, project_suffix="controls"
    )
    successor = create(
        f"/bootstrap/schedule-drafts/{draft['id']}/corrections", correction, "control-correction"
    )
    calculation = create(
        f"/bootstrap/schedule-drafts/{successor['id']}/calculations",
        {"project_start": "2026-10-05"},
        "control-calculation",
    )
    assert calculation["readiness"] == "PLANNER_REVIEW_REQUIRED"
    details = client.get(
        f"{base}/bootstrap/schedule-drafts/{successor['id']}", headers=headers
    ).json()
    execution = next(a for a in details["activities"] if a["activity_type"] == "EXECUTION")
    controlled = create(
        "/controlled-objects",
        {"object_type": "WORK_PACKAGE", "code": "WP-CONTROL", "name": "Reviewed scope"},
        "control-object",
    )
    control = {
        "activity_code": execution["activity_code"],
        "controlled_object_id": controlled["id"],
        "measurement_basis": "PHYSICAL_VERIFIED",
        "progress_plan": [
            {
                "as_of": datetime.now(UTC).date().isoformat(),
                "numerator": "200",
                "denominator": "200",
                "unit": "m3",
                "measurement_basis": "PHYSICAL_VERIFIED",
            }
        ],
        "source_reference": "Synthetic planner quantity plan, revision 1",
    }
    review_path = f"/bootstrap/schedule-calculations/{calculation['id']}/reviews"
    review_data = {
        "reason": "Explicit planner review of scope and planned quantities.",
        "control_inputs": [control],
    }
    invalid = []
    for field, value in (
        ("controlled_object_id", str(uuid.uuid4())),
        ("activity_code", "OUTSIDE"),
        ("source_reference", "  "),
        ("authorized", True),
    ):
        bad = deepcopy(control)
        bad[field] = value
        invalid.append([bad])
    invalid.append([control, control])
    bad = deepcopy(control)
    bad["progress_plan"][0]["measurement_basis"] = "PHYSICAL_EXECUTED"
    invalid.append([bad])
    bad = deepcopy(control)
    bad["progress_plan"] *= 2
    invalid.append([bad])
    for index, inputs in enumerate(invalid):
        response = client.post(
            f"{base}{review_path}",
            headers={**headers, "Idempotency-Key": f"invalid-control-{index}"},
            json={**review_data, "control_inputs": inputs},
        )
        assert response.status_code == 422, response.text
    reviewed = create(review_path, review_data, "control-review")
    assert create(review_path, review_data, "control-review")["id"] == reviewed["id"]
    assert (
        client.get(f"{base}/authorized-context/current/SCHEDULE", headers=headers).status_code
        == 404
    )
    assert reviewed["edit_history"][0]["original_value"]["progress_plan"] == []
    assert reviewed["edit_history"][0]["revised_value"]["progress_plan"] == control["progress_plan"]
    grant = create(
        "/authority-grants",
        {"actor_id": headers["X-VAI-Actor-ID"], "authority_type": "BASELINE_SCHEDULE_APPROVAL"},
        "baseline-grant",
    )
    approval = {
        "authority_grant_id": grant["id"],
        "authorize_as_baseline": True,
        "approval_reference": "CONTROL-BASELINE-1",
        "reason": "Human approves the explicit baseline and current schedule.",
    }
    approved = create(
        f"/bootstrap/schedule-releases/{reviewed['id']}/approve", approval, "control-approve"
    )
    assert approved["schedule_payload"]["activities"] == reviewed["schedule_payload"]["activities"]
    assert (
        create(
            f"/bootstrap/schedule-releases/{reviewed['id']}/approve", approval, "control-approve"
        )["id"]
        == approved["id"]
    )
    current = client.get(f"{base}/authorized-context/current/SCHEDULE", headers=headers).json()
    baseline_id = approved["schedule_payload"]["authorization_lineage"]["baseline_context_id"]
    assert baseline_id != current["id"]
    assert current["source_version_id"] == baseline_id
    assert current["payload"]["authorization_lineage"]["baseline_context_id"] == baseline_id
    activity = next(
        a for a in current["payload"]["activities"] if a["code"] == execution["activity_code"]
    )
    assert activity["controlled_object_code"] == "WP-CONTROL"
    assert activity["progress_plan"] == control["progress_plan"]
    assert current["payload"]["bootstrap_lineage"]["reviewed_release_id"] == reviewed["id"]
    assert (
        current["payload"]["bootstrap_control_inputs"][0]["source_reference"]
        == control["source_reference"]
    )
    evidence = create(
        "/evidence/items",
        {
            "controlled_object_id": controlled["id"],
            "field_name": "planned_progress",
            "value": "200",
            "unit": "m3",
            "measurement_basis": "PHYSICAL_VERIFIED",
            "semantic_state": "CURRENT_AUTHORIZED",
            "truth_type": "JUDGMENT",
            "as_of": datetime.now(UTC).isoformat(),
            "confidence": "1",
        },
        "planned-evidence",
    )
    measurement = {
        "evidence_item_id": evidence["id"],
        "authorized_context_id": current["id"],
        "measurement_kind": "PLANNED_AUTHORIZED",
        "numerator": "200",
        "denominator": "200",
        "unit": "m3",
    }
    wrong = client.post(
        f"{base}/progress/measurements",
        headers=headers,
        json={**measurement, "denominator": "400"},
    )
    assert wrong.status_code == 422 and "not present" in wrong.text
    planned = create("/progress/measurements", measurement, "planned-measurement")
    assert planned["authorized_context_id"] == current["id"]
    assert planned["measurement_kind"] == "PLANNED_AUTHORIZED"
    with sessions() as session:
        baseline = session.get(AuthorizedContextVersion, uuid.UUID(baseline_id))
        assert baseline.semantic_state == "BASELINE"
        assert baseline.activated_by == headers["X-VAI-Actor-ID"]
        baseline_payload = deepcopy(baseline.payload)
    unapproved = create(
        "/authorized-context/versions",
        {
            "context_type": "SCHEDULE",
            "semantic_state": "BASELINE",
            "effective_from": datetime.now(UTC).isoformat(),
            "payload": current["payload"],
        },
        "unapproved-baseline-source",
    )
    assert unapproved["id"] != baseline_id
    # A new current release must retain the baseline rather than silently replacing it.
    later_review = create(review_path, review_data, "later-control-review")
    current_grant = create(
        "/authority-grants",
        {"actor_id": headers["X-VAI-Actor-ID"], "authority_type": "CURRENT_SCHEDULE_APPROVAL"},
        "current-grant",
    )
    later = create(
        f"/bootstrap/schedule-releases/{later_review['id']}/approve",
        {**approval, "authority_grant_id": current_grant["id"], "authorize_as_baseline": False},
        "later-control-approve",
    )
    with sessions() as session:
        assert (
            session.get(AuthorizedContextVersion, uuid.UUID(baseline_id)).payload
            == baseline_payload
        )
        old = session.get(AuthorizedContextVersion, uuid.UUID(current["id"]))
        assert old.semantic_state == "SUPERSEDED" and old.superseded_at
        new = session.get(AuthorizedContextVersion, uuid.UUID(later["authorized_context_id"]))
        assert new.payload["authorization_lineage"]["baseline_context_id"] == baseline_id
        assert new.source_version_id != uuid.UUID(baseline_id)
        assert (
            session.get(AuthorizedContextVersion, new.source_version_id).semantic_state
            == "PROPOSED"
        )
        assert (
            len(
                list(
                    session.scalars(
                        select(AuthorizedContextVersion).where(
                            AuthorizedContextVersion.project_id
                            == uuid.UUID(successor["project_id"])
                        )
                    )
                )
            )
            == 5
        )
    return baseline_id, current["id"], later["authorized_context_id"]


def test_planned_control_inputs_and_distinct_baseline_survive_current_supersession(evidence_api):
    exercise_bootstrap_controls(evidence_api)
