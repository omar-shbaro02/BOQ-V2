import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from io import BytesIO

import pytest
from app.models import (
    AuditEvent,
    BoqPlanningStructureVersion,
    Membership,
    PlanningAssumption,
    Project,
    ProposedScheduleActivity,
    ScheduleDraftGeneration,
    ScheduleLogicProposal,
)
from app.services.bootstrap_corrections import logic_inputs
from openpyxl import Workbook
from sqlalchemy import func, select
from test_evidence_api import bootstrap
from test_evidence_api import evidence_api as evidence_api


def setup_correction(api, assumed_calendar=False, project_suffix=None):
    client, _ = api
    if project_suffix:
        from test_project_control_api import bootstrap_project

        organization_id, project_id, headers = bootstrap_project(client, project_suffix)
    else:
        organization_id, project_id, headers, _ = bootstrap(client)
    base = f"/api/v1/projects/{project_id}"

    def create(path, data, key):
        response = client.post(
            f"{base}{path}", headers={**headers, "Idempotency-Key": key}, json=data
        )
        assert response.status_code == 201, response.text
        return response.json()

    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Item", "Description", "Quantity", "Unit"])
    sheet.append(["C-1", "Concrete foundations", 120, "m3"])
    sheet.append(["C-2", "Concrete columns", 80, "m3"])
    sheet.append(["P-1", "Supply pumps", 2, "No"])
    content = BytesIO()
    workbook.save(content)
    artifact = client.post(
        f"{base}/evidence/artifacts",
        headers=headers,
        data={"source_type": "BOQ", "source_id": "correction-fixture"},
        files={"upload": ("correction.xlsx", content.getvalue())},
    )
    assert artifact.status_code == 201, artifact.text
    source = create("/bootstrap/boq-sources", {"artifact_id": artifact.json()["id"]}, "source")
    create(f"/bootstrap/boq-sources/{source['id']}/normalizations", {}, "normalize")
    structure = create(
        f"/bootstrap/boq-sources/{source['id']}/planning-structures", {}, "structure"
    )
    reviewed = create(
        f"/bootstrap/planning-structures/{structure['id']}/revisions",
        {"action": "ACCEPT_PROPOSAL", "reason": "Planner checked package and source allocation."},
        "review-structure",
    )
    draft = create(
        f"/bootstrap/planning-structures/{reviewed['id']}/schedule-drafts",
        {"validation_owner": headers["X-VAI-Actor-ID"]},
        "draft",
    )
    detail = client.get(f"{base}/bootstrap/schedule-drafts/{draft['id']}", headers=headers).json()
    by_type = {item["activity_type"]: item for item in detail["activities"]}
    logic = create(
        f"/bootstrap/schedule-drafts/{draft['id']}/logic",
        {
            "validation_owner": headers["X-VAI-Actor-ID"],
            "calendar": None
            if assumed_calendar
            else {
                "name": "Reviewed working calendar",
                "working_weekdays": [0, 1, 2, 3, 4],
                "working_hours_per_day": 8,
                "review_state": "ACCEPTED",
            },
            "dependencies": [
                {
                    "predecessor_activity_id": by_type["DELIVERY"]["id"],
                    "successor_activity_id": by_type["EXECUTION"]["id"],
                    "relation_type": "FINISH_TO_START",
                    "basis": "PHYSICAL_PREREQUISITE",
                    "source_reference": "Delivery before execution",
                    "confidence": "HIGH",
                    "review_state": "ACCEPTED",
                }
            ],
            "sequence_templates": [
                {
                    "predecessor_activity_id": by_type["SUBMITTAL"]["id"],
                    "successor_activity_id": by_type["EXECUTION"]["id"],
                    "basis": "VALIDATED_SEQUENCE_TEMPLATE",
                    "source_reference": "Reviewed construction sequence template",
                    "confidence": "HIGH",
                    "review_state": "ACCEPTED",
                }
            ],
            "milestones": [
                {
                    "code": "MS-1",
                    "name": "Required completion",
                    "target_date": "2026-11-01",
                    "source_type": "CONTRACT_EVIDENCE",
                    "source_reference": "Synthetic contract requirement",
                    "feeds_from_activity_ids": [by_type["EXECUTION"]["id"]],
                }
            ],
            "constraints": [
                {
                    "activity_id": by_type["EXECUTION"]["id"],
                    "constraint_type": "START_NO_EARLIER_THAN",
                    "constraint_date": "2026-10-05",
                    "source_reference": "Reviewed access date",
                }
            ],
        },
        "logic",
    )
    payload = {
        "expected_structure_version_id": reviewed["id"],
        "expected_logic_proposal_id": logic["id"],
        "reason": "Planner supplied defensible durations for unresolved activities.",
        "draft_inputs": {
            "validation_owner": headers["X-VAI-Actor-ID"],
            "duration_inputs": [
                {
                    "work_package_id": item["work_package_id"],
                    "activity_type": item["activity_type"],
                    "duration_working_days": "4" if item["activity_type"] == "EXECUTION" else "1",
                    "basis": "EXPLICIT_PROJECT_DURATION",
                    "source_reference": "Synthetic planner duration record",
                    "confidence": "HIGH",
                }
                for item in detail["activities"]
            ],
        },
    }
    return base, headers, draft, detail, logic, payload, create


