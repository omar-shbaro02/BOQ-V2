from __future__ import annotations

import csv
import hashlib
import io
import json
import uuid
from bisect import bisect_right
from copy import deepcopy
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from app.auth import ActorContext
from app.bootstrap_schemas import (
    RevisionDeltaCreate,
    ScheduleApprovalCreate,
    ScheduleCalculationCreate,
    ScheduleReviewCreate,
)
from app.generated.taxonomies import (
    AuthorizedContextType,
    BootstrapReadiness,
    PlanningReviewState,
    ScheduleActivityArchetype,
    SemanticState,
)
from app.models import (
    AuthorityGrant,
    AuthorizedContextVersion,
    BootstrapRevisionDelta,
    BootstrapScheduleCalculation,
    BootstrapScheduleRelease,
    BoqLine,
    BoqNormalizationRun,
    BoqPlanningStructureVersion,
    BoqSourceVersion,
    Project,
    ProposedScheduleActivity,
    ScheduleDraftGeneration,
    ScheduleLogicProposal,
)
from app.services.audit import record_audit
from fastapi import HTTPException
from openpyxl import Workbook
from sqlalchemy import func, select
from sqlalchemy.orm import Session

CALCULATION_VERSION = "1.0.0"
DELTA_VERSION = "1.0.0"


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _working_days(calendar: dict[str, Any], start: date, count: int = 5000) -> list[date]:
    weekdays = set(calendar["working_weekdays"])
    holidays = {date.fromisoformat(value) for value in calendar.get("holidays", [])}
    result: list[date] = []
    cursor = start
    while len(result) < count:
        if cursor.weekday() in weekdays and cursor not in holidays:
            result.append(cursor)
        cursor += timedelta(days=1)
    return result


def _working_date(calendar: dict[str, Any], workdays: list[date], index: int) -> date:
    if index >= 0:
        return workdays[index]
    weekdays = set(calendar["working_weekdays"])
    holidays = {date.fromisoformat(value) for value in calendar.get("holidays", [])}
    cursor = workdays[0]
    remaining = -index
    while remaining:
        cursor -= timedelta(days=1)
        if cursor.weekday() in weekdays and cursor not in holidays:
            remaining -= 1
    return cursor


def _finding(
    code: str,
    severity: str,
    message: str,
    activity_ids: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "code": code,
        "severity": severity,
        "message": message,
        "activity_ids": activity_ids or [],
    }


