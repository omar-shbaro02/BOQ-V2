from __future__ import annotations

import hashlib
import json
import uuid
from collections import deque
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from app.auth import ActorContext
from app.generated.taxonomies import (
    AuthorizedContextType,
    CaseLedgerEventType,
    CaseLifecycle,
    ContradictionStatus,
    FloatSource,
    ScheduleAssessmentStatus,
    ScheduleConclusion,
    ScheduleDependencyType,
    ScheduleExposureLevel,
    ScheduleQualityStatus,
    ScheduleTimingDirection,
    SemanticState,
    TruthType,
)
from app.models import (
    AuthorizedContextVersion,
    CaseSnapshot,
    Contradiction,
    ControlledObject,
    Project,
    ScheduleAnalysisPolicy,
    ScheduleAssessment,
)
from app.schedule_schemas import ScheduleAssessmentCreate, SchedulePolicyCreate
from app.services.audit import record_audit
from app.services.cases import add_ledger, audit_case, require_version, scoped_case
from app.services.evidence import scoped_item
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

DEFAULT_POLICY_VERSION = "SCHEDULE-DEFAULT-1.0.0"
FORMULA_VERSION = "SCHEDULE-NETWORK-1.0.0"
DEFAULT_POLICY = {
    "id": None,
    "organization_id": None,
    "project_id": None,
    "policy_version": DEFAULT_POLICY_VERSION,
    "on_time_tolerance_days": Decimal("0.5"),
    "maximum_schedule_age_days": 14,
    "require_dependency_for_consequence": True,
    "allow_calculated_float": True,
    "rationale": "Visible MVP default: half-day tolerance and 14-day schedule freshness",
    "supersedes_policy_id": None,
    "created_by": "SYSTEM",
    "created_at": None,
}
DELAY_FIELDS = {
    "delay_days",
    "schedule_variance_days",
    "activity_delay_days",
    "finish_variance_days",
}


