from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from app.auth import ActorContext
from app.generated.taxonomies import (
    AuthorizedContextType,
    ControlledObjectType,
    DeviationDirection,
    ProgressMeasurementKind,
    SemanticState,
    TruthType,
)
from app.models import (
    AuthorizedContextVersion,
    ControlledObject,
    CostAssessment,
    ForecastProjection,
    ProgressMeasurement,
    Project,
    ProjectControlSnapshot,
)
from app.progress_schemas import ProjectControlSnapshotCreate
from app.services.audit import record_audit
from app.services.control_support import freeze_support
from app.services.progress import resolve_policy
from app.services.project_health import compute_health
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

FORMULA_VERSION = "PROJECT-WEIGHTED-PROGRESS-1.1.0"
ACTUAL_KINDS = {
    ProgressMeasurementKind.VERIFIED,
    ProgressMeasurementKind.ACCEPTED_RELEASED,
}
STRONG_TRUTH_TYPES = {TruthType.VERIFIED_FACT, TruthType.CORROBORATED_FACT}


def utc_value(value: datetime) -> datetime:
    return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)


def request_digest(data: ProjectControlSnapshotCreate) -> str:
    payload = data.model_dump(mode="json")
    if not data.schedule_assessment_ids:
        payload.pop("schedule_assessment_ids")
    if data.health_policy is None:
        payload.pop("health_policy")
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def require_current_context(
    session: Session,
    project: Project,
    context_id: uuid.UUID,
    context_type: AuthorizedContextType,
    data_date: datetime,
) -> AuthorizedContextVersion:
    context = session.get(AuthorizedContextVersion, context_id)
    if context is None or context.project_id != project.id:
        raise HTTPException(status_code=404, detail=f"{context_type} context not found")
    if context.context_type != context_type:
        raise HTTPException(status_code=422, detail=f"Context is not {context_type}")
    if context.semantic_state != SemanticState.CURRENT_AUTHORIZED:
        raise HTTPException(
            status_code=422, detail=f"{context_type} context is not current authorized"
        )
    if context.activated_at is None or utc_value(context.activated_at) > utc_value(data_date):
        raise HTTPException(
            status_code=422,
            detail=f"{context_type} context was not authorized at the snapshot data date",
        )
    if utc_value(context.effective_from) > utc_value(data_date):
        raise HTTPException(
            status_code=422,
            detail=f"{context_type} context is not effective at the snapshot data date",
        )
    return context


def scoped_measurement(
    session: Session, project: Project, measurement_id: uuid.UUID
) -> ProgressMeasurement:
    measurement = session.get(ProgressMeasurement, measurement_id)
    if measurement is None or measurement.project_id != project.id:
        raise HTTPException(status_code=404, detail="Progress measurement not found")
    return measurement