def calculate_schedule(
    session: Session,
    actor: ActorContext,
    project: Project,
    logic: ScheduleLogicProposal,
    data: ScheduleCalculationCreate,
    idempotency_key: str,
) -> BootstrapScheduleCalculation:
    request = {"logic_proposal_id": str(logic.id), **data.model_dump(mode="json")}
    request_hash = _digest(request)
    existing = session.scalar(
        select(BootstrapScheduleCalculation).where(
            BootstrapScheduleCalculation.project_id == project.id,
            BootstrapScheduleCalculation.idempotency_key == idempotency_key,
        )
    )
    if existing:
        if existing.request_hash != request_hash:
            raise HTTPException(status_code=409, detail="Idempotency key payload mismatch")
        return existing
    if session.scalar(
        select(BootstrapScheduleCalculation.id).where(
            BootstrapScheduleCalculation.logic_proposal_id == logic.id
        )
    ):
        raise HTTPException(status_code=409, detail="Schedule logic already calculated")

    activities = list(
        session.scalars(
            select(ProposedScheduleActivity)
            .where(ProposedScheduleActivity.generation_id == logic.generation_id)
            .order_by(ProposedScheduleActivity.activity_code)
        )
    )
    ids = {str(item.id) for item in activities}
    findings: list[dict[str, Any]] = []
    if not activities:
        findings.append(_finding("EMPTY_SCHEDULE", "BLOCKER", "No proposed activities to schedule"))
    seen_activity_keys: set[tuple[str, str]] = set()
    durations: dict[str, int] = {}
    for activity in activities:
        activity_id = str(activity.id)
        activity_key = (activity.work_package_id, activity.activity_type)
        if activity_key in seen_activity_keys:
            findings.append(
                _finding(
                    "DUPLICATE_SCHEDULING",
                    "BLOCKER",
                    f"Multiple {activity.activity_type} activities occupy one work package",
                    [activity_id],
                )
            )
        seen_activity_keys.add(activity_key)
        if activity.duration_working_days is None:
            findings.append(
                _finding(
                    "MISSING_DURATION",
                    "BLOCKER",
                    f"{activity.activity_code} has no defensible duration",
                    [activity_id],
                )
            )
        else:
            proposed_duration = Decimal(activity.duration_working_days)
            if proposed_duration <= 0 or proposed_duration != proposed_duration.to_integral_value():
                findings.append(
                    _finding(
                        "INVALID_DURATION",
                        "BLOCKER",
                        f"{activity.activity_code} requires a positive whole working-day duration",
                        [activity_id],
                    )
                )
            else:
                durations[activity_id] = int(proposed_duration)
        if (
            activity.activity_type == ScheduleActivityArchetype.EXECUTION
            and not activity.boq_line_refs
        ):
            findings.append(
                _finding(
                    "MISSING_SOURCE_TRACEABILITY",
                    "BLOCKER",
                    f"Execution activity {activity.activity_code} has no BOQ trace",
                    [activity_id],
                )
            )

    generation = session.get(ScheduleDraftGeneration, logic.generation_id)
    structure = (
        session.get(BoqPlanningStructureVersion, generation.planning_structure_id)
        if generation
        else None
    )
    if structure:
        expected_lines = {item["boq_line_id"] for item in structure.line_mappings}
        covered_lines = {line_id for activity in activities for line_id in activity.boq_line_refs}
        if expected_lines - covered_lines:
            findings.append(
                _finding(
                    "INCOMPLETE_BOQ_COVERAGE",
                    "BLOCKER",
                    "Mapped schedulable BOQ lines are missing from proposed activities",
                )
            )
        if covered_lines - expected_lines:
            findings.append(
                _finding(
                    "UNMAPPED_OR_SUMMARY_CONTAMINATION",
                    "BLOCKER",
                    "Proposed activity references BOQ lines outside reviewed schedulable mappings",
                )
            )

    if sum(durations.values()) > 5000:
        findings.append(
            _finding(
                "SCHEDULE_HORIZON_EXCEEDED",
                "BLOCKER",
                "Total proposed duration exceeds the supported 5000-working-day horizon",
            )
        )

    dependencies = logic.dependencies
    successors = {activity_id: [] for activity_id in ids}
    predecessors = {activity_id: [] for activity_id in ids}
    duplicate_keys: set[tuple[str, str, str, str]] = set()
    for dependency in dependencies:
        predecessor = dependency["predecessor_activity_id"]
        successor = dependency["successor_activity_id"]
        key = (
            predecessor,
            successor,
            dependency["relation_type"],
            str(dependency["lag_working_days"]),
        )
        if key in duplicate_keys:
            findings.append(
                _finding(
                    "DUPLICATE_DEPENDENCY",
                    "BLOCKER",
                    "Duplicate dependency",
                    [predecessor, successor],
                )
            )
        duplicate_keys.add(key)
        lag = Decimal(str(dependency["lag_working_days"]))
        if lag != lag.to_integral_value():
            findings.append(
                _finding(
                    "INVALID_LAG",
                    "BLOCKER",
                    "CPM requires whole working-day lags",
                    [predecessor, successor],
                )
            )
        successors[predecessor].append(dependency)
        predecessors[successor].append(dependency)

    activity_by_package: dict[str, dict[str, str]] = {}
    for activity in activities:
        activity_by_package.setdefault(activity.work_package_id, {})[activity.activity_type] = str(
            activity.id
        )
    edge_pairs = {
        (item["predecessor_activity_id"], item["successor_activity_id"]) for item in dependencies
    }
    for package_activities in activity_by_package.values():
        for predecessor_type, successor_type in (
            (ScheduleActivityArchetype.SUBMITTAL, ScheduleActivityArchetype.PROCUREMENT),
            (ScheduleActivityArchetype.PROCUREMENT, ScheduleActivityArchetype.DELIVERY),
        ):
            predecessor = package_activities.get(predecessor_type)
            successor = package_activities.get(successor_type)
            if predecessor and successor and (predecessor, successor) not in edge_pairs:
                findings.append(
                    _finding(
                        "MISSING_PREREQUISITE",
                        "BLOCKER",
                        f"{predecessor_type} must precede {successor_type} in the work package",
                        [predecessor, successor],
                    )
                )

    indegree = {activity_id: len(predecessors[activity_id]) for activity_id in ids}
    queue = sorted(activity_id for activity_id, value in indegree.items() if value == 0)
    order: list[str] = []
    while queue:
        current = queue.pop(0)
        order.append(current)
        for dependency in successors[current]:
            target = dependency["successor_activity_id"]
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)
                queue.sort()
    cycle_ids = sorted(ids - set(order))
    if cycle_ids:
        findings.append(
            _finding(
                "DEPENDENCY_CYCLE", "BLOCKER", "Dependency cycle blocks CPM calculation", cycle_ids
            )
        )
    orphan_ids = sorted(
        activity_id
        for activity_id in ids
        if not predecessors[activity_id] and not successors[activity_id] and len(ids) > 1
    )
    if orphan_ids:
        findings.append(
            _finding(
                "ORPHAN_ACTIVITY", "WARNING", "Activities have no dependency connection", orphan_ids
            )
        )
    if logic.calendar.get("review_state") not in {
        PlanningReviewState.ACCEPTED,
        PlanningReviewState.REVISED,
    }:
        findings.append(
            _finding(
                "CALENDAR_REVIEW_REQUIRED", "BLOCKER", "Working calendar requires planner review"
            )
        )

    can_calculate = (
        bool(activities)
        and not cycle_ids
        and len(durations) == len(activities)
        and not any(
            item["code"] in {"INVALID_LAG", "SCHEDULE_HORIZON_EXCEEDED"} for item in findings
        )
    )
    early_start: dict[str, int] = {}
    early_finish: dict[str, int] = {}
    late_start: dict[str, int] = {}
    late_finish: dict[str, int] = {}
    if can_calculate:
        for activity_id in order:
            duration = durations[activity_id]
            start_index = 0
            for dependency in predecessors[activity_id]:
                predecessor = dependency["predecessor_activity_id"]
                lag = int(Decimal(str(dependency["lag_working_days"])))
                relation = dependency["relation_type"]
                candidate = {
                    "FINISH_TO_START": early_finish[predecessor] + 1 + lag,
                    "START_TO_START": early_start[predecessor] + lag,
                    "FINISH_TO_FINISH": early_finish[predecessor] + lag - duration + 1,
                    "START_TO_FINISH": early_start[predecessor] + lag - duration + 1,
                }[relation]
                start_index = max(start_index, candidate)
            for constraint in logic.constraints:
                if constraint["activity_id"] != activity_id:
                    continue
                constraint_date = date.fromisoformat(constraint["constraint_date"])
                calendar_days = _working_days(logic.calendar, data.project_start)
                constraint_index = next(
                    (i for i, day in enumerate(calendar_days) if day >= constraint_date), None
                )
                if constraint_index is None:
                    findings.append(
                        _finding(
                            "CONSTRAINT_OUTSIDE_HORIZON",
                            "BLOCKER",
                            "Constraint date exceeds the supported working-calendar horizon",
                            [activity_id],
                        )
                    )
                    continue
                if constraint["constraint_type"] in {"START_NO_EARLIER_THAN", "MUST_START_ON"}:
                    start_index = max(start_index, constraint_index)
            early_start[activity_id] = start_index
            early_finish[activity_id] = start_index + duration - 1
        if max(early_finish.values(), default=0) >= 5000:
            findings.append(
                _finding(
                    "SCHEDULE_HORIZON_EXCEEDED",
                    "BLOCKER",
                    "Calculated finish exceeds the supported 5000-working-day horizon",
                )
            )
            early_start.clear()
            early_finish.clear()
            order = []
        calendar_days = _working_days(logic.calendar, data.project_start)
        for constraint in logic.constraints:
            activity_id = constraint["activity_id"]
            if activity_id not in early_start:
                continue
            target = date.fromisoformat(constraint["constraint_date"])
            actual_start = calendar_days[early_start[activity_id]]
            actual_finish = calendar_days[early_finish[activity_id]]
            kind = constraint["constraint_type"]
            violated = (
                (kind == "MUST_START_ON" and actual_start != target)
                or (kind == "MUST_FINISH_ON" and actual_finish != target)
                or (kind == "FINISH_NO_LATER_THAN" and actual_finish > target)
            )
            if violated:
                findings.append(
                    _finding(
                        "CONSTRAINT_CONFLICT",
                        "BLOCKER",
                        f"{kind} on {target.isoformat()} conflicts with calculated dates",
                        [activity_id],
                    )
                )
        project_finish_index = max(early_finish.values(), default=0)
        milestone_finish_caps: dict[str, int] = {}
        for milestone in logic.milestones:
            if not milestone.get("material", True):
                continue
            target = date.fromisoformat(milestone["target_date"])
            deadline_index = bisect_right(calendar_days, target) - 1
            for feeder_id in milestone["feeds_from_activity_ids"]:
                milestone_finish_caps[feeder_id] = min(
                    milestone_finish_caps.get(feeder_id, project_finish_index),
                    deadline_index,
                )
        for activity_id in reversed(order):
            duration = durations[activity_id]
            finish_index = milestone_finish_caps.get(activity_id, project_finish_index)
            for dependency in successors[activity_id]:
                successor = dependency["successor_activity_id"]
                lag = int(Decimal(str(dependency["lag_working_days"])))
                relation = dependency["relation_type"]
                candidate = {
                    "FINISH_TO_START": late_start[successor] - 1 - lag,
                    "START_TO_START": late_start[successor] - lag + duration - 1,
                    "FINISH_TO_FINISH": late_finish[successor] - lag,
                    "START_TO_FINISH": late_finish[successor] - lag + duration - 1,
                }[relation]
                finish_index = min(finish_index, candidate)
            late_finish[activity_id] = finish_index
            late_start[activity_id] = finish_index - duration + 1

    workdays = _working_days(logic.calendar, data.project_start)
    activity_results: list[dict[str, Any]] = []
    critical_ids: list[str] = []
    for activity in activities:
        activity_id = str(activity.id)
        if activity_id not in early_start:
            activity_results.append(
                {
                    "activity_id": activity_id,
                    "activity_code": activity.activity_code,
                    "early_start": None,
                    "early_finish": None,
                    "late_start": None,
                    "late_finish": None,
                    "total_float_working_days": None,
                    "free_float_working_days": None,
                    "critical": False,
                    "near_critical": False,
                }
            )
            continue
        total_float = late_start[activity_id] - early_start[activity_id]
        if total_float < 0:
            findings.append(
                _finding(
                    "NEGATIVE_FLOAT",
                    "BLOCKER",
                    f"{activity.activity_code} has {total_float} working days of negative float",
                    [activity_id],
                )
            )
        free_float_candidates = []
        for dependency in successors[activity_id]:
            successor = dependency["successor_activity_id"]
            lag = int(Decimal(str(dependency["lag_working_days"])))
            relation = dependency["relation_type"]
            available = {
                "FINISH_TO_START": early_start[successor] - early_finish[activity_id] - 1 - lag,
                "START_TO_START": early_start[successor] - early_start[activity_id] - lag,
                "FINISH_TO_FINISH": early_finish[successor] - early_finish[activity_id] - lag,
                "START_TO_FINISH": early_finish[successor] - early_start[activity_id] - lag,
            }[relation]
            free_float_candidates.append(available)
        free_float = min(
            free_float_candidates, default=project_finish_index - early_finish[activity_id]
        )
        critical = total_float <= 0
        if critical:
            critical_ids.append(activity_id)
        activity_results.append(
            {
                "activity_id": activity_id,
                "activity_code": activity.activity_code,
                "early_start": workdays[early_start[activity_id]].isoformat(),
                "early_finish": workdays[early_finish[activity_id]].isoformat(),
                "late_start": _working_date(
                    logic.calendar, workdays, late_start[activity_id]
                ).isoformat(),
                "late_finish": _working_date(
                    logic.calendar, workdays, late_finish[activity_id]
                ).isoformat(),
                "total_float_working_days": str(total_float),
                "free_float_working_days": str(max(0, free_float)),
                "critical": critical,
                "near_critical": 0 < total_float <= 5,
            }
        )

    result_by_id = {item["activity_id"]: item for item in activity_results}
    milestone_results = []
    for milestone in logic.milestones:
        if milestone.get("material", True) and not milestone["feeds_from_activity_ids"]:
            findings.append(
                _finding(
                    "MILESTONE_FEEDER_MISSING",
                    "BLOCKER",
                    f"Material milestone {milestone['code']} has no activity feeder",
                )
            )
        feeder_finishes = [
            result_by_id[item]["early_finish"]
            for item in milestone["feeds_from_activity_ids"]
            if item in result_by_id and result_by_id[item]["early_finish"]
        ]
        calculated = max(feeder_finishes, default=None)
        variance = None
        if calculated:
            variance = (
                date.fromisoformat(calculated) - date.fromisoformat(milestone["target_date"])
            ).days
            if variance > 0:
                findings.append(
                    _finding(
                        "REQUIRED_COMPLETION_CONFLICT",
                        "BLOCKER" if milestone.get("material", True) else "WARNING",
                        f"{milestone['code']} is calculated {variance} calendar days late",
                        milestone["feeds_from_activity_ids"],
                    )
                )
        milestone_results.append(
            {**milestone, "calculated_date": calculated, "variance_calendar_days": variance}
        )

    if critical_ids:
        weak = [
            str(item.id)
            for item in activities
            if str(item.id) in critical_ids and item.confidence in {"LOW", "INSUFFICIENT"}
        ]
        if weak:
            findings.append(
                _finding(
                    "WEAK_CRITICAL_ASSUMPTION",
                    "BLOCKER",
                    "Critical activities depend on weak planning inputs and require correction",
                    weak,
                )
            )
    blockers = [item for item in findings if item["severity"] == "BLOCKER"]
    readiness = (
        BootstrapReadiness.VALIDATION_BLOCKED
        if blockers
        else BootstrapReadiness.PLANNER_REVIEW_REQUIRED
    )
    proposed_finish = max(
        (
            date.fromisoformat(item["early_finish"])
            for item in activity_results
            if item["early_finish"]
        ),
        default=None,
    )
    input_hash = _digest(
        {
            "activities": [
                {
                    "id": str(item.id),
                    "code": item.activity_code,
                    "type": item.activity_type,
                    "work_package_id": item.work_package_id,
                    "duration": str(item.duration_working_days),
                    "boq": item.boq_line_refs,
                    "confidence": item.confidence,
                    "review_state": item.review_state,
                }
                for item in activities
            ],
            "logic": {
                "dependencies": logic.dependencies,
                "milestones": logic.milestones,
                "constraints": logic.constraints,
                "calendar": logic.calendar,
            },
            "project_start": data.project_start,
            "calculation_version": CALCULATION_VERSION,
        }
    )
    calculation = BootstrapScheduleCalculation(
        id=uuid.uuid4(),
        organization_id=project.organization_id,
        project_id=project.id,
        generation_id=logic.generation_id,
        logic_proposal_id=logic.id,
        calculation_version=CALCULATION_VERSION,
        project_start=data.project_start,
        proposed_finish=proposed_finish,
        readiness=readiness,
        input_hash=input_hash,
        activity_results=activity_results,
        milestone_results=milestone_results,
        validation_findings=findings,
        critical_activity_ids=critical_ids,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
        created_by=actor.actor_id,
    )
    session.add(calculation)
    record_audit(
        session,
        actor,
        organization_id=project.organization_id,
        project_id=project.id,
        action="BOOTSTRAP_SCHEDULE_CALCULATED",
        object_type="BOOTSTRAP_SCHEDULE_CALCULATION",
        object_id=str(calculation.id),
        details={"readiness": readiness, "input_hash": input_hash, "blocker_count": len(blockers)},
    )
    return calculation


