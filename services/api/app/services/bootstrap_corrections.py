"""Human material corrections create immutable successors; dates and authority remain separate."""

import hashlib
import uuid
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from app.auth import ActorContext
from app.bootstrap_schemas import (
    ScheduleDraftCorrectionCreate,
    ScheduleDraftGenerateCreate,
    ScheduleLogicCreate,
)
from app.generated.taxonomies import PlanningStructureAction, PlanningStructureStatus, ProjectRole
from app.models import (
    BoqPlanningStructureVersion,
    Project,
    ProposedScheduleActivity,
    ScheduleDraftGeneration,
    ScheduleLogicProposal,
)
from app.services.access import require_project_roles
from app.services.audit import record_audit
from app.services.bootstrap import _structure_digest, create_schedule_logic, generate_schedule_draft
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session


def logic_inputs(proposal: ScheduleLogicProposal, owner: str) -> ScheduleLogicCreate:
    assumed = any(
        item.get("source_basis") == "VISIBLE_DEFAULT_ASSUMPTION" for item in proposal.assumptions
    )
    return ScheduleLogicCreate.model_validate(
        {
            "calendar": None if assumed else proposal.calendar,
            "dependencies": [item for item in proposal.dependencies if not item.get("generated")],
            "sequence_templates": proposal.sequence_templates,
            "milestones": proposal.milestones,
            "constraints": proposal.constraints,
            "validation_owner": owner,
        }
    )


def _changes(before: Any, after: Any, path: str) -> list[dict[str, Any]]:
    if before == after:
        return []
    if isinstance(before, dict) and isinstance(after, dict):
        return [
            item
            for key in sorted(before.keys() | after.keys())
            for item in _changes(before.get(key), after.get(key), f"{path}.{key}")
        ]
    if isinstance(before, list) and isinstance(after, list):
        return [
            item
            for index in range(max(len(before), len(after)))
            for item in _changes(
                before[index] if index < len(before) else None,
                after[index] if index < len(after) else None,
                f"{path}.{index}",
            )
        ]
    return [{"field_path": path, "original_value": before, "revised_value": after}]