def utc_value(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def decimal_value(value: Any) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise HTTPException(status_code=422, detail="Schedule delay must be numeric")
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise HTTPException(status_code=422, detail="Schedule delay must be numeric") from exc


def create_policy(
    session: Session,
    actor: ActorContext,
    project: Project,
    data: SchedulePolicyCreate,
) -> ScheduleAnalysisPolicy:
    if data.policy_version == DEFAULT_POLICY_VERSION:
        raise HTTPException(status_code=409, detail="Default schedule policy version is reserved")
    if data.supersedes_policy_id:
        previous = session.get(ScheduleAnalysisPolicy, data.supersedes_policy_id)
        if previous is None or previous.project_id != project.id:
            raise HTTPException(status_code=422, detail="Superseded schedule policy not found")
    policy = ScheduleAnalysisPolicy(
        id=uuid.uuid4(),
        organization_id=project.organization_id,
        project_id=project.id,
        created_by=actor.actor_id,
        **data.model_dump(),
    )
    session.add(policy)
    record_audit(
        session,
        actor,
        organization_id=project.organization_id,
        project_id=project.id,
        action="SCHEDULE_POLICY_CREATED",
        object_type="SCHEDULE_ANALYSIS_POLICY",
        object_id=str(policy.id),
        details={"policy_version": policy.policy_version},
    )
    return policy


def list_policies(
    session: Session, project: Project
) -> list[dict[str, Any] | ScheduleAnalysisPolicy]:
    configured = list(
        session.scalars(
            select(ScheduleAnalysisPolicy)
            .where(ScheduleAnalysisPolicy.project_id == project.id)
            .order_by(ScheduleAnalysisPolicy.created_at)
        )
    )
    return [DEFAULT_POLICY, *configured]


def resolve_policy(
    session: Session, project: Project, version: str
) -> dict[str, Any] | ScheduleAnalysisPolicy:
    if version == DEFAULT_POLICY_VERSION:
        return DEFAULT_POLICY
    policy = session.scalar(
        select(ScheduleAnalysisPolicy).where(
            ScheduleAnalysisPolicy.project_id == project.id,
            ScheduleAnalysisPolicy.policy_version == version,
        )
    )
    if policy is None:
        raise HTTPException(status_code=422, detail="Unsupported schedule policy version")
    return policy


def policy_value(policy: dict[str, Any] | ScheduleAnalysisPolicy, name: str) -> Any:
    return policy[name] if isinstance(policy, dict) else getattr(policy, name)


def calendar_for(project: Project, payload: dict[str, Any], calendar_id: str) -> dict[str, Any]:
    if calendar_id == "PROJECT":
        return project.calendar_config
    for calendar in payload.get("calendars", []):
        if calendar["calendar_id"] == calendar_id:
            return calendar
    raise HTTPException(status_code=422, detail=f"Unknown schedule calendar {calendar_id}")


def working_days_between(start: date, finish: date, calendar: dict[str, Any]) -> Decimal:
    if finish <= start:
        return Decimal("0")
    weekdays = set(calendar.get("working_weekdays", [0, 1, 2, 3, 4]))
    holidays = {date.fromisoformat(value) for value in calendar.get("holidays", [])}
    cursor = start + timedelta(days=1)
    count = 0
    while cursor <= finish:
        if cursor.weekday() in weekdays and cursor not in holidays:
            count += 1
        cursor += timedelta(days=1)
    return Decimal(count)


def anchor_dates(
    relation: ScheduleDependencyType,
    predecessor: dict[str, Any],
    successor: dict[str, Any],
) -> tuple[date, date]:
    predecessor_start = date.fromisoformat(predecessor["planned_start"])
    predecessor_finish = date.fromisoformat(predecessor["planned_finish"])
    successor_start = date.fromisoformat(successor["planned_start"])
    successor_finish = date.fromisoformat(successor["planned_finish"])
    if relation == ScheduleDependencyType.FINISH_TO_START:
        return predecessor_finish, successor_start
    if relation == ScheduleDependencyType.START_TO_START:
        return predecessor_start, successor_start
    if relation == ScheduleDependencyType.FINISH_TO_FINISH:
        return predecessor_finish, successor_finish
    return predecessor_start, successor_finish


def edge_slack(
    project: Project,
    payload: dict[str, Any],
    dependency: dict[str, Any],
    activities: dict[str, dict[str, Any]],
) -> Decimal:
    predecessor = activities[dependency["predecessor_code"]]
    successor = activities[dependency["successor_code"]]
    start, finish = anchor_dates(
        ScheduleDependencyType(dependency["relation_type"]), predecessor, successor
    )
    calendar = calendar_for(project, payload, successor.get("calendar_id", "PROJECT"))
    return max(Decimal("0"), raw_edge_slack(start, finish, calendar, dependency))


def raw_edge_slack(
    start: date,
    finish: date,
    calendar: dict[str, Any],
    dependency: dict[str, Any],
) -> Decimal:
    signed_days = (
        working_days_between(start, finish, calendar)
        if finish >= start
        else -working_days_between(finish, start, calendar)
    )
    return signed_days - Decimal(str(dependency["lag_days"]))


def shortest_paths(
    project: Project,
    payload: dict[str, Any],
    source_code: str,
    activities: dict[str, dict[str, Any]],
) -> dict[str, tuple[Decimal, list[str]]]:
    adjacency: dict[str, list[dict[str, Any]]] = {code: [] for code in activities}
    for dependency in payload.get("dependencies", []):
        adjacency[dependency["predecessor_code"]].append(dependency)
    best: dict[str, tuple[Decimal, list[str]]] = {source_code: (Decimal("0"), [source_code])}
    queue: deque[str] = deque([source_code])
    while queue:
        code = queue.popleft()
        slack, path = best[code]
        for dependency in adjacency[code]:
            successor = dependency["successor_code"]
            candidate = slack + edge_slack(project, payload, dependency, activities)
            if successor not in best or candidate < best[successor][0]:
                best[successor] = (candidate, [*path, successor])
                queue.append(successor)
    return best


def schedule_network(context: AuthorizedContextVersion) -> dict[str, Any]:
    payload = context.payload
    return {
        "context_id": context.id,
        "version_number": context.version_number,
        "effective_from": context.effective_from,
        "data_date": payload["data_date"],
        "activity_count": len(payload.get("activities", [])),
        "dependency_count": len(payload.get("dependencies", [])),
        "milestone_count": len(payload.get("milestones", [])),
        "calendar_count": len(payload.get("calendars", [])) + 1,
        "activities": payload.get("activities", []),
        "dependencies": payload.get("dependencies", []),
        "milestones": payload.get("milestones", []),
        "constraints": payload.get("constraints", []),
    }


def assessment_digest(data: ScheduleAssessmentCreate) -> str:
    return hashlib.sha256(
        json.dumps(data.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def assess_schedule(
    session: Session,
    actor: ActorContext,
    project: Project,
    case_id: uuid.UUID,
    data: ScheduleAssessmentCreate,
    idempotency_key: str,
) -> tuple[Any, ScheduleAssessment]:
    digest = assessment_digest(data)
    existing = session.scalar(
        select(ScheduleAssessment).where(
            ScheduleAssessment.case_id == case_id,
            ScheduleAssessment.idempotency_key == idempotency_key,
        )
    )
    if existing:
        if existing.request_hash != digest:
            raise HTTPException(status_code=409, detail="Idempotency key payload mismatch")
        return scoped_case(session, project, case_id), existing
    case = scoped_case(session, project, case_id, for_update=True)
    require_version(case, data.expected_version)
    if case.lifecycle == CaseLifecycle.CLOSED:
        raise HTTPException(
            status_code=409, detail="Closed case must be reopened before assessment"
        )
    snapshot = session.get(CaseSnapshot, data.snapshot_id)
    if snapshot is None or snapshot.case_id != case.id:
        raise HTTPException(status_code=404, detail="Case snapshot not found")
    if str(data.controlled_object_id) not in snapshot.controlled_object_ids:
        raise HTTPException(status_code=422, detail="Schedule object is outside the case snapshot")
    controlled_object = session.get(ControlledObject, data.controlled_object_id)
    if controlled_object is None or controlled_object.project_id != project.id:
        raise HTTPException(status_code=404, detail="Controlled object not found")
    policy = resolve_policy(session, project, data.policy_version)
    schedule_ref = next(
        (
            value
            for value in snapshot.authorized_context_refs
            if value["context_type"] == AuthorizedContextType.SCHEDULE
        ),
        None,
    )
    if schedule_ref is None:
        raise HTTPException(status_code=422, detail="Snapshot has no effective authorized schedule")
    context = session.get(AuthorizedContextVersion, uuid.UUID(schedule_ref["id"]))
    if context is None or context.project_id != project.id:
        raise HTTPException(status_code=422, detail="Snapshot schedule context is unavailable")
    payload = context.payload
    activities = {value["code"]: value for value in payload["activities"]}
    activity = activities.get(data.activity_code)
    if activity is None:
        raise HTTPException(status_code=422, detail="Activity is absent from authorized schedule")
    evidence = scoped_item(session, project, data.delay_evidence_item_id)
    if str(evidence.id) not in snapshot.evidence_item_ids:
        raise HTTPException(status_code=422, detail="Delay evidence is not frozen in snapshot")
    if evidence.controlled_object_id != controlled_object.id:
        raise HTTPException(status_code=422, detail="Delay evidence belongs to another object")
    if evidence.field_name.lower() not in DELAY_FIELDS:
        raise HTTPException(
            status_code=422, detail="Evidence is not a supported schedule-delay field"
        )
    if (evidence.unit or "").lower() not in {"day", "days", "d"}:
        raise HTTPException(status_code=422, detail="Schedule delay evidence must use days")
    if evidence.semantic_state not in {
        SemanticState.ACTUAL,
        SemanticState.REPORTED,
        SemanticState.VERIFIED,
    }:
        raise HTTPException(status_code=422, detail="Schedule delay must be observed or verified")
    if utc_value(evidence.as_of) > utc_value(snapshot.data_date):
        raise HTTPException(
            status_code=422, detail="Delay evidence is later than snapshot data date"
        )
    delay = decimal_value(evidence.value)
    tolerance = Decimal(str(policy_value(policy, "on_time_tolerance_days")))
    if abs(delay) <= tolerance:
        timing = ScheduleTimingDirection.ON_TIME
    elif delay > 0:
        timing = ScheduleTimingDirection.DELAYED
    else:
        timing = ScheduleTimingDirection.AHEAD

    limitations: list[dict[str, Any]] = []
    mapping_valid = activity.get("controlled_object_code") == controlled_object.code
    if not mapping_valid:
        limitations.append(
            {
                "code": "ACTIVITY_OBJECT_MAPPING_MISSING",
                "description": (
                    "Activity is not explicitly mapped to the selected controlled object"
                ),
            }
        )
    schedule_age = (snapshot.data_date.date() - date.fromisoformat(payload["data_date"])).days
    if schedule_age < 0:
        limitations.append(
            {
                "code": "SCHEDULE_DATA_DATE_AFTER_CASE",
                "description": "Authorized schedule data date is later than the case data date",
            }
        )
    if schedule_age > policy_value(policy, "maximum_schedule_age_days"):
        limitations.append(
            {
                "code": "STALE_AUTHORIZED_SCHEDULE",
                "description": f"Authorized schedule data date is {schedule_age} days old",
            }
        )
    if not payload.get("network_complete", False):
        limitations.append(
            {
                "code": "NETWORK_COMPLETENESS_UNCONFIRMED",
                "description": "Schedule source does not assert that dependency logic is complete",
            }
        )
    logic_violations = []
    for dependency in payload.get("dependencies", []):
        predecessor = activities[dependency["predecessor_code"]]
        successor = activities[dependency["successor_code"]]
        start, finish = anchor_dates(
            ScheduleDependencyType(dependency["relation_type"]), predecessor, successor
        )
        calendar = calendar_for(project, payload, successor.get("calendar_id", "PROJECT"))
        if raw_edge_slack(start, finish, calendar, dependency) < 0:
            logic_violations.append(
                f"{dependency['predecessor_code']}->{dependency['successor_code']}"
            )
    if logic_violations:
        limitations.append(
            {
                "code": "LOGIC_DATE_INCONSISTENCY",
                "description": f"Dependency dates conflict for {logic_violations}",
            }
        )

    contradiction_ids = [uuid.UUID(value) for value in snapshot.contradiction_ids]
    contradiction = session.scalar(
        select(Contradiction.id).where(
            Contradiction.id.in_(contradiction_ids),
            Contradiction.status == ContradictionStatus.OPEN,
            (Contradiction.left_item_id == evidence.id)
            | (Contradiction.right_item_id == evidence.id),
        )
    )
    strong_truth = {TruthType.VERIFIED_FACT, TruthType.CORROBORATED_FACT}
    if evidence.truth_type not in strong_truth:
        limitations.append(
            {
                "code": "WEAK_DELAY_EVIDENCE",
                "description": "Decision-critical delay evidence is not verified or corroborated",
            }
        )
    if contradiction:
        limitations.append(
            {
                "code": "UNRESOLVED_SCHEDULE_CONTRADICTION",
                "description": f"Delay evidence participates in contradiction {contradiction}",
            }
        )

    paths = shortest_paths(project, payload, activity["code"], activities)
    reachable = {code: value for code, value in paths.items() if code != activity["code"]}
    supplied_float = activity.get("total_float_days")
    float_value: Decimal | None
    if supplied_float is not None:
        float_value = Decimal(str(supplied_float))
        float_source = FloatSource.SUPPLIED
    elif policy_value(policy, "allow_calculated_float"):
        if reachable:
            float_value = min(value[0] for value in reachable.values())
        else:
            project_finish = max(
                date.fromisoformat(value["planned_finish"]) for value in activities.values()
            )
            float_value = working_days_between(
                date.fromisoformat(activity["planned_finish"]),
                project_finish,
                calendar_for(project, payload, activity.get("calendar_id", "PROJECT")),
            )
        float_source = FloatSource.CALCULATED
    else:
        float_value = None
        float_source = FloatSource.UNAVAILABLE
        limitations.append(
            {
                "code": "FLOAT_UNAVAILABLE",
                "description": "Float was neither supplied nor permitted to be calculated",
            }
        )

    downstream_paths: list[dict[str, Any]] = []
    affected: list[str] = []
    for code, (path_slack, path) in sorted(reachable.items()):
        absorption = float_value if supplied_float is not None else path_slack
        residual = max(Decimal("0"), delay - (absorption or Decimal("0")))
        downstream_paths.append(
            {
                "target_activity_code": code,
                "activity_path": path,
                "available_slack_days": str(absorption) if absorption is not None else None,
                "residual_delay_days": str(residual),
            }
        )
        if residual > 0:
            affected.append(code)

    milestone_exposures: list[dict[str, Any]] = []
    for milestone in payload.get("milestones", []):
        target = milestone.get("activity_code")
        if target == activity["code"]:
            path_slack, path = Decimal("0"), [activity["code"]]
        elif target in reachable:
            path_slack, path = reachable[target]
        else:
            continue
        absorption = float_value if supplied_float is not None else path_slack
        residual = max(Decimal("0"), delay - (absorption or Decimal("0")))
        if residual > 0:
            milestone_exposures.append(
                {
                    "milestone_code": milestone["code"],
                    "material": milestone.get("material", True),
                    "activity_path": path,
                    "exposure_days": str(residual),
                    "planned_date": milestone["planned_date"],
                }
            )

    terminals = {
        code
        for code in activities
        if not any(
            dependency["predecessor_code"] == code for dependency in payload.get("dependencies", [])
        )
    }
    completion_exposures = [
        Decimal(value["residual_delay_days"])
        for value in downstream_paths
        if value["target_activity_code"] in terminals and Decimal(value["residual_delay_days"]) > 0
    ]
    source_is_project_terminal = activity["code"] in terminals and date.fromisoformat(
        activity["planned_finish"]
    ) == max(date.fromisoformat(value["planned_finish"]) for value in activities.values())
    if source_is_project_terminal:
        source_residual = max(Decimal("0"), delay - (float_value or Decimal("0")))
        if source_residual > 0:
            completion_exposures.append(source_residual)
    completion_exposure = max(completion_exposures) if completion_exposures else None

    critical_codes = {
        "ACTIVITY_OBJECT_MAPPING_MISSING",
        "STALE_AUTHORIZED_SCHEDULE",
        "SCHEDULE_DATA_DATE_AFTER_CASE",
        "NETWORK_COMPLETENESS_UNCONFIRMED",
        "LOGIC_DATE_INCONSISTENCY",
        "WEAK_DELAY_EVIDENCE",
        "UNRESOLVED_SCHEDULE_CONTRADICTION",
    }
    limitation_codes = {value["code"] for value in limitations}
    if "ACTIVITY_OBJECT_MAPPING_MISSING" in limitation_codes:
        status = ScheduleAssessmentStatus.INSUFFICIENT
    elif limitation_codes & critical_codes:
        status = ScheduleAssessmentStatus.VERIFICATION_REQUIRED
    else:
        status = ScheduleAssessmentStatus.ASSESSED
    quality = (
        ScheduleQualityStatus.VALID
        if not limitations
        else ScheduleQualityStatus.VALID_WITH_LIMITATIONS
    )
    if milestone_exposures:
        exposure = ScheduleExposureLevel.MILESTONE
    elif completion_exposure is not None:
        exposure = ScheduleExposureLevel.PROJECT_COMPLETION
    elif affected:
        exposure = ScheduleExposureLevel.DOWNSTREAM
    else:
        exposure = ScheduleExposureLevel.LOCAL
    if status != ScheduleAssessmentStatus.ASSESSED:
        maximum_conclusion = ScheduleConclusion.LOCAL_TIMING_VARIANCE
    elif milestone_exposures:
        maximum_conclusion = ScheduleConclusion.MILESTONE_EXPOSURE
    elif affected:
        maximum_conclusion = ScheduleConclusion.DOWNSTREAM_EXPOSURE
    else:
        maximum_conclusion = ScheduleConclusion.LOCAL_TIMING_VARIANCE
    output_truth = (
        TruthType.CONTRADICTED
        if contradiction or evidence.truth_type == TruthType.CONTRADICTED
        else TruthType.DERIVED_METRIC
    )
    number = (
        session.scalar(
            select(func.coalesce(func.max(ScheduleAssessment.assessment_number), 0)).where(
                ScheduleAssessment.case_id == case.id
            )
        )
        + 1
    )
    assessment = ScheduleAssessment(
        id=uuid.uuid4(),
        organization_id=project.organization_id,
        project_id=project.id,
        case_id=case.id,
        snapshot_id=snapshot.id,
        schedule_context_id=context.id,
        controlled_object_id=controlled_object.id,
        delay_evidence_item_id=evidence.id,
        assessment_number=number,
        activity_code=activity["code"],
        data_date=snapshot.data_date,
        planned_start=date.fromisoformat(activity["planned_start"]),
        planned_finish=date.fromisoformat(activity["planned_finish"]),
        delay_days=delay,
        timing_direction=timing,
        effective_float_days=float_value,
        float_source=float_source,
        schedule_quality=quality,
        assessment_status=status,
        exposure_level=exposure,
        downstream_paths=downstream_paths,
        affected_activity_codes=affected,
        milestone_exposures=milestone_exposures,
        project_completion_exposure_days=completion_exposure,
        maximum_supported_conclusion=maximum_conclusion,
        input_evidence_ids=[str(evidence.id)],
        truth_type=output_truth,
        confidence=evidence.confidence,
        limitations=limitations,
        policy_version=data.policy_version,
        formula_version=FORMULA_VERSION,
        idempotency_key=idempotency_key,
        request_hash=digest,
        assessed_by=actor.actor_id,
    )
    session.add(assessment)
    session.flush()
    case.last_schedule_assessment_id = assessment.id
    case.version += 1
    add_ledger(
        session,
        actor,
        case,
        CaseLedgerEventType.SCHEDULE_ASSESSED,
        f"Schedule timing assessed as {timing} with {exposure} exposure",
        details={
            "schedule_assessment_id": str(assessment.id),
            "maximum_supported_conclusion": maximum_conclusion,
            "assessment_status": status,
        },
    )
    audit_case(
        session,
        actor,
        case,
        "CASE_SCHEDULE_ASSESSED",
        {"schedule_assessment_id": str(assessment.id)},
    )
    return case, assessment