def _schedule_payload(
    session: Session, calculation: BootstrapScheduleCalculation
) -> dict[str, Any]:
    logic = session.get(ScheduleLogicProposal, calculation.logic_proposal_id)
    activities = list(
        session.scalars(
            select(ProposedScheduleActivity)
            .where(ProposedScheduleActivity.generation_id == calculation.generation_id)
            .order_by(ProposedScheduleActivity.activity_code)
        )
    )
    result_by_id = {item["activity_id"]: item for item in calculation.activity_results}
    code_by_id = {str(item.id): item.activity_code for item in activities}
    payload = {
        "data_date": calculation.project_start.isoformat(),
        "network_complete": True,
        "activities": [
            {
                "code": item.activity_code,
                "name": item.activity_name,
                "planned_start": result_by_id[str(item.id)]["early_start"],
                "planned_finish": result_by_id[str(item.id)]["early_finish"],
                "progress_basis": "PHYSICAL_EXECUTED",
                "responsible_owner": item.responsible_role or "PROJECT_DELIVERY_MANAGER",
                "controlled_object_code": None,
                "progress_plan": [],
                "calendar_id": logic.calendar["calendar_id"],
                "total_float_days": result_by_id[str(item.id)]["total_float_working_days"],
                "boq_line_refs": item.boq_line_refs,
                "work_package_id": item.work_package_id,
            }
            for item in activities
        ],
        "calendars": [
            {
                "calendar_id": logic.calendar["calendar_id"],
                "name": logic.calendar["name"],
                "working_weekdays": logic.calendar["working_weekdays"],
                "holidays": logic.calendar.get("holidays", []),
            }
        ],
        "dependencies": [
            {
                "predecessor_code": code_by_id[item["predecessor_activity_id"]],
                "successor_code": code_by_id[item["successor_activity_id"]],
                "relation_type": item["relation_type"],
                "lag_days": item["lag_working_days"],
                "basis": item["basis"],
            }
            for item in logic.dependencies
        ],
        "constraints": [
            {
                "activity_code": code_by_id[item["activity_id"]],
                "constraint_type": item["constraint_type"],
                "constraint_date": item["constraint_date"],
                "status": "PROPOSED",
            }
            for item in logic.constraints
        ],
        "milestones": [
            {
                "code": item["code"],
                "name": item["name"],
                "planned_date": item["calculated_date"] or item["target_date"],
                "activity_code": code_by_id[item["feeds_from_activity_ids"][0]]
                if item["feeds_from_activity_ids"]
                else None,
                "controlled_object_code": None,
                "material": item["material"],
                "target_date": item["target_date"],
                "variance_calendar_days": item["variance_calendar_days"],
            }
            for item in calculation.milestone_results
        ],
        "bootstrap_lineage": {
            "calculation_id": str(calculation.id),
            "logic_proposal_id": str(logic.id),
            "generation_id": str(calculation.generation_id),
            "input_hash": calculation.input_hash,
        },
        "semantic_notice": "Planner-reviewed proposal; authority is recorded separately.",
    }
    return payload


