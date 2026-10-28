"""Explicit planner control inputs; no interpolation or truth upgrade."""

import uuid
from typing import Any

from app.bootstrap_schemas import ActivityControlInput
from app.generated.taxonomies import ControlledObjectType
from app.models import ControlledObject, Project
from fastapi import HTTPException
from sqlalchemy.orm import Session


def apply_control_inputs(
    session: Session,
    project: Project,
    payload: dict[str, Any],
    inputs: list[ActivityControlInput],
) -> list[dict[str, Any]]:
    activities = {item["code"]: item for item in payload["activities"]}
    history = []
    stored = []
    for item in inputs:
        activity = activities.get(item.activity_code)
        if activity is None:
            raise HTTPException(422, "Control binding activity is outside the calculated draft")
        controlled = session.get(ControlledObject, item.controlled_object_id)
        if (
            controlled is None
            or controlled.project_id != project.id
            or not controlled.active
            or controlled.object_type
            not in {
                ControlledObjectType.WORK_PACKAGE,
                ControlledObjectType.ACTIVITY,
            }
        ):
            raise HTTPException(
                422, "Control bindings require an active project work package or activity"
            )
        original = {
            key: activity[key]
            for key in ("controlled_object_code", "progress_basis", "progress_plan")
        }
        revised = {
            "controlled_object_code": controlled.code,
            "progress_basis": item.measurement_basis.value,
            "progress_plan": [point.model_dump(mode="json") for point in item.progress_plan],
        }
        activity.update(revised)
        stored.append({**item.model_dump(mode="json"), "controlled_object_code": controlled.code})
        history.append(
            {
                "field_path": f"activities.{item.activity_code}.control_input",
                "original_value": original,
                "revised_value": revised,
                "reason": item.source_reference,
            }
        )
    payload["bootstrap_control_inputs"] = stored
    return history


def validate_stored_controls(session: Session, project: Project, payload: dict[str, Any]) -> None:
    activities = {item["code"]: item for item in payload["activities"]}
    for binding in payload.get("bootstrap_control_inputs", []):
        controlled = session.get(ControlledObject, uuid.UUID(binding["controlled_object_id"]))
        if (
            controlled is None
            or controlled.project_id != project.id
            or not controlled.active
            or controlled.code != binding["controlled_object_code"]
            or controlled.object_type
            not in {
                ControlledObjectType.WORK_PACKAGE,
                ControlledObjectType.ACTIVITY,
            }
            or activities[binding["activity_code"]]["controlled_object_code"] != controlled.code
        ):
            raise HTTPException(
                409, "Reviewed control mapping changed; obtain a fresh planner review"
            )
