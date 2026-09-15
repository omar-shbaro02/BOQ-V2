from __future__ import annotations

import hashlib
import json
import math
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from app.auth import ActorContext
from app.services.recovery import utc
from app.forecast_schemas import ForecastCreate, ForecastPolicyCreate
from app.generated.taxonomies import (
    ActiveResponseStatus,
    CaseLedgerEventType,
    CaseLifecycle,
    CostForecastStatus,
    ForecastMethod,
    ForecastRecalculationTrigger,
    ForecastScenarioType,
    ForecastStatus,
    ForecastTarget,
    ForecastValidity,
    ProgressReconciliationStatus,
    ScheduleAssessmentStatus,
    SemanticState,
    TruthType,
)
from app.models import (
    CaseActiveResponse,
    CaseSnapshot,
    CostAssessment,
    ForecastPolicy,
    ForecastProjection,
    ProgressEvaluation,
    ProgressMeasurement,
    Project,
    ScheduleAssessment,
)
from app.services.audit import record_audit
from app.services.cases import add_ledger, audit_case, require_version, scoped_case
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

DEFAULT_POLICY_VERSION = "FORECAST-DEFAULT-1.0.0"
FORMULA_VERSION = "FORECAST-DETERMINISTIC-1.0.0"
DEFAULT_POLICY = {
    "id": None,
    "organization_id": None,
    "project_id": None,
    "policy_version": DEFAULT_POLICY_VERSION,
    "lower_rate_factor": Decimal("0.80"),
    "upper_rate_factor": Decimal("1.20"),
    "lower_cost_factor": Decimal("0.90"),
    "upper_cost_factor": Decimal("1.10"),
    "confidence_decay_per_30_days": Decimal("0.08"),
    "confidence_floor": Decimal("0.20"),
    "maximum_horizon_days": 730,
    "validity_days": 14,
    "rationale": "Visible MVP default: ±20% rate, ±10% cost, 8% monthly confidence decay",
    "supersedes_policy_id": None,
    "created_by": "SYSTEM",
    "created_at": None,
}


def policy_value(policy: dict[str, Any] | ForecastPolicy, name: str) -> Any:
    return policy[name] if isinstance(policy, dict) else getattr(policy, name)


def decimal_parameter(values: dict[str, Any], name: str, default: str) -> Decimal:
    try:
        value = Decimal(str(values.get(name, default)))
    except (InvalidOperation, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"{name} must be numeric") from exc
    if name in {"productivity_multiplier", "cost_multiplier"} and value <= 0:
        raise HTTPException(status_code=422, detail=f"{name} must be positive")
    return value


def create_policy(
    session: Session, actor: ActorContext, project: Project, data: ForecastPolicyCreate
) -> ForecastPolicy:
    if data.policy_version == DEFAULT_POLICY_VERSION:
        raise HTTPException(status_code=409, detail="Default forecast policy version is reserved")
    if data.supersedes_policy_id:
        previous = session.get(ForecastPolicy, data.supersedes_policy_id)
        if previous is None or previous.project_id != project.id:
            raise HTTPException(status_code=422, detail="Superseded forecast policy not found")
    policy = ForecastPolicy(
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
        action="FORECAST_POLICY_CREATED",
        object_type="FORECAST_POLICY",
        object_id=str(policy.id),
        details={"policy_version": policy.policy_version},
    )
    return policy


def list_policies(session: Session, project: Project) -> list[dict[str, Any] | ForecastPolicy]:
    configured = list(
        session.scalars(
            select(ForecastPolicy)
            .where(ForecastPolicy.project_id == project.id)
            .order_by(ForecastPolicy.created_at)
        )
    )
    return [DEFAULT_POLICY, *configured]


def resolve_policy(
    session: Session, project: Project, version: str
) -> dict[str, Any] | ForecastPolicy:
    if version == DEFAULT_POLICY_VERSION:
        return DEFAULT_POLICY
    policy = session.scalar(
        select(ForecastPolicy).where(
            ForecastPolicy.project_id == project.id, ForecastPolicy.policy_version == version
        )
    )
    if policy is None:
        raise HTTPException(status_code=422, detail="Unsupported forecast policy version")
    return policy