def review_schedule(
    session: Session,
    actor: ActorContext,
    project: Project,
    calculation: BootstrapScheduleCalculation,
    data: ScheduleReviewCreate,
    idempotency_key: str,
) -> BootstrapScheduleRelease:
    request_hash = _digest({"calculation_id": str(calculation.id), **data.model_dump(mode="json")})
    existing = session.scalar(
        select(BootstrapScheduleRelease).where(
            BootstrapScheduleRelease.project_id == project.id,
            BootstrapScheduleRelease.idempotency_key == idempotency_key,
        )
    )
    if existing:
        if existing.request_hash != request_hash:
            raise HTTPException(status_code=409, detail="Idempotency key payload mismatch")
        return existing
    if calculation.readiness != BootstrapReadiness.PLANNER_REVIEW_REQUIRED:
        raise HTTPException(
            status_code=409, detail="Blocking validation findings prevent planner review"
        )
    payload = _schedule_payload(session, calculation)
    edit_history = []
    activities = {item["code"]: item for item in payload["activities"]}
    for edit in data.edits:
        parts = edit.field_path.split(".")
        if (
            len(parts) != 3
            or parts[0] != "activities"
            or parts[1] not in activities
            or parts[2] not in {"name", "responsible_owner", "progress_basis"}
        ):
            raise HTTPException(
                status_code=422, detail=f"Unsupported reviewed field path: {edit.field_path}"
            )
        current = activities[parts[1]][parts[2]]
        if current != edit.original_value:
            raise HTTPException(
                status_code=409, detail=f"Original value mismatch: {edit.field_path}"
            )
        activities[parts[1]][parts[2]] = edit.revised_value
        edit_history.append(
            {
                **edit.model_dump(mode="json"),
                "actor_id": actor.actor_id,
                "recorded_at": datetime.now(UTC).isoformat(),
            }
        )
    release = BootstrapScheduleRelease(
        id=uuid.uuid4(),
        organization_id=project.organization_id,
        project_id=project.id,
        calculation_id=calculation.id,
        supersedes_release_id=None,
        version_number=1,
        state=BootstrapReadiness.PM_APPROVAL_REQUIRED,
        schedule_payload=payload,
        edit_history=edit_history,
        review_reason=data.reason,
        authority_grant_id=None,
        authorized_context_id=None,
        approval_reference=None,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
        created_by=actor.actor_id,
    )
    session.add(release)
    record_audit(
        session,
        actor,
        organization_id=project.organization_id,
        project_id=project.id,
        action="BOOTSTRAP_SCHEDULE_REVIEWED",
        object_type="BOOTSTRAP_SCHEDULE_RELEASE",
        object_id=str(release.id),
        details={"edit_count": len(edit_history), "state": release.state},
    )
    return release