def exercise_material_correction(api, concurrent=False):
    client, sessions = api
    base, headers, draft, original, original_logic, payload, create = setup_correction(api)
    path = f"/bootstrap/schedule-drafts/{draft['id']}/corrections"
    successor = create(path, payload, "correct-1")
    assert successor["id"] != draft["id"]
    assert create(path, payload, "correct-1")["id"] == successor["id"]
    mismatch = client.post(
        f"{base}{path}",
        headers={**headers, "Idempotency-Key": "correct-1"},
        json={**payload, "reason": "Different reason cannot reuse the accepted command key."},
    )
    assert mismatch.status_code == 409
    unchanged = client.get(f"{base}/bootstrap/schedule-drafts/{draft['id']}", headers=headers)
    assert unchanged.json() == original
    old_logic = client.get(f"{base}/bootstrap/schedule-drafts/{draft['id']}/logic", headers=headers)
    assert old_logic.json() == original_logic
    detail = client.get(
        f"{base}/bootstrap/schedule-drafts/{successor['id']}", headers=headers
    ).json()
    history = detail["correction_history"]
    assert detail["source_version_id"] == original["source_version_id"]
    assert detail["source_version_number"] == original["source_version_number"] == 1
    assert history["generation_id"] == successor["id"]
    assert history["previous_generation_id"] == draft["id"]
    assert history["previous_logic_proposal_id"] == original_logic["id"]
    assert history["actor_id"] == headers["X-VAI-Actor-ID"]
    assert history["reason"] == payload["reason"]
    assert history["recorded_at"]
    assert all(change["original_value"] is None for change in history["changes"])
    assert all(item["duration_working_days"] is None for item in history["previous_activities"])
    new_logic = client.get(
        f"{base}/bootstrap/schedule-drafts/{successor['id']}/logic", headers=headers
    ).json()
    new_ids = {item["id"] for item in detail["activities"]}
    reordered = deepcopy(payload)
    reordered["expected_structure_version_id"] = successor["planning_structure_id"]
    reordered["expected_logic_proposal_id"] = new_logic["id"]
    reordered["draft_inputs"]["duration_inputs"].reverse()
    no_op = client.post(
        f"{base}/bootstrap/schedule-drafts/{successor['id']}/corrections",
        headers={**headers, "Idempotency-Key": "reordered-noop"},
        json=reordered,
    )
    assert no_op.status_code == 422, no_op.text
    old_ids = {item["id"] for item in original["activities"]}
    assert not new_ids & old_ids
    assert len(new_logic["dependencies"]) == 4
    assert len(new_logic["sequence_templates"]) == 1
    for edge in new_logic["dependencies"]:
        assert {edge["predecessor_activity_id"], edge["successor_activity_id"]} <= new_ids
    assert set(new_logic["milestones"][0]["feeds_from_activity_ids"]) <= new_ids
    assert new_logic["constraints"][0]["activity_id"] in new_ids
    assert new_logic["milestones"][0]["authorized"] is False
    assert (
        client.get(
            f"{base}/bootstrap/schedule-drafts/{successor['id']}/calculation", headers=headers
        ).status_code
        == 404
    )
    assert (
        client.get(f"{base}/authorized-context/current/SCHEDULE", headers=headers).status_code
        == 404
    )
    calculation = create(
        f"/bootstrap/schedule-drafts/{successor['id']}/calculations",
        {"project_start": "2026-10-05"},
        "calculate-corrected",
    )
    assert calculation["readiness"] == "PLANNER_REVIEW_REQUIRED"
    assert calculation["proposed_finish"] == "2026-10-13"
    reviewed = create(
        f"/bootstrap/schedule-calculations/{calculation['id']}/reviews",
        {"reason": "Planner separately reviewed corrected logic and CPM."},
        "review-corrected",
    )
    grant = create(
        "/authority-grants",
        {"actor_id": headers["X-VAI-Actor-ID"], "authority_type": "CURRENT_SCHEDULE_APPROVAL"},
        "authority",
    )
    approved = create(
        f"/bootstrap/schedule-releases/{reviewed['id']}/approve",
        {
            "authority_grant_id": grant["id"],
            "approval_reference": "CORRECTION-PM-1",
            "reason": "Explicit human approval after recalculation and review.",
        },
        "approve-corrected",
    )
    pending_review = create(
        f"/bootstrap/schedule-calculations/{calculation['id']}/reviews",
        {"reason": "A pending review must become stale when planning inputs change."},
        "pending-review",
    )
    second = deepcopy(payload)
    second["expected_structure_version_id"] = successor["planning_structure_id"]
    second["expected_logic_proposal_id"] = new_logic["id"]
    for duration in second["draft_inputs"]["duration_inputs"]:
        if duration["activity_type"] == "EXECUTION":
            duration["duration_working_days"] = "2"
    second_path = f"/bootstrap/schedule-drafts/{successor['id']}/corrections"
    corrected_again = create(second_path, second, "correct-2")
    stale_review = client.post(
        f"{base}/bootstrap/schedule-calculations/{calculation['id']}/reviews",
        headers={**headers, "Idempotency-Key": "stale-calculation-review"},
        json={"reason": "Do not review the earlier corrected planning version."},
    )
    assert stale_review.status_code == 409
    stale_approval = client.post(
        f"{base}/bootstrap/schedule-releases/{pending_review['id']}/approve",
        headers={**headers, "Idempotency-Key": "stale-planning-approval"},
        json={
            "authority_grant_id": grant["id"],
            "approval_reference": "STALE-INPUTS",
            "reason": "A valid grant cannot approve superseded planning inputs.",
        },
    )
    assert stale_approval.status_code == 409
    current = client.get(f"{base}/authorized-context/current/SCHEDULE", headers=headers).json()
    assert current["id"] == approved["authorized_context_id"]
    assert (
        client.get(
            f"{base}/bootstrap/schedule-drafts/{corrected_again['id']}/calculation", headers=headers
        ).status_code
        == 404
    )
    for stale_path, stale_payload in ((path, payload), (second_path, second)):
        response = client.post(
            f"{base}{stale_path}",
            headers={**headers, "Idempotency-Key": "stale-" + str(uuid.uuid4())},
            json=stale_payload,
        )
        assert response.status_code == 409
    with sessions() as session:
        structures = list(
            session.scalars(
                select(BoqPlanningStructureVersion).where(
                    BoqPlanningStructureVersion.project_id == uuid.UUID(successor["project_id"])
                )
            )
        )
        assert len(structures) == 4
    if concurrent:
        active_logic = client.get(
            f"{base}/bootstrap/schedule-drafts/{corrected_again['id']}/logic", headers=headers
        ).json()
        third = deepcopy(second)
        third["expected_structure_version_id"] = corrected_again["planning_structure_id"]
        third["expected_logic_proposal_id"] = active_logic["id"]
        for duration in third["draft_inputs"]["duration_inputs"]:
            if duration["activity_type"] == "EXECUTION":
                duration["duration_working_days"] = "3"
        barrier = threading.Barrier(2)

        def submit(index):
            barrier.wait(timeout=10)
            return client.post(
                f"{base}/bootstrap/schedule-drafts/{corrected_again['id']}/corrections",
                headers={**headers, "Idempotency-Key": f"concurrent-{index}"},
                json=third,
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(submit, (0, 1)))
        assert sorted(response.status_code for response in results) == [201, 409], [
            response.text for response in results
        ]
        winner = next(response.json() for response in results if response.status_code == 201)
        assert (
            client.get(f"{base}/authorized-context/current/SCHEDULE", headers=headers).json()["id"]
            == approved["authorized_context_id"]
        )
        return winner["planning_structure_id"]
    return corrected_again["planning_structure_id"]