def request_digest(data: ForecastCreate) -> str:
    return hashlib.sha256(
        json.dumps(data.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def horizon_confidence(
    upstream: Decimal, horizon_days: int, policy: dict[str, Any] | ForecastPolicy
) -> Decimal:
    periods = max(1, math.ceil(horizon_days / 30))
    decay = Decimal("1") - Decimal(str(policy_value(policy, "confidence_decay_per_30_days")))
    floor = Decimal(str(policy_value(policy, "confidence_floor")))
    return min(upstream, max(floor, upstream * (decay**periods))).quantize(Decimal("0.000001"))


def date_result(
    data_date: date, remaining: Decimal, rate: Decimal, low_factor: Decimal, high_factor: Decimal
) -> tuple[str, str, str, int]:
    point_days = math.ceil(remaining / rate)
    lower_days = math.ceil(remaining / (rate * high_factor))
    upper_days = math.ceil(remaining / (rate * low_factor))
    return (
        (data_date + timedelta(days=point_days)).isoformat(),
        (data_date + timedelta(days=lower_days)).isoformat(),
        (data_date + timedelta(days=upper_days)).isoformat(),
        point_days,
    )


def create_forecast(
    session: Session,
    actor: ActorContext,
    project: Project,
    case_id: uuid.UUID,
    data: ForecastCreate,
    idempotency_key: str,
) -> tuple[Any, ForecastProjection]:
    digest = request_digest(data)
    existing = session.scalar(
        select(ForecastProjection).where(
            ForecastProjection.case_id == case_id,
            ForecastProjection.idempotency_key == idempotency_key,
        )
    )
    if existing:
        if existing.request_hash != digest:
            raise HTTPException(status_code=409, detail="Idempotency key payload mismatch")
        return scoped_case(session, project, case_id), existing
    case = scoped_case(session, project, case_id, for_update=True)
    require_version(case, data.expected_version)
    if case.lifecycle == CaseLifecycle.CLOSED:
        raise HTTPException(status_code=409, detail="Closed case must be reopened before forecast")
    snapshot = session.get(CaseSnapshot, data.snapshot_id)
    if snapshot is None or snapshot.case_id != case.id:
        raise HTTPException(status_code=404, detail="Case snapshot not found")
    if str(data.controlled_object_id) not in snapshot.controlled_object_ids:
        raise HTTPException(status_code=422, detail="Forecast object is outside the snapshot")
    horizon_days = (data.horizon_end - snapshot.data_date.date()).days
    if horizon_days <= 0:
        raise HTTPException(status_code=422, detail="Forecast horizon must follow the data date")
    policy = resolve_policy(session, project, data.policy_version)
    if horizon_days > policy_value(policy, "maximum_horizon_days"):
        raise HTTPException(status_code=422, detail="Forecast horizon exceeds policy maximum")

    parameters: dict[str, Any] = dict(data.scenario_parameters)
    response = None
    relevant_parameter = {
        ForecastTarget.PRODUCTION_COMPLETION_DATE: "productivity_multiplier",
        ForecastTarget.SCHEDULE_COMPLETION_DATE: "schedule_day_adjustment",
        ForecastTarget.ESTIMATE_AT_COMPLETION: "cost_multiplier",
    }[data.target]
    if data.scenario_type == ForecastScenarioType.ACTIVE_RESPONSE:
        response = session.get(CaseActiveResponse, data.active_response_id)
        if (
            response is None
            or response.case_id != case.id
            or str(response.id) not in snapshot.active_response_ids
            or response.status != ActiveResponseStatus.ACTIVE
        ):
            raise HTTPException(
                status_code=422,
                detail="Active response must be authorized, active, and frozen in snapshot",
            )
        if relevant_parameter not in response.details:
            raise HTTPException(
                status_code=422,
                detail=f"Active response has no {relevant_parameter} forecast parameter",
            )
        parameters = {relevant_parameter: response.details[relevant_parameter]}
    elif data.scenario_type == ForecastScenarioType.HYPOTHETICAL:
        if set(parameters) != {relevant_parameter}:
            raise HTTPException(
                status_code=422,
                detail=f"Hypothetical target requires only {relevant_parameter}",
            )
        if (
            relevant_parameter == "schedule_day_adjustment"
            and Decimal(str(parameters[relevant_parameter])) == 0
        ):
            raise HTTPException(status_code=422, detail="Hypothetical adjustment cannot be zero")

    low_rate = Decimal(str(policy_value(policy, "lower_rate_factor")))
    high_rate = Decimal(str(policy_value(policy, "upper_rate_factor")))
    limitations: list[dict[str, Any]] = []
    input_values: dict[str, Any]
    evidence_ids: list[str]
    projected_days: int
    if data.target == ForecastTarget.PRODUCTION_COMPLETION_DATE:
        evaluation = session.get(ProgressEvaluation, data.progress_evaluation_id)
        if (
            evaluation is None
            or evaluation.case_id != case.id
            or evaluation.snapshot_id != snapshot.id
            or evaluation.controlled_object_id != data.controlled_object_id
        ):
            raise HTTPException(status_code=422, detail="Progress input is outside this snapshot")
        if (
            evaluation.reconciliation_status != ProgressReconciliationStatus.RECONCILED
            or evaluation.actual_productivity is None
            or evaluation.actual_productivity <= 0
            or evaluation.truth_type == TruthType.CONTRADICTED
        ):
            raise HTTPException(
                status_code=422, detail="Progress input cannot support a rate forecast"
            )
        actual = session.get(ProgressMeasurement, evaluation.actual_measurement_id)
        remaining = actual.denominator - actual.numerator
        multiplier = decimal_parameter(parameters, "productivity_multiplier", "1")
        point, lower, upper, projected_days = date_result(
            snapshot.data_date.date(),
            remaining,
            evaluation.actual_productivity * multiplier,
            low_rate,
            high_rate,
        )
        method = ForecastMethod.LINEAR_PRODUCTION_RATE
        unit = "DATE"
        upstream = evaluation.confidence
        evidence_ids = list(evaluation.input_evidence_ids)
        input_values = {
            "remaining_quantity": str(remaining),
            "observed_productivity_per_day": str(evaluation.actual_productivity),
            "measurement_unit": actual.unit,
        }
        limitations.append(
            {
                "code": "LINEAR_RATE_ASSUMPTION",
                "description": "Observed production rate is held constant over calendar days",
            }
        )
        method_assumption = "Current observed production rate remains constant"
    elif data.target == ForecastTarget.SCHEDULE_COMPLETION_DATE:
        assessment = session.get(ScheduleAssessment, data.schedule_assessment_id)
        if (
            assessment is None
            or assessment.case_id != case.id
            or assessment.snapshot_id != snapshot.id
            or assessment.controlled_object_id != data.controlled_object_id
        ):
            raise HTTPException(status_code=422, detail="Schedule input is outside this snapshot")
        if (
            assessment.assessment_status != ScheduleAssessmentStatus.ASSESSED
            or assessment.truth_type == TruthType.CONTRADICTED
        ):
            raise HTTPException(status_code=422, detail="Schedule input cannot support a forecast")
        adjustment = decimal_parameter(parameters, "schedule_day_adjustment", "0")
        delay = max(Decimal("0"), assessment.delay_days + adjustment)
        point_date = assessment.planned_finish + timedelta(days=math.ceil(delay))
        lower_date = assessment.planned_finish + timedelta(days=math.ceil(delay / high_rate))
        upper_date = assessment.planned_finish + timedelta(days=math.ceil(delay / low_rate))
        point, lower, upper = (
            point_date.isoformat(),
            lower_date.isoformat(),
            upper_date.isoformat(),
        )
        projected_days = (point_date - snapshot.data_date.date()).days
        method = ForecastMethod.SCHEDULE_DELAY_PROPAGATION
        unit = "DATE"
        upstream = assessment.confidence
        evidence_ids = list(assessment.input_evidence_ids)
        input_values = {
            "planned_finish": assessment.planned_finish.isoformat(),
            "assessed_delay_days": str(assessment.delay_days),
            "exposure_level": assessment.exposure_level,
        }
        method_assumption = "Assessed schedule delay persists without a new authorized update"
    else:
        assessment = session.get(CostAssessment, data.cost_assessment_id)
        if (
            assessment is None
            or assessment.case_id != case.id
            or assessment.snapshot_id != snapshot.id
            or assessment.controlled_object_id != data.controlled_object_id
        ):
            raise HTTPException(status_code=422, detail="Cost input is outside this snapshot")
        if (
            assessment.forecast_status != CostForecastStatus.CALCULATED
            or assessment.estimate_at_completion is None
            or assessment.truth_type == TruthType.CONTRADICTED
        ):
            raise HTTPException(status_code=422, detail="Cost input cannot support EAC forecast")
        multiplier = decimal_parameter(parameters, "cost_multiplier", "1")
        point_value = assessment.estimate_at_completion * multiplier
        point = str(point_value.quantize(Decimal("0.0001")))
        lower = str(
            (point_value * Decimal(str(policy_value(policy, "lower_cost_factor")))).quantize(
                Decimal("0.0001")
            )
        )
        upper = str(
            (point_value * Decimal(str(policy_value(policy, "upper_cost_factor")))).quantize(
                Decimal("0.0001")
            )
        )
        projected_days = horizon_days
        method = ForecastMethod.COST_PERFORMANCE_INDEX
        unit = assessment.currency
        upstream = assessment.confidence
        evidence_ids = list(assessment.input_evidence_ids)
        input_values = {
            "recognized_cost": str(assessment.recognized_cost),
            "earned_value": str(assessment.earned_value),
            "source_eac": str(assessment.estimate_at_completion),
            "authorized_budget": str(assessment.current_authorized_budget),
        }
        method_assumption = "Current cost performance relationship continues through completion"

    status = ForecastStatus.CALCULATED
    if projected_days > horizon_days:
        status = ForecastStatus.LIMITED
        limitations.append(
            {
                "code": "RESULT_BEYOND_HORIZON",
                "description": "Point result extends beyond the requested forecast horizon",
            }
        )
    if data.scenario_type == ForecastScenarioType.HYPOTHETICAL:
        semantic_state = SemanticState.SCENARIO
    else:
        semantic_state = SemanticState.FORECAST
    confidence = horizon_confidence(upstream, horizon_days, policy)
    triggers = [
        ForecastRecalculationTrigger.INPUT_CHANGED,
        ForecastRecalculationTrigger.NEW_SNAPSHOT,
        ForecastRecalculationTrigger.POLICY_CHANGED,
        ForecastRecalculationTrigger.VALID_UNTIL_REACHED,
        ForecastRecalculationTrigger.MANUAL,
    ]
    if response:
        triggers.append(ForecastRecalculationTrigger.ACTIVE_RESPONSE_CHANGED)
    forecast_number = (
        session.scalar(
            select(func.max(ForecastProjection.forecast_number)).where(
                ForecastProjection.case_id == case.id
            )
        )
        or 0
    ) + 1
    forecast = ForecastProjection(
        id=uuid.uuid4(),
        organization_id=project.organization_id,
        project_id=project.id,
        case_id=case.id,
        snapshot_id=snapshot.id,
        controlled_object_id=data.controlled_object_id,
        progress_evaluation_id=data.progress_evaluation_id,
        schedule_assessment_id=data.schedule_assessment_id,
        cost_assessment_id=data.cost_assessment_id,
        active_response_id=response.id if response else None,
        forecast_number=forecast_number,
        target=data.target,
        scenario_type=data.scenario_type,
        method=method,
        status=status,
        semantic_state=semantic_state,
        truth_type=TruthType.SCENARIO_ESTIMATE,
        data_date=snapshot.data_date,
        horizon_end=data.horizon_end,
        horizon_days=horizon_days,
        result_unit=unit,
        result_point=point,
        result_lower=lower,
        result_upper=upper,
        input_values=input_values,
        input_evidence_ids=evidence_ids,
        assumptions=[method_assumption, *data.assumptions],
        scenario_parameters={key: str(value) for key, value in parameters.items()},
        limitations=limitations,
        upstream_confidence=upstream,
        horizon_confidence=confidence,
        valid_until=datetime.now(UTC) + timedelta(days=int(policy_value(policy, "validity_days"))),
        recalculation_triggers=[str(value) for value in triggers],
        policy_version=data.policy_version,
        formula_version=FORMULA_VERSION,
        idempotency_key=idempotency_key,
        request_hash=digest,
        created_by=actor.actor_id,
    )
    session.add(forecast)
    session.flush()
    case.last_forecast_projection_id = forecast.id
    case.version += 1
    add_ledger(
        session,
        actor,
        case,
        CaseLedgerEventType.FORECAST_CREATED,
        "Versioned forecast projection created",
        details={
            "forecast_id": str(forecast.id),
            "target": str(data.target),
            "scenario_type": str(data.scenario_type),
        },
    )
    audit_case(session, actor, case, "FORECAST_CREATED", {"forecast_id": str(forecast.id)})
    return case, forecast


def validity_for(session: Session, forecast: ForecastProjection) -> ForecastValidity:
    if datetime.now(UTC) > (
        forecast.valid_until
        if forecast.valid_until.tzinfo
        else forecast.valid_until.replace(tzinfo=UTC)
    ):
        return ForecastValidity.EXPIRED
    case = scoped_case(session, session.get(Project, forecast.project_id), forecast.case_id)
    if case.last_snapshot_id != forecast.snapshot_id:
        return ForecastValidity.RECALCULATION_REQUIRED
    input_changed = (
        (
            forecast.progress_evaluation_id is not None
            and case.last_progress_evaluation_id != forecast.progress_evaluation_id
        )
        or (
            forecast.schedule_assessment_id is not None
            and case.last_schedule_assessment_id != forecast.schedule_assessment_id
        )
        or (
            forecast.cost_assessment_id is not None
            and case.last_cost_assessment_id != forecast.cost_assessment_id
        )
    )
    if input_changed:
        return ForecastValidity.RECALCULATION_REQUIRED
    if forecast.active_response_id:
        response = session.get(CaseActiveResponse, forecast.active_response_id)
        now = datetime.now(UTC)
        if (
            response is None
            or response.status != ActiveResponseStatus.ACTIVE
            or now < utc(response.effective_from)
            or (response.effective_until is not None and now > utc(response.effective_until))
        ):
            return ForecastValidity.RECALCULATION_REQUIRED
    return ForecastValidity.CURRENT


def forecast_read(session: Session, forecast: ForecastProjection) -> dict[str, Any]:
    values = {column.name: getattr(forecast, column.name) for column in forecast.__table__.columns}
    values["validity"] = validity_for(session, forecast)
    return values