def approve_schedule(
    session: Session,
    actor: ActorContext,
    project: Project,
    release: BootstrapScheduleRelease,
    data: ScheduleApprovalCreate,
    idempotency_key: str,
) -> BootstrapScheduleRelease:
    request_hash = _digest({"release_id": str(release.id), **data.model_dump(mode="json")})
    existing = session.scalar(
        select(BootstrapScheduleRelease).where(
            BootstrapScheduleRelease.project_id == project.id,
            BootstrapScheduleRelease.idempotency_key == idempotency_key,
        )
    )
    if existing:
        if existing.request_hash != request_hash:
            raise HTTPException(status_code=409, detail="Idempotency key payload mismatch")
        return existing
    if release.state != BootstrapReadiness.PM_APPROVAL_REQUIRED:
        raise HTTPException(status_code=409, detail="Release is not awaiting approval")
    if session.scalar(
        select(BootstrapScheduleRelease.id).where(
            BootstrapScheduleRelease.supersedes_release_id == release.id
        )
    ):
        raise HTTPException(status_code=409, detail="Release has already been approved")
    grant = session.get(AuthorityGrant, data.authority_grant_id)
    today = date.today()
    required_type = (
        "BASELINE_SCHEDULE_APPROVAL" if data.authorize_as_baseline else "CURRENT_SCHEDULE_APPROVAL"
    )
    if (
        grant is None
        or grant.project_id != project.id
        or not grant.active
        or grant.actor_id != actor.actor_id
        or grant.authority_type != required_type
        or (grant.valid_from and today < grant.valid_from)
        or (grant.valid_until and today > grant.valid_until)
    ):
        raise HTTPException(
            status_code=403, detail="Active matching schedule authority grant denied"
        )
    payload = deepcopy(release.schedule_payload)
    typed_payload = {
        key: payload[key]
        for key in (
            "data_date",
            "network_complete",
            "activities",
            "calendars",
            "dependencies",
            "constraints",
            "milestones",
        )
    }
    for activity in typed_payload["activities"]:
        activity.pop("boq_line_refs", None)
        activity.pop("work_package_id", None)
    for dependency in typed_payload["dependencies"]:
        dependency.pop("basis", None)
    for constraint in typed_payload["constraints"]:
        constraint.pop("status", None)
    for milestone in typed_payload["milestones"]:
        milestone.pop("target_date", None)
        milestone.pop("variance_calendar_days", None)
    from app.schemas import SchedulePayload

    SchedulePayload.model_validate(typed_payload)
    now = datetime.now(UTC)
    current = session.scalar(
        select(AuthorizedContextVersion)
        .where(
            AuthorizedContextVersion.project_id == project.id,
            AuthorizedContextVersion.context_type == AuthorizedContextType.SCHEDULE,
            AuthorizedContextVersion.semantic_state == SemanticState.CURRENT_AUTHORIZED,
        )
        .with_for_update()
    )
    if current:
        current.semantic_state = SemanticState.SUPERSEDED
        current.superseded_at = now
    context = AuthorizedContextVersion(
        id=uuid.uuid4(),
        organization_id=project.organization_id,
        project_id=project.id,
        context_type=AuthorizedContextType.SCHEDULE,
        version_number=(
            session.scalar(
                select(func.max(AuthorizedContextVersion.version_number)).where(
                    AuthorizedContextVersion.project_id == project.id,
                    AuthorizedContextVersion.context_type == AuthorizedContextType.SCHEDULE,
                )
            )
            or 0
        )
        + 1,
        semantic_state=SemanticState.CURRENT_AUTHORIZED,
        effective_from=now,
        payload=typed_payload,
        created_by=release.created_by,
        source_version_id=None,
        approval_reference=data.approval_reference,
        activation_reason=data.reason,
        activated_by=actor.actor_id,
        activated_at=now,
    )
    session.add(context)
    approved = BootstrapScheduleRelease(
        id=uuid.uuid4(),
        organization_id=project.organization_id,
        project_id=project.id,
        calculation_id=release.calculation_id,
        supersedes_release_id=release.id,
        version_number=release.version_number + 1,
        state=BootstrapReadiness.BASELINE_AUTHORIZED
        if data.authorize_as_baseline
        else BootstrapReadiness.CURRENT_AUTHORIZED,
        schedule_payload=payload,
        edit_history=release.edit_history,
        review_reason=data.reason,
        authority_grant_id=grant.id,
        authorized_context_id=context.id,
        approval_reference=data.approval_reference,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
        created_by=actor.actor_id,
    )
    session.add(approved)
    record_audit(
        session,
        actor,
        organization_id=project.organization_id,
        project_id=project.id,
        action="BOOTSTRAP_SCHEDULE_AUTHORIZED",
        object_type="BOOTSTRAP_SCHEDULE_RELEASE",
        object_id=str(approved.id),
        details={
            "authority_grant_id": str(grant.id),
            "authorized_context_id": str(context.id),
            "state": approved.state,
        },
    )
    return approved