def test_material_correction_preserves_history_remaps_logic_and_never_self_authorizes(evidence_api):
    exercise_material_correction(evidence_api)


def test_material_correction_denials_are_atomic(evidence_api):
    client, sessions = evidence_api
    base, headers, draft, _, logic, payload, create = setup_correction(evidence_api)
    path = f"{base}/bootstrap/schedule-drafts/{draft['id']}/corrections"

    def counts():
        with sessions() as session:
            return {
                model.__tablename__: session.scalar(select(func.count()).select_from(model))
                for model in (
                    AuditEvent,
                    BoqPlanningStructureVersion,
                    ScheduleDraftGeneration,
                    ScheduleLogicProposal,
                    ProposedScheduleActivity,
                    PlanningAssumption,
                )
            }

    before = counts()
    invalid = [
        ({**payload, "reason": "            "}, 422),
        ({**payload, "authorized_context_id": str(uuid.uuid4())}, 422),
        ({**payload, "expected_structure_version_id": str(uuid.uuid4())}, 409),
        ({**payload, "expected_logic_proposal_id": None}, 409),
        ({**payload, "draft_inputs": {"validation_owner": "planner@example.test"}}, 422),
    ]
    foreign_logic = {
        "validation_owner": "planner@example.test",
        "dependencies": [
            {**logic["dependencies"][-1], "predecessor_activity_id": str(uuid.uuid4())}
        ],
    }
    invalid.append(({**payload, "logic_inputs": foreign_logic}, 422))
    for number, (data, code) in enumerate(invalid):
        response = client.post(
            path, headers={**headers, "Idempotency-Key": f"invalid-{number}"}, json=data
        )
        assert response.status_code == code, response.text
    with sessions() as session:
        project = session.get(Project, uuid.UUID(draft["project_id"]))
        for actor, role in (
            ("reader", "AUDITOR_READ_ONLY"),
            ("service", "SYSTEM_SERVICE"),
            ("service", "PROJECT_ADMIN"),
        ):
            session.add(
                Membership(
                    organization_id=project.organization_id,
                    project_id=project.id,
                    actor_id=actor,
                    role=role,
                )
            )
        session.commit()
    for actor in ("reader", "service", "outsider"):
        response = client.post(
            path,
            headers={**headers, "X-VAI-Actor-ID": actor, "Idempotency-Key": "deny-" + actor},
            json=payload,
        )
        assert response.status_code == 403
    response = client.post(
        path,
        headers={
            **headers,
            "X-VAI-Organization-ID": str(uuid.uuid4()),
            "Idempotency-Key": "foreign",
        },
        json=payload,
    )
    assert response.status_code == 403
    with sessions() as session:
        assert len(list(session.scalars(select(BoqPlanningStructureVersion)))) == 2
    assert counts() == before
    create(f"/bootstrap/schedule-drafts/{draft['id']}/corrections", payload, "valid-after-denials")