def create_project_control_snapshot(
    session: Session,
    actor: ActorContext,
    project: Project,
    data: ProjectControlSnapshotCreate,
    idempotency_key: str,
) -> ProjectControlSnapshot:
    session.execute(select(Project).where(Project.id == project.id).with_for_update()).scalar_one()
    if utc_value(data.data_date) > datetime.now(UTC):
        raise HTTPException(status_code=422, detail="Snapshot data date cannot be in the future")
    request_hash = request_digest(data)
    existing = session.scalar(
        select(ProjectControlSnapshot).where(
            ProjectControlSnapshot.project_id == project.id,
            ProjectControlSnapshot.idempotency_key == idempotency_key,
        )
    )
    if existing:
        if existing.request_hash != request_hash:
            raise HTTPException(status_code=409, detail="Idempotency key payload mismatch")
        return existing

    weighting = require_current_context(
        session,
        project,
        data.progress_weighting_context_id,
        AuthorizedContextType.PROGRESS_WEIGHTING,
        data.data_date,
    )
    schedule = require_current_context(
        session,
        project,
        data.schedule_context_id,
        AuthorizedContextType.SCHEDULE,
        data.data_date,
    )
    payload = weighting.payload
    payload_date = datetime.fromisoformat(payload["data_date"]).replace(tzinfo=UTC)
    if payload_date > utc_value(data.data_date):
        raise HTTPException(
            status_code=422, detail="Progress weighting data date is later than snapshot data date"
        )

    package_objects = list(
        session.scalars(
            select(ControlledObject).where(
                ControlledObject.project_id == project.id,
                ControlledObject.object_type == ControlledObjectType.WORK_PACKAGE,
                ControlledObject.active.is_(True),
            )
        )
    )
    objects_by_code = {item.code: item for item in package_objects}
    weighted_codes = {item["controlled_object_code"] for item in payload["entries"]}
    unavailable_codes = sorted(weighted_codes - set(objects_by_code))
    if unavailable_codes:
        raise HTTPException(
            status_code=422,
            detail=(
                "Authorized weighting refers to inactive or missing work packages: "
                + ", ".join(unavailable_codes)
            ),
        )
    weights_by_id = {
        objects_by_code[item["controlled_object_code"]].id: Decimal(str(item["weight"]))
        for item in payload["entries"]
    }
    supplied_ids = {item.controlled_object_id for item in data.packages}
    if supplied_ids != set(weights_by_id):
        missing = sorted(str(value) for value in set(weights_by_id) - supplied_ids)
        unexpected = sorted(str(value) for value in supplied_ids - set(weights_by_id))
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Snapshot packages must exactly match the authorized weighting set",
                "missing_controlled_object_ids": missing,
                "unexpected_controlled_object_ids": unexpected,
            },
        )

    planned_total = Decimal("0")
    actual_total = Decimal("0")
    confidence = Decimal("1")
    results: list[dict[str, Any]] = []
    evidence_ids: list[str] = []
    limitations: list[dict[str, Any]] = []
    snapshot_date = utc_value(data.data_date)
    measurement_basis = payload["measurement_basis"]

    for item in sorted(data.packages, key=lambda value: str(value.controlled_object_id)):
        controlled_object = session.get(ControlledObject, item.controlled_object_id)
        if (
            controlled_object is None
            or controlled_object.project_id != project.id
            or controlled_object.object_type != ControlledObjectType.WORK_PACKAGE
            or not controlled_object.active
        ):
            raise HTTPException(
                status_code=422, detail="Snapshot input is not an active work package"
            )
        planned = scoped_measurement(session, project, item.planned_measurement_id)
        actual = scoped_measurement(session, project, item.actual_measurement_id)
        if (
            planned.controlled_object_id != item.controlled_object_id
            or actual.controlled_object_id != item.controlled_object_id
        ):
            raise HTTPException(
                status_code=422, detail="Measurements do not match their work package"
            )
        if planned.measurement_kind != ProgressMeasurementKind.PLANNED_AUTHORIZED:
            raise HTTPException(
                status_code=422, detail="Planned input is not authorized planned progress"
            )
        if planned.authorized_context_id != schedule.id:
            raise HTTPException(
                status_code=422, detail="Planned input does not use the selected schedule"
            )
        if actual.measurement_kind not in ACTUAL_KINDS:
            raise HTTPException(
                status_code=422, detail="Actual input must be verified or accepted/released"
            )
        if actual.truth_type not in STRONG_TRUTH_TYPES:
            raise HTTPException(
                status_code=422, detail="Actual input does not have verified or corroborated truth"
            )
        if (
            planned.measurement_basis != measurement_basis
            or actual.measurement_basis != measurement_basis
        ):
            raise HTTPException(
                status_code=422,
                detail="Progress measurement basis differs from authorized weighting",
            )
        if planned.measurement_basis != actual.measurement_basis:
            raise HTTPException(
                status_code=422, detail="Progress measurement bases are incomparable"
            )
        if planned.unit != actual.unit or planned.denominator != actual.denominator:
            raise HTTPException(
                status_code=422, detail="Progress units or denominators are incomparable"
            )
        observation_date = utc_value(planned.as_of)
        project_zone = ZoneInfo(project.timezone)
        if (
            observation_date != utc_value(actual.as_of)
            or observation_date > snapshot_date
            or observation_date.astimezone(project_zone).date()
            != snapshot_date.astimezone(project_zone).date()
        ):
            raise HTTPException(
                status_code=422,
                detail=(
                    "Progress pairs require one exact observation time on the snapshot "
                    "reporting day, before its cut-off"
                ),
            )

        weight = weights_by_id[item.controlled_object_id]
        planned_contribution = weight * planned.completion_ratio
        actual_contribution = weight * actual.completion_ratio
        planned_total += planned_contribution
        actual_total += actual_contribution
        confidence = min(confidence, actual.confidence)
        evidence_ids.extend((str(planned.evidence_item_id), str(actual.evidence_item_id)))
        if actual.measurement_kind != ProgressMeasurementKind.ACCEPTED_RELEASED:
            limitations.append(
                {
                    "code": "VERIFIED_NOT_ACCEPTED_RELEASED",
                    "controlled_object_id": str(controlled_object.id),
                }
            )
        results.append(
            {
                "controlled_object_id": str(controlled_object.id),
                "controlled_object_code": controlled_object.code,
                "weight": str(weight),
                "planned_measurement_id": str(planned.id),
                "actual_measurement_id": str(actual.id),
                "observation_as_of": observation_date.isoformat(),
                "planned_ratio": str(planned.completion_ratio),
                "actual_ratio": str(actual.completion_ratio),
                "planned_contribution": str(planned_contribution),
                "actual_contribution": str(actual_contribution),
                "actual_measurement_kind": actual.measurement_kind,
                "actual_truth_type": actual.truth_type,
                "actual_confidence": str(actual.confidence),
            }
        )

    cost_refs: list[dict[str, Any]] = []
    cost_policy_versions: set[str] = set()
    for assessment_id in sorted(data.cost_assessment_ids, key=str):
        assessment = session.get(CostAssessment, assessment_id)
        if assessment is None or assessment.project_id != project.id:
            raise HTTPException(status_code=404, detail="Cost assessment not found")
        if utc_value(assessment.data_date) > snapshot_date:
            raise HTTPException(
                status_code=422, detail="Cost assessment is later than snapshot data date"
            )
        cost_policy_versions.add(assessment.policy_version)
        evidence_ids.extend(assessment.input_evidence_ids)
        cost_refs.append(
            {
                "id": str(assessment.id),
                "case_id": str(assessment.case_id),
                "controlled_object_id": str(assessment.controlled_object_id),
                "budget_context_id": str(assessment.budget_context_id),
                "data_date": utc_value(assessment.data_date).isoformat(),
                "currency": assessment.currency,
                "current_authorized_budget": str(assessment.current_authorized_budget),
                "commitments": str(assessment.commitments),
                "actuals": str(assessment.actuals),
                "accruals": str(assessment.accruals),
                "forecast_to_complete": (
                    str(assessment.forecast_to_complete)
                    if assessment.forecast_to_complete is not None
                    else None
                ),
                "estimate_at_completion": (
                    str(assessment.estimate_at_completion)
                    if assessment.estimate_at_completion is not None
                    else None
                ),
                "assessment_status": assessment.assessment_status,
                "truth_type": assessment.truth_type,
                "confidence": str(assessment.confidence),
                "limitations": assessment.limitations,
                "policy_version": assessment.policy_version,
                "formula_version": assessment.formula_version,
            }
        )
    if not cost_refs:
        limitations.append({"code": "COST_POSITION_UNKNOWN"})

    forecast_refs: list[dict[str, Any]] = []
    forecast_policy_versions: set[str] = set()
    for projection_id in sorted(data.forecast_projection_ids, key=str):
        projection = session.get(ForecastProjection, projection_id)
        if projection is None or projection.project_id != project.id:
            raise HTTPException(status_code=404, detail="Forecast projection not found")
        if utc_value(projection.data_date) > snapshot_date:
            raise HTTPException(
                status_code=422, detail="Forecast projection is later than snapshot data date"
            )
        if utc_value(projection.valid_until) < snapshot_date:
            raise HTTPException(
                status_code=422, detail="Forecast projection is stale at snapshot data date"
            )
        if projection.scenario_type == "HYPOTHETICAL":
            raise HTTPException(
                status_code=422,
                detail="Hypothetical forecast cannot define current project control",
            )
        forecast_policy_versions.add(projection.policy_version)
        evidence_ids.extend(projection.input_evidence_ids)
        forecast_refs.append(
            {
                "id": str(projection.id),
                "case_id": str(projection.case_id),
                "controlled_object_id": str(projection.controlled_object_id),
                "target": projection.target,
                "scenario_type": projection.scenario_type,
                "status": projection.status,
                "data_date": utc_value(projection.data_date).isoformat(),
                "horizon_end": projection.horizon_end.isoformat(),
                "result_unit": projection.result_unit,
                "result_point": projection.result_point,
                "result_lower": projection.result_lower,
                "result_upper": projection.result_upper,
                "truth_type": projection.truth_type,
                "upstream_confidence": str(projection.upstream_confidence),
                "horizon_confidence": str(projection.horizon_confidence),
                "valid_until": utc_value(projection.valid_until).isoformat(),
                "limitations": projection.limitations,
                "policy_version": projection.policy_version,
                "formula_version": projection.formula_version,
            }
        )
    if not forecast_refs:
        limitations.append({"code": "FORECAST_POSITION_UNKNOWN"})

    progress_policy = resolve_policy(session, project, data.progress_policy_version)
    on_plan_tolerance = (
        progress_policy["on_plan_tolerance"]
        if isinstance(progress_policy, dict)
        else progress_policy.on_plan_tolerance
    )
    variance = actual_total - planned_total
    if abs(variance) <= on_plan_tolerance:
        progress_status = DeviationDirection.ON_PLAN
    elif variance > 0:
        progress_status = DeviationDirection.AHEAD
    else:
        progress_status = DeviationDirection.BEHIND
    policy_versions = {
        "project_progress_formula": FORMULA_VERSION,
        "progress_threshold": data.progress_policy_version,
        "progress_weighting_context_version": weighting.version_number,
        "schedule_context_version": schedule.version_number,
        "cost": sorted(cost_policy_versions),
        "forecast": sorted(forecast_policy_versions),
    }

    snapshot_number = (
        session.scalar(
            select(func.max(ProjectControlSnapshot.snapshot_number)).where(
                ProjectControlSnapshot.project_id == project.id
            )
        )
        or 0
    ) + 1
    if data.health_policy:
        if utc_value(data.health_policy.effective_from) > snapshot_date:
            raise HTTPException(422, "Health policy is not effective at the snapshot cut-off")
        if data.health_policy.owner_actor_id != actor.actor_id:
            raise HTTPException(422, "Health policy owner must be the explicit recording actor")
        for previous in session.scalars(
            select(ProjectControlSnapshot).where(ProjectControlSnapshot.project_id == project.id)
        ):
            previous_policy = (previous.health or {}).get("policy")
            if (
                previous_policy
                and previous_policy["version"] == data.health_policy.version
                and previous_policy != data.health_policy.model_dump(mode="json")
            ):
                raise HTTPException(
                    409, "Health policy version already has different immutable parameters"
                )
    supporting_context = freeze_support(
        session,
        project,
        data.data_date,
        schedule.id,
        data.schedule_assessment_ids,
        data.health_policy,
    )
    health_costs = [
        {
            **item,
            "stale": data.health_policy is not None
            and (snapshot_date - datetime.fromisoformat(item["data_date"])).days
            > data.health_policy.maximum_source_age_days,
        }
        for item in cost_refs
    ]
    health = compute_health(
        results, health_costs, supporting_context, data.health_policy, snapshot_date.isoformat()
    )
    if data.health_policy:
        policy_versions["project_rag"] = data.health_policy.version
    for item in supporting_context["schedule_assessments"]:
        evidence_ids.extend(item["input_evidence_ids"])
    snapshot = ProjectControlSnapshot(
        id=uuid.uuid4(),
        organization_id=project.organization_id,
        project_id=project.id,
        snapshot_number=snapshot_number,
        data_date=data.data_date,
        progress_weighting_context_id=weighting.id,
        schedule_context_id=schedule.id,
        weighting_basis=payload["weighting_basis"],
        measurement_basis=measurement_basis,
        package_results=results,
        package_exclusions=[],
        cost_assessment_refs=cost_refs,
        forecast_projection_refs=forecast_refs,
        supporting_context=supporting_context,
        health=health,
        policy_versions=policy_versions,
        planned_ratio=planned_total,
        actual_ratio=actual_total,
        variance_ratio=variance,
        progress_status=progress_status,
        progress_policy_version=data.progress_policy_version,
        input_evidence_ids=sorted(set(evidence_ids)),
        truth_type=TruthType.DERIVED_METRIC,
        confidence=confidence,
        limitations=limitations,
        formula_version=FORMULA_VERSION,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
        created_by=actor.actor_id,
    )
    session.add(snapshot)
    record_audit(
        session,
        actor,
        organization_id=project.organization_id,
        project_id=project.id,
        action="PROJECT_CONTROL_SNAPSHOT_CREATED",
        object_type="PROJECT_CONTROL_SNAPSHOT",
        object_id=str(snapshot.id),
        object_version=snapshot.snapshot_number,
        details={
            "data_date": snapshot_date.isoformat(),
            "progress_weighting_context_id": str(weighting.id),
            "schedule_context_id": str(schedule.id),
            "formula_version": FORMULA_VERSION,
        },
    )
    return snapshot