def export_release(release: BootstrapScheduleRelease, export_format: str) -> tuple[bytes, str, str]:
    notice_text = (
        "Authorization is recorded in the linked context and authority grant"
        if release.authorized_context_id
        else "Planner-reviewed proposal; not an authorized schedule"
    )
    if export_format == "JSON":
        document = deepcopy(release.schedule_payload)
        document["export_metadata"] = {
            "release_id": str(release.id),
            "semantic_state": release.state,
            "authorized_context_id": (
                str(release.authorized_context_id) if release.authorized_context_id else None
            ),
            "notice": notice_text,
        }
        return (
            json.dumps(document, indent=2).encode(),
            "application/json",
            "schedule.json",
        )
    rows = release.schedule_payload["activities"]
    headers = [
        "code",
        "name",
        "planned_start",
        "planned_finish",
        "total_float_days",
        "work_package_id",
        "boq_line_refs",
        "semantic_state",
        "semantic_notice",
    ]
    normalized = [
        {
            **row,
            "boq_line_refs": "|".join(row.get("boq_line_refs", [])),
            "semantic_state": release.state,
            "semantic_notice": notice_text,
        }
        for row in rows
    ]
    if export_format == "CSV":
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(normalized)
        return output.getvalue().encode(), "text/csv", "schedule.csv"
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Activities"
    sheet.append(headers)
    for row in normalized:
        sheet.append([row.get(key) for key in headers])
    notice = workbook.create_sheet("Semantic notice")
    notice.append(["State", release.state])
    notice.append(["Notice", notice_text])
    notice.append(["Release ID", str(release.id)])
    output_bytes = io.BytesIO()
    workbook.save(output_bytes)
    return (
        output_bytes.getvalue(),
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "schedule.xlsx",
    )