@pytest.mark.parametrize("assumed_calendar", [False, True])
def test_logic_correction_and_assumed_calendar_provenance(evidence_api, assumed_calendar):
    client, sessions = evidence_api
    base, headers, draft, _, logic, payload, create = setup_correction(
        evidence_api, assumed_calendar
    )
    if not assumed_calendar:
        with sessions() as session:
            stored = session.get(ScheduleLogicProposal, uuid.UUID(logic["id"]))
            payload["logic_inputs"] = logic_inputs(stored, headers["X-VAI-Actor-ID"]).model_dump(
                mode="json"
            )
        payload["draft_inputs"]["duration_inputs"] = []
        payload["logic_inputs"]["calendar"]["holidays"] = ["2026-10-07"]
        payload["logic_inputs"]["sequence_templates"][0]["lag_working_days"] = "2"
        payload["logic_inputs"]["milestones"][0]["target_date"] = "2026-11-02"
        payload["logic_inputs"]["constraints"][0]["constraint_date"] = "2026-10-06"
    successor = create(
        f"/bootstrap/schedule-drafts/{draft['id']}/corrections", payload, "logic-correct"
    )
    detail = client.get(
        f"{base}/bootstrap/schedule-drafts/{successor['id']}", headers=headers
    ).json()
    successor_logic = client.get(
        f"{base}/bootstrap/schedule-drafts/{successor['id']}/logic", headers=headers
    ).json()
    if assumed_calendar:
        assert successor_logic["calendar"]["review_state"] == "REVIEW_REQUIRED"
        assert successor_logic["assumptions"][0]["source_basis"] == "VISIBLE_DEFAULT_ASSUMPTION"
        assert successor_logic["assumptions"][0]["status"] == "OPEN"
    else:
        changes = detail["correction_history"]["changes"]
        lag = next(item for item in changes if item["field_path"].endswith("lag_working_days"))
        assert lag["original_value"] == "0"
        assert lag["revised_value"] == "2"
        assert successor_logic["calendar"]["holidays"] == ["2026-10-07"]
        assert len(successor_logic["dependencies"]) == 4
        assert successor_logic["milestones"][0]["target_date"] == "2026-11-02"
        assert successor_logic["milestones"][0]["authorized"] is False
        assert successor_logic["constraints"][0]["constraint_date"] == "2026-10-06"
        assert successor_logic["constraints"][0]["authorized"] is False
    calculation = create(
        f"/bootstrap/schedule-drafts/{successor['id']}/calculations",
        {"project_start": "2026-10-05"},
        "calculate",
    )
    assert calculation["readiness"] == "VALIDATION_BLOCKED"
    codes = {finding["code"] for finding in calculation["validation_findings"]}
    assert ("CALENDAR_REVIEW_REQUIRED" if assumed_calendar else "MISSING_DURATION") in codes