def correct_schedule_draft(
    session: Session,
    actor: ActorContext,
    project: Project,
    previous: ScheduleDraftGeneration,
    data: ScheduleDraftCorrectionCreate,
    idempotency_key: str,
) -> ScheduleDraftGeneration:
    roles = require_project_roles(session, actor, project, set(ProjectRole))
    if actor.principal_type != "HUMAN" or ProjectRole.SYSTEM_SERVICE in roles:
        raise HTTPException(403, "Human planner required for material corrections")
    if not roles.intersection(
        {
            ProjectRole.ORGANIZATION_ADMIN,
            ProjectRole.PROJECT_ADMIN,
            ProjectRole.DATA_CONTRIBUTOR,
            ProjectRole.ANALYST_CONTROLLER,
        }
    ):
        raise HTTPException(403, "Planning role required for material corrections")
    if previous.project_id != project.id:
        raise HTTPException(404, "Schedule draft not found")
    session.execute(select(Project.id).where(Project.id == project.id).with_for_update())
    digest = _structure_digest({"generation_id": str(previous.id), **data.model_dump(mode="json")})
    key_hash = hashlib.sha256(idempotency_key.encode()).hexdigest()
    structure_key = f"material-structure-{key_hash}"
    existing = session.scalar(
        select(BoqPlanningStructureVersion).where(
            BoqPlanningStructureVersion.project_id == project.id,
            BoqPlanningStructureVersion.idempotency_key == structure_key,
        )
    )
    if existing:
        if existing.request_hash != digest:
            raise HTTPException(409, "Idempotency key payload mismatch")
        result = session.scalar(
            select(ScheduleDraftGeneration).where(
                ScheduleDraftGeneration.planning_structure_id == existing.id,
                ScheduleDraftGeneration.project_id == project.id,
            )
        )
        if result is None:
            raise HTTPException(409, "Correction lineage is incomplete")
        return result
    structure = session.get(BoqPlanningStructureVersion, previous.planning_structure_id)
    if structure is None or structure.project_id != project.id:
        raise HTTPException(404, "Planning structure not found")
    latest = session.scalar(
        select(BoqPlanningStructureVersion)
        .where(BoqPlanningStructureVersion.normalization_run_id == structure.normalization_run_id)
        .order_by(BoqPlanningStructureVersion.version_number.desc())
        .limit(1)
    )
    if (
        latest is None
        or latest.id != structure.id
        or structure.id != data.expected_structure_version_id
    ):
        raise HTTPException(409, "Planning structure version is stale")
    if structure.status != PlanningStructureStatus.REVIEWED:
        raise HTTPException(409, "Material corrections require a reviewed planning structure")
    prior_logic = session.scalar(
        select(ScheduleLogicProposal).where(
            ScheduleLogicProposal.generation_id == previous.id,
            ScheduleLogicProposal.project_id == project.id,
        )
    )
    if (prior_logic.id if prior_logic else None) != data.expected_logic_proposal_id:
        raise HTTPException(409, "Schedule logic version is stale")
    before = ScheduleDraftGenerateCreate(
        duration_inputs=previous.duration_inputs,
        productivity_inputs=previous.productivity_inputs,
        validation_owner=data.draft_inputs.validation_owner,
    ).model_dump(mode="json")
    after = data.draft_inputs.model_dump(mode="json")
    for snapshot in (before, after):
        snapshot["duration_inputs"].sort(
            key=lambda item: (item["work_package_id"], item["activity_type"])
        )
        snapshot["productivity_inputs"].sort(key=lambda item: item["work_package_id"])
    original_logic = (
        logic_inputs(prior_logic, data.draft_inputs.validation_owner) if prior_logic else None
    )
    revised_logic = data.logic_inputs or original_logic
    changes = _changes(before, after, "draft_inputs") + _changes(
        original_logic.model_dump(mode="json") if original_logic else None,
        revised_logic.model_dump(mode="json") if revised_logic else None,
        "logic_inputs",
    )
    if not changes:
        raise HTTPException(422, "A material correction must change planning inputs")
    old_activities = list(
        session.scalars(
            select(ProposedScheduleActivity)
            .where(ProposedScheduleActivity.generation_id == previous.id)
            .order_by(ProposedScheduleActivity.activity_code)
        )
    )
    generation_id = uuid.uuid4()
    history = {
        "generation_id": str(generation_id),
        "previous_generation_id": str(previous.id),
        "previous_logic_proposal_id": str(prior_logic.id) if prior_logic else None,
        "actor_id": actor.actor_id,
        "recorded_at": datetime.now(UTC).isoformat(),
        "reason": data.reason,
        "changes": changes,
        "previous_activities": [
            {
                "activity_id": str(item.id),
                "activity_code": item.activity_code,
                "work_package_id": item.work_package_id,
                "activity_type": item.activity_type,
                "duration_working_days": (
                    str(item.duration_working_days)
                    if item.duration_working_days is not None
                    else None
                ),
                "duration_basis": item.duration_basis,
            }
            for item in old_activities
        ],
        "semantic_notice": (
            "Corrected planning proposal. Recalculate CPM and obtain fresh review and authority."
        ),
    }
    successor = BoqPlanningStructureVersion(
        id=uuid.uuid4(),
        organization_id=project.organization_id,
        project_id=project.id,
        normalization_run_id=structure.normalization_run_id,
        supersedes_version_id=structure.id,
        version_number=structure.version_number + 1,
        status=PlanningStructureStatus.REVIEWED,
        action=PlanningStructureAction.ACCEPT_PROPOSAL,
        wbs_nodes=deepcopy(structure.wbs_nodes),
        work_packages=deepcopy(structure.work_packages),
        line_mappings=deepcopy(structure.line_mappings),
        unmapped_lines=deepcopy(structure.unmapped_lines),
        assumptions=deepcopy(structure.assumptions),
        warnings=deepcopy(structure.warnings),
        change_summary={"action": "MATERIAL_PLANNING_CORRECTION", "material_correction": history},
        reason=data.reason,
        idempotency_key=structure_key,
        request_hash=digest,
        created_by=actor.actor_id,
    )
    session.add(successor)
    result = generate_schedule_draft(
        session,
        actor,
        project,
        successor,
        data.draft_inputs,
        f"material-draft-{key_hash}",
        generation_id=generation_id,
    )
    new_logic = None
    if revised_logic:
        new_activities = list(
            session.scalars(
                select(ProposedScheduleActivity).where(
                    ProposedScheduleActivity.generation_id == result.id
                )
            )
        )
        new_by_key = {
            (item.work_package_id, item.activity_type): str(item.id) for item in new_activities
        }
        remapping = {
            str(item.id): new_by_key[(item.work_package_id, item.activity_type)]
            for item in old_activities
            if (item.work_package_id, item.activity_type) in new_by_key
        }

        def remap(value: str) -> str:
            if value not in remapping:
                raise HTTPException(
                    422, "Correction logic references an activity outside the draft"
                )
            return remapping[value]

        payload = revised_logic.model_dump(mode="json")
        for dependency in [*payload["dependencies"], *payload["sequence_templates"]]:
            dependency["predecessor_activity_id"] = remap(dependency["predecessor_activity_id"])
            dependency["successor_activity_id"] = remap(dependency["successor_activity_id"])
        for milestone in payload["milestones"]:
            milestone["feeds_from_activity_ids"] = [
                remap(value) for value in milestone["feeds_from_activity_ids"]
            ]
        for constraint in payload["constraints"]:
            constraint["activity_id"] = remap(constraint["activity_id"])
        new_logic = create_schedule_logic(
            session,
            actor,
            project,
            result,
            ScheduleLogicCreate.model_validate(payload),
            f"material-logic-{key_hash}",
        )
    record_audit(
        session,
        actor,
        organization_id=project.organization_id,
        project_id=project.id,
        action="BOOTSTRAP_MATERIAL_CORRECTION_RECORDED",
        object_type="SCHEDULE_DRAFT_GENERATION",
        object_id=str(result.id),
        details={
            "previous_generation_id": str(previous.id),
            "planning_structure_id": str(successor.id),
            "logic_proposal_id": str(new_logic.id) if new_logic else None,
            "change_count": len(changes),
        },
    )
    return result