def create_revision_delta(
    session: Session,
    actor: ActorContext,
    project: Project,
    new_source: BoqSourceVersion,
    data: RevisionDeltaCreate,
    idempotency_key: str,
) -> BootstrapRevisionDelta:
    if not new_source.prior_source_version_id:
        raise HTTPException(status_code=422, detail="BOQ revision requires a predecessor")
    request_hash = _digest(
        {"new_source_version_id": str(new_source.id), **data.model_dump(mode="json")}
    )
    existing = session.scalar(
        select(BootstrapRevisionDelta).where(
            BootstrapRevisionDelta.project_id == project.id,
            BootstrapRevisionDelta.idempotency_key == idempotency_key,
        )
    )
    if existing:
        if existing.request_hash != request_hash:
            raise HTTPException(status_code=409, detail="Idempotency key payload mismatch")
        return existing
    prior_norm = session.scalar(
        select(BoqNormalizationRun).where(
            BoqNormalizationRun.source_version_id == new_source.prior_source_version_id
        )
    )
    new_norm = session.scalar(
        select(BoqNormalizationRun).where(BoqNormalizationRun.source_version_id == new_source.id)
    )
    if not prior_norm or not new_norm:
        raise HTTPException(status_code=422, detail="Both BOQ versions must be normalized")
    prior_lines = list(
        session.scalars(select(BoqLine).where(BoqLine.normalization_run_id == prior_norm.id))
    )
    new_lines = list(
        session.scalars(select(BoqLine).where(BoqLine.normalization_run_id == new_norm.id))
    )

    def keyed(lines: list[BoqLine]) -> dict[str, BoqLine]:
        result: dict[str, BoqLine] = {}
        occurrences: dict[str, int] = {}
        for line in sorted(lines, key=lambda item: item.stable_line_id):
            if not line.schedule_relevant:
                continue
            base = f"{line.item_number or ''}|{line.description or ''}|{line.unit or ''}"
            occurrences[base] = occurrences.get(base, 0) + 1
            result[f"{base}|occurrence:{occurrences[base]}"] = line
        return result

    before, after = keyed(prior_lines), keyed(new_lines)
    added = [
        {
            "key": key,
            "line_id": str(after[key].id),
            "quantity": str(after[key].quantity) if after[key].quantity is not None else None,
        }
        for key in sorted(after.keys() - before.keys())
    ]
    removed = [
        {
            "key": key,
            "line_id": str(before[key].id),
            "quantity": str(before[key].quantity) if before[key].quantity is not None else None,
        }
        for key in sorted(before.keys() - after.keys())
    ]
    changed = []
    for key in sorted(before.keys() & after.keys()):
        fields = {}
        for field in ("quantity", "unit_price", "total_price", "location", "trade", "package"):
            old, new = getattr(before[key], field), getattr(after[key], field)
            if old != new:
                fields[field] = {
                    "prior": str(old) if old is not None else None,
                    "new": str(new) if new is not None else None,
                }
        if fields:
            changed.append(
                {
                    "key": key,
                    "prior_line_id": str(before[key].id),
                    "new_line_id": str(after[key].id),
                    "fields": fields,
                }
            )
    current = session.scalar(
        select(AuthorizedContextVersion).where(
            AuthorizedContextVersion.project_id == project.id,
            AuthorizedContextVersion.context_type == AuthorizedContextType.SCHEDULE,
            AuthorizedContextVersion.semantic_state == SemanticState.CURRENT_AUTHORIZED,
        )
    )
    prior_release = (
        session.get(BootstrapScheduleRelease, data.prior_release_id)
        if data.prior_release_id
        else None
    )
    if prior_release and prior_release.project_id != project.id:
        raise HTTPException(status_code=404, detail="Prior release not found")
    if prior_release:
        if prior_release.state not in {
            BootstrapReadiness.CURRENT_AUTHORIZED,
            BootstrapReadiness.BASELINE_AUTHORIZED,
        }:
            raise HTTPException(status_code=422, detail="Prior schedule release must be authorized")
        prior_calculation = session.get(BootstrapScheduleCalculation, prior_release.calculation_id)
        prior_generation = (
            session.get(ScheduleDraftGeneration, prior_calculation.generation_id)
            if prior_calculation
            else None
        )
        prior_structure_for_release = (
            session.get(BoqPlanningStructureVersion, prior_generation.planning_structure_id)
            if prior_generation
            else None
        )
        if (
            prior_structure_for_release is None
            or prior_structure_for_release.normalization_run_id != prior_norm.id
        ):
            raise HTTPException(
                status_code=422,
                detail="Prior schedule release does not derive from the predecessor BOQ version",
            )

    def latest_structure(run_id: uuid.UUID) -> BoqPlanningStructureVersion | None:
        return session.scalar(
            select(BoqPlanningStructureVersion)
            .where(BoqPlanningStructureVersion.normalization_run_id == run_id)
            .order_by(BoqPlanningStructureVersion.version_number.desc())
            .limit(1)
        )

    def mapped_packages(
        structure: BoqPlanningStructureVersion | None, keyed_lines: dict[str, BoqLine]
    ) -> dict[str, str]:
        if structure is None:
            return {}
        package_names = {item["id"]: item["name"] for item in structure.work_packages}
        line_keys = {str(line.id): key for key, line in keyed_lines.items()}
        return {
            line_keys[item["boq_line_id"]]: package_names[item["work_package_id"]]
            for item in structure.line_mappings
            if item["boq_line_id"] in line_keys and item["work_package_id"] in package_names
        }

    prior_structure = latest_structure(prior_norm.id)
    new_structure = latest_structure(new_norm.id)
    prior_mappings = mapped_packages(prior_structure, before)
    new_mappings = mapped_packages(new_structure, after)
    mapping_changes = [
        {
            "key": key,
            "prior_package": prior_mappings.get(key),
            "new_package": new_mappings.get(key),
        }
        for key in sorted(prior_mappings.keys() | new_mappings.keys())
        if prior_mappings.get(key) != new_mappings.get(key)
    ]

    def generation_for_structure(
        structure: BoqPlanningStructureVersion | None,
    ) -> ScheduleDraftGeneration | None:
        if structure is None:
            return None
        return session.scalar(
            select(ScheduleDraftGeneration).where(
                ScheduleDraftGeneration.planning_structure_id == structure.id
            )
        )

    def draft_activities(structure: BoqPlanningStructureVersion | None) -> list[dict[str, Any]]:
        generation = generation_for_structure(structure)
        if generation is None:
            return []
        return [
            {
                "activity_code": activity.activity_code,
                "activity_type": activity.activity_type,
                "package_name": next(
                    (
                        package["name"]
                        for package in structure.work_packages
                        if package["id"] == activity.work_package_id
                    ),
                    activity.work_package_id,
                ),
                "duration_working_days": (
                    str(activity.duration_working_days)
                    if activity.duration_working_days is not None
                    else None
                ),
            }
            for activity in session.scalars(
                select(ProposedScheduleActivity).where(
                    ProposedScheduleActivity.generation_id == generation.id
                )
            )
        ]

    prior_activities = draft_activities(prior_structure)
    new_activities = draft_activities(new_structure)
    activity_changes = []
    if prior_activities and new_activities:

        def activity_index(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
            return {f"{item['package_name']}|{item['activity_type']}": item for item in items}

        old_activities = activity_index(prior_activities)
        revised_activities = activity_index(new_activities)
        activity_changes = [
            {
                "key": key,
                "prior": old_activities.get(key),
                "new": revised_activities.get(key),
            }
            for key in sorted(old_activities.keys() | revised_activities.keys())
            if old_activities.get(key) != revised_activities.get(key)
        ]
    schedule_effects = {
        "status": "PENDING_REGENERATION",
        "reason": "A revised schedule requires separate deterministic CPM and human authorization",
        "authorized_schedule_unchanged": True,
        "prior_activity_count": len(prior_activities) if prior_activities else None,
        "new_activity_count": len(new_activities) if new_activities else None,
    }
    prior_generation = generation_for_structure(prior_structure)
    new_generation = generation_for_structure(new_structure)
    if prior_generation and new_generation:
        prior_calculation = session.scalar(
            select(BootstrapScheduleCalculation).where(
                BootstrapScheduleCalculation.generation_id == prior_generation.id
            )
        )
        new_calculation = session.scalar(
            select(BootstrapScheduleCalculation).where(
                BootstrapScheduleCalculation.generation_id == new_generation.id
            )
        )
        if prior_calculation and new_calculation:
            schedule_effects.update(
                {
                    "status": "PROPOSED_COMPARISON",
                    "prior_calculation_id": str(prior_calculation.id),
                    "new_calculation_id": str(new_calculation.id),
                    "prior_proposed_finish": (
                        prior_calculation.proposed_finish.isoformat()
                        if prior_calculation.proposed_finish
                        else None
                    ),
                    "new_proposed_finish": (
                        new_calculation.proposed_finish.isoformat()
                        if new_calculation.proposed_finish
                        else None
                    ),
                    "proposed_finish_delta_calendar_days": (
                        (new_calculation.proposed_finish - prior_calculation.proposed_finish).days
                        if prior_calculation.proposed_finish and new_calculation.proposed_finish
                        else None
                    ),
                    "prior_readiness": prior_calculation.readiness,
                    "new_readiness": new_calculation.readiness,
                    "reason": (
                        "Draft CPM comparison only; current authorized schedule remains unchanged"
                    ),
                }
            )
    delta = BootstrapRevisionDelta(
        id=uuid.uuid4(),
        organization_id=project.organization_id,
        project_id=project.id,
        prior_source_version_id=new_source.prior_source_version_id,
        new_source_version_id=new_source.id,
        prior_release_id=prior_release.id if prior_release else None,
        comparison_version=DELTA_VERSION,
        added_scope=added,
        removed_scope=removed,
        changed_scope=changed,
        mapping_changes=mapping_changes,
        activity_changes=activity_changes,
        schedule_effects=schedule_effects,
        current_authorized_context_id=current.id if current else None,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
        created_by=actor.actor_id,
    )
    session.add(delta)
    record_audit(
        session,
        actor,
        organization_id=project.organization_id,
        project_id=project.id,
        action="BOOTSTRAP_REVISION_DELTA_CREATED",
        object_type="BOOTSTRAP_REVISION_DELTA",
        object_id=str(delta.id),
        details={
            "added": len(added),
            "removed": len(removed),
            "changed": len(changed),
            "authorized_schedule_unchanged": True,
        },
    )
    return delta
