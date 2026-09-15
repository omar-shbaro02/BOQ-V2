from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from app.auth import ActorContext
from app.confidence import impact_confidence
from app.generated.taxonomies import (
    CaseLedgerEventType,
    CaseLifecycle,
    ConsequenceSeverity,
    ConsequenceType,
    DecisionClockType,
    ForecastValidity,
    ImpactAssessmentStatus,
    PriorityBand,
    TruthType,
    UrgencyLevel,
)
from app.impact_schemas import (
    ConfidenceOverrideCreate,
    ImpactAssessmentCreate,
    ImpactPolicyCreate,
)
from app.models import (
    CaseActiveResponse,
    CaseSnapshot,
    ConfidenceOverride,
    CostAssessment,
    EvidenceItem,
    ForecastProjection,
    ImpactAssessment,
    ImpactPriorityPolicy,
    ProgressEvaluation,
    Project,
    ScheduleAssessment,
)
from app.services.audit import record_audit
from app.services.cases import add_ledger, audit_case, require_version, scoped_case
from app.services.forecast import validity_for
from app.services.recovery import qualify_recovery
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

DEFAULT_POLICY_VERSION = "IMPACT-DEFAULT-1.0.0"
FORMULA_VERSION = "IMPACT-PRIORITY-1.0.3"
DEFAULT_POLICY = {
    "id": None,
    "organization_id": None,
    "project_id": None,
    "policy_version": DEFAULT_POLICY_VERSION,
    "medium_cost_exposure_ratio": Decimal("0.05"),
    "high_cost_exposure_ratio": Decimal("0.10"),
    "critical_cost_exposure_ratio": Decimal("0.20"),
    "elevated_margin_days": 21,
    "urgent_margin_days": 7,
    "active_response_score_reduction": Decimal("10"),
    "cross_cutting_bonus_per_object": Decimal("2"),
    "medium_priority_score": Decimal("25"),
    "high_priority_score": Decimal("50"),
    "critical_priority_score": Decimal("75"),
    "rationale": "Visible MVP defaults for consequence, clock margin, and priority scoring",
    "supersedes_policy_id": None,
    "created_by": "SYSTEM",
    "created_at": None,
}


def policy_value(policy: dict[str, Any] | ImpactPriorityPolicy, name: str) -> Any:
    return policy[name] if isinstance(policy, dict) else getattr(policy, name)


def create_policy(
    session: Session, actor: ActorContext, project: Project, data: ImpactPolicyCreate
) -> ImpactPriorityPolicy:
    if data.policy_version == DEFAULT_POLICY_VERSION:
        raise HTTPException(status_code=409, detail="Default impact policy version is reserved")
    if data.supersedes_policy_id:
        previous = session.get(ImpactPriorityPolicy, data.supersedes_policy_id)
        if previous is None or previous.project_id != project.id:
            raise HTTPException(status_code=422, detail="Superseded impact policy not found")
    policy = ImpactPriorityPolicy(
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
        action="IMPACT_POLICY_CREATED",
        object_type="IMPACT_PRIORITY_POLICY",
        object_id=str(policy.id),
        details={"policy_version": policy.policy_version},
    )
    return policy


def list_policies(
    session: Session, project: Project
) -> list[dict[str, Any] | ImpactPriorityPolicy]:
    configured = list(
        session.scalars(
            select(ImpactPriorityPolicy)
            .where(ImpactPriorityPolicy.project_id == project.id)
            .order_by(ImpactPriorityPolicy.created_at)
        )
    )
    return [DEFAULT_POLICY, *configured]


def resolve_policy(
    session: Session, project: Project, version: str
) -> dict[str, Any] | ImpactPriorityPolicy:
    if version == DEFAULT_POLICY_VERSION:
        return DEFAULT_POLICY
    policy = session.scalar(
        select(ImpactPriorityPolicy).where(
            ImpactPriorityPolicy.project_id == project.id,
            ImpactPriorityPolicy.policy_version == version,
        )
    )
    if policy is None:
        raise HTTPException(status_code=422, detail="Unsupported impact policy version")
    return policy


def create_confidence_override(
    session: Session,
    actor: ActorContext,
    project: Project,
    case_id: uuid.UUID,
    data: ConfidenceOverrideCreate,
) -> tuple[Any, ConfidenceOverride]:
    case = scoped_case(session, project, case_id, for_update=True)
    require_version(case, data.expected_version)
    if case.lifecycle == CaseLifecycle.CLOSED:
        raise HTTPException(status_code=409, detail="Closed case cannot receive an override")
    snapshot = session.get(CaseSnapshot, data.snapshot_id)
    if snapshot is None or snapshot.case_id != case.id:
        raise HTTPException(status_code=404, detail="Case snapshot not found")
    if data.approved_confidence <= data.upstream_ceiling:
        raise HTTPException(
            status_code=422,
            detail="Approved confidence must exceed the recorded upstream ceiling",
        )
    override = ConfidenceOverride(
        id=uuid.uuid4(),
        organization_id=project.organization_id,
        project_id=project.id,
        case_id=case.id,
        snapshot_id=snapshot.id,
        upstream_ceiling=data.upstream_ceiling,
        approved_confidence=data.approved_confidence,
        justification=data.justification,
        approved_by=actor.actor_id,
    )
    session.add(override)
    session.flush()
    case.version += 1
    add_ledger(
        session,
        actor,
        case,
        CaseLedgerEventType.CONFIDENCE_OVERRIDE_APPROVED,
        "Explicit confidence ceiling override approved",
        details={
            "override_id": str(override.id),
            "upstream_ceiling": str(override.upstream_ceiling),
            "approved_confidence": str(override.approved_confidence),
            "justification": override.justification,
        },
    )
    audit_case(
        session, actor, case, "CONFIDENCE_OVERRIDE_APPROVED", {"override_id": str(override.id)}
    )
    return case, override


def request_digest(data: ImpactAssessmentCreate) -> str:
    return hashlib.sha256(
        json.dumps(data.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _specialist_input(
    session: Session,
    model: type,
    identifier: uuid.UUID | None,
    case_id: uuid.UUID,
    snapshot_id: uuid.UUID,
    object_id: uuid.UUID,
    label: str,
) -> Any | None:
    if identifier is None:
        return None
    value = session.get(model, identifier)
    if (
        value is None
        or value.case_id != case_id
        or value.snapshot_id != snapshot_id
        or value.controlled_object_id != object_id
    ):
        raise HTTPException(status_code=422, detail=f"{label} input is outside this snapshot")
    return value


def _clock(
    clock_type: DecisionClockType, days: int | None, target: date | None = None
) -> dict[str, Any]:
    return {
        "clock_type": clock_type.value,
        "duration_days": days,
        "target_date": target.isoformat() if target else None,
    }


def _severity_rank(value: ConsequenceSeverity) -> int:
    return {
        ConsequenceSeverity.NONE: 0,
        ConsequenceSeverity.LOW: 1,
        ConsequenceSeverity.MEDIUM: 2,
        ConsequenceSeverity.HIGH: 3,
        ConsequenceSeverity.CRITICAL: 4,
    }[value]


def create_impact_assessment(
    session: Session,
    actor: ActorContext,
    project: Project,
    case_id: uuid.UUID,
    data: ImpactAssessmentCreate,
    idempotency_key: str,
) -> tuple[Any, ImpactAssessment]:
    digest = request_digest(data)
    existing = session.scalar(
        select(ImpactAssessment).where(
            ImpactAssessment.case_id == case_id,
            ImpactAssessment.idempotency_key == idempotency_key,
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
        raise HTTPException(status_code=422, detail="Impact object is outside the snapshot")

    progress = _specialist_input(
        session,
        ProgressEvaluation,
        data.progress_evaluation_id,
        case.id,
        snapshot.id,
        data.controlled_object_id,
        "Progress",
    )
    schedule = _specialist_input(
        session,
        ScheduleAssessment,
        data.schedule_assessment_id,
        case.id,
        snapshot.id,
        data.controlled_object_id,
        "Schedule",
    )
    cost = _specialist_input(
        session,
        CostAssessment,
        data.cost_assessment_id,
        case.id,
        snapshot.id,
        data.controlled_object_id,
        "Cost",
    )
    forecasts: list[ForecastProjection] = []
    forecast_sources: dict[tuple[str, uuid.UUID], Any] = {}
    for identifier in data.forecast_projection_ids:
        forecast = session.get(ForecastProjection, identifier)
        if (
            forecast is None
            or forecast.case_id != case.id
            or forecast.snapshot_id != snapshot.id
            or forecast.controlled_object_id != data.controlled_object_id
        ):
            raise HTTPException(status_code=422, detail="Forecast input is outside this snapshot")
        for label, model, identifier in (
            ("PROGRESS", ProgressEvaluation, forecast.progress_evaluation_id),
            ("SCHEDULE", ScheduleAssessment, forecast.schedule_assessment_id),
            ("COST", CostAssessment, forecast.cost_assessment_id),
        ):
            source = _specialist_input(
                session,
                model,
                identifier,
                case.id,
                snapshot.id,
                data.controlled_object_id,
                f"Forecast {label}",
            )
            if source is not None:
                forecast_sources[(label, source.id)] = source
        forecasts.append(forecast)

    policy = resolve_policy(session, project, data.policy_version)
    paths: list[dict[str, Any]] = []
    severity = ConsequenceSeverity.NONE
    if progress and progress.threshold_crossed:
        paths.append(
            {
                "type": ConsequenceType.DOWNSTREAM_WORK.value,
                "source": "PROGRESS",
                "variance_ratio": str(progress.variance_ratio),
                "persistence": progress.persistence,
                "conclusion_boundary": (
                    "Variance only; schedule consequence requires schedule evidence"
                ),
            }
        )
        severity = ConsequenceSeverity.LOW
    if schedule and schedule.assessment_status == "ASSESSED":
        for path in schedule.downstream_paths:
            paths.append(
                {"type": ConsequenceType.DOWNSTREAM_WORK.value, "source": "SCHEDULE", **path}
            )
        if any(Decimal(path["residual_delay_days"]) > 0 for path in schedule.downstream_paths):
            severity = max((severity, ConsequenceSeverity.MEDIUM), key=_severity_rank)
        for exposure in schedule.milestone_exposures:
            paths.append(
                {"type": ConsequenceType.MATERIAL_MILESTONE.value, "source": "SCHEDULE", **exposure}
            )
        if any(item.get("material", True) for item in schedule.milestone_exposures):
            severity = ConsequenceSeverity.CRITICAL
        if (
            schedule.project_completion_exposure_days is not None
            and schedule.project_completion_exposure_days > 0
        ):
            paths.append(
                {
                    "type": ConsequenceType.PROJECT_COMPLETION.value,
                    "source": "SCHEDULE",
                    "exposure_days": str(schedule.project_completion_exposure_days),
                }
            )
            severity = max((severity, ConsequenceSeverity.HIGH), key=_severity_rank)
    cost_ratio = Decimal("0")
    if (
        cost
        and cost.assessment_status == "ASSESSED"
        and cost.estimate_at_completion is not None
        and cost.current_authorized_budget > 0
    ):
        exposure = max(Decimal("0"), cost.estimate_at_completion - cost.current_authorized_budget)
        cost_ratio = exposure / cost.current_authorized_budget
        if exposure > 0:
            paths.append(
                {
                    "type": ConsequenceType.COST_EXPOSURE.value,
                    "source": "COST",
                    "amount": str(exposure),
                    "currency": cost.currency,
                    "authorized_budget": str(cost.current_authorized_budget),
                    "exposure_ratio": str(cost_ratio),
                }
            )
        threshold_severity = ConsequenceSeverity.NONE
        if cost_ratio >= Decimal(str(policy_value(policy, "critical_cost_exposure_ratio"))):
            threshold_severity = ConsequenceSeverity.CRITICAL
        elif cost_ratio >= Decimal(str(policy_value(policy, "high_cost_exposure_ratio"))):
            threshold_severity = ConsequenceSeverity.HIGH
        elif cost_ratio >= Decimal(str(policy_value(policy, "medium_cost_exposure_ratio"))):
            threshold_severity = ConsequenceSeverity.MEDIUM
        elif exposure > 0:
            threshold_severity = ConsequenceSeverity.LOW
        severity = max((severity, threshold_severity), key=_severity_rank)
        for effect in cost.explained_effects:
            paths.append(
                {
                    "type": ConsequenceType.COMMERCIAL_EXPOSURE.value,
                    "source": "COST",
                    "effect": effect,
                    "conclusion_boundary": (
                        "Exposure indication only; no entitlement or liability conclusion"
                    ),
                }
            )

    forecast_validities = {str(value.id): validity_for(session, value) for value in forecasts}
    for forecast in forecasts:
        paths.append(
            {
                "type": ConsequenceType.RECOVERY_OPTION.value
                if forecast.active_response_id
                else ConsequenceType.DOWNSTREAM_WORK.value,
                "source": "FORECAST",
                "forecast_id": str(forecast.id),
                "input_evidence_ids": list(forecast.input_evidence_ids),
                "source_result_ids": [
                    str(identifier)
                    for identifier in (
                        forecast.progress_evaluation_id,
                        forecast.schedule_assessment_id,
                        forecast.cost_assessment_id,
                    )
                    if identifier is not None
                ],
                "semantic_state": forecast.semantic_state,
                "truth_type": forecast.truth_type,
                "assumptions": list(forecast.assumptions),
                "limitations": list(forecast.limitations),
                "target": forecast.target,
                "scenario_type": forecast.scenario_type,
                "range": [forecast.result_lower, forecast.result_point, forecast.result_upper],
                "result_unit": forecast.result_unit,
                "horizon_end": forecast.horizon_end.isoformat(),
                "active_response_id": str(forecast.active_response_id)
                if forecast.active_response_id
                else None,
            }
        )
    # Preserve the exact specialist result and evidence behind every consequence path.
    sources = {"PROGRESS": progress, "SCHEDULE": schedule, "COST": cost}
    for path in paths:
        source = sources.get(path["source"])
        if source is not None:
            path["source_result_id"] = str(source.id)
            path["input_evidence_ids"] = list(source.input_evidence_ids)
    active_responses = (
        list(
            session.scalars(
                select(CaseActiveResponse).where(
                    CaseActiveResponse.case_id == case.id,
                    CaseActiveResponse.id.in_(
                        [uuid.UUID(value) for value in snapshot.active_response_ids]
                    ),
                )
            )
        )
        if snapshot.active_response_ids
        else []
    )
    assessed_at = datetime.now(UTC)
    qualified_response_ids: list[str] = []
    for response in active_responses:
        qualification = qualify_recovery(
            response, forecasts, forecast_validities, snapshot.data_date, assessed_at
        )
        if qualification["qualified"]:
            qualified_response_ids.append(str(response.id))
        for path in paths:
            if path.get("active_response_id") == str(response.id):
                path["recovery_qualification"] = qualification
        paths.append(
            {
                "type": ConsequenceType.RECOVERY_OPTION.value,
                "source": "AUTHORIZED_RESPONSE",
                "active_response_id": str(response.id),
                "authorization_reference": response.authorization_reference,
                "status": response.status,
                "recovery_qualification": qualification,
                "conclusion_boundary": "Authorized option recorded; outcome is not presumed",
            }
        )

    confidences: list[Decimal] = []
    evidence_ids: set[str] = set()
    truth_types: list[str] = []
    for value in (progress, schedule, cost, *forecast_sources.values()):
        if value:
            confidences.append(Decimal(str(value.confidence)))
            evidence_ids.update(value.input_evidence_ids)
            truth_types.append(value.truth_type)
    for forecast in forecasts:
        confidences.append(Decimal(str(forecast.upstream_confidence)))
        evidence_ids.update(forecast.input_evidence_ids)
    reliability_values = (
        list(
            session.scalars(
                select(EvidenceItem.source_reliability).where(
                    EvidenceItem.id.in_([uuid.UUID(value) for value in evidence_ids]),
                    EvidenceItem.source_reliability.is_not(None),
                )
            )
        )
        if evidence_ids
        else []
    )
    components = impact_confidence(
        confidences,
        [Decimal(str(value.horizon_confidence)) for value in forecasts],
        [Decimal(str(value)) for value in reliability_values],
    )
    truth_confidence = components.truth
    forecast_confidence = components.forecast
    consequence_confidence = components.consequence
    upstream_ceiling = components.upstream_ceiling
    overall_confidence = components.overall
    override = None
    if data.confidence_override_id:
        override = session.get(ConfidenceOverride, data.confidence_override_id)
        if (
            override is None
            or override.case_id != case.id
            or override.snapshot_id != snapshot.id
            or Decimal(str(override.upstream_ceiling)) != upstream_ceiling
        ):
            raise HTTPException(
                status_code=422,
                detail=(
                    "Confidence override does not match this case, snapshot, and computed ceiling"
                ),
            )
        overall_confidence = Decimal(str(override.approved_confidence))

    data_date = snapshot.data_date.date()
    consequence_days = (data.consequence_date - data_date).days if data.consequence_date else None
    recovery_days = (
        (data.recovery_window_end - data_date).days if data.recovery_window_end else None
    )
    clocks = [
        _clock(DecisionClockType.CONSEQUENCE, consequence_days, data.consequence_date),
        _clock(DecisionClockType.VERIFICATION, data.verification_duration_days),
        _clock(DecisionClockType.APPROVAL, data.approval_duration_days),
        _clock(DecisionClockType.MOBILIZATION, data.mobilization_duration_days),
        _clock(DecisionClockType.RECOVERY_WINDOW, recovery_days, data.recovery_window_end),
    ]
    response_lead = (
        data.verification_duration_days
        + data.approval_duration_days
        + data.mobilization_duration_days
    )
    available_values = [value for value in (consequence_days, recovery_days) if value is not None]
    margin = min(available_values) - response_lead if available_values else None
    if margin is None:
        urgency = UrgencyLevel.NONE
    elif margin <= 0:
        urgency = UrgencyLevel.IMMEDIATE
    elif margin <= int(policy_value(policy, "urgent_margin_days")):
        urgency = UrgencyLevel.URGENT
    elif margin <= int(policy_value(policy, "elevated_margin_days")):
        urgency = UrgencyLevel.ELEVATED
    else:
        urgency = UrgencyLevel.ROUTINE

    severity_points = Decimal(
        str(
            {
                ConsequenceSeverity.NONE: 0,
                ConsequenceSeverity.LOW: 25,
                ConsequenceSeverity.MEDIUM: 50,
                ConsequenceSeverity.HIGH: 75,
                ConsequenceSeverity.CRITICAL: 100,
            }[severity]
        )
    )
    urgency_points = Decimal(
        str(
            {
                UrgencyLevel.NONE: 0,
                UrgencyLevel.ROUTINE: 10,
                UrgencyLevel.ELEVATED: 25,
                UrgencyLevel.URGENT: 40,
                UrgencyLevel.IMMEDIATE: 50,
            }[urgency]
        )
    )
    reach = max(1, len(snapshot.controlled_object_ids))
    score = (
        severity_points * Decimal("0.6") + urgency_points * Decimal("0.3")
    ) * overall_confidence
    score += Decimal(max(0, reach - 1)) * Decimal(
        str(policy_value(policy, "cross_cutting_bonus_per_object"))
    )
    response_reduction_applied = bool(qualified_response_ids) and all(
        not value.limitations and value.truth_type != TruthType.CONTRADICTED
        for value in (progress, schedule, cost, *forecast_sources.values()) if value is not None
    ) and all(value == ForecastValidity.CURRENT for value in forecast_validities.values())
    if response_reduction_applied:
        score -= Decimal(str(policy_value(policy, "active_response_score_reduction")))
    score = min(Decimal("100"), max(Decimal("0"), score)).quantize(Decimal("0.001"))
    if score >= Decimal(str(policy_value(policy, "critical_priority_score"))):
        band = PriorityBand.CRITICAL
    elif score >= Decimal(str(policy_value(policy, "high_priority_score"))):
        band = PriorityBand.HIGH
    elif score >= Decimal(str(policy_value(policy, "medium_priority_score"))):
        band = PriorityBand.MEDIUM
    else:
        band = PriorityBand.LOW
    reason_codes = [
        f"CONSEQUENCE_{severity.value}",
        f"URGENCY_{urgency.value}",
        "UPSTREAM_CONFIDENCE_CEILING",
    ]
    if reliability_values:
        reason_codes.append("SOURCE_RELIABILITY_APPLIED")
    if reach > 1:
        reason_codes.append("CROSS_CUTTING_REACH")
    if response_reduction_applied:
        reason_codes.append("QUALIFIED_RECOVERY_REDUCTION")
    elif active_responses:
        reason_codes.append("ACTIVE_RESPONSE_NO_PRIORITY_REDUCTION")
    if override:
        reason_codes.append("APPROVED_CONFIDENCE_OVERRIDE")

    limitations: list[dict[str, Any]] = []
    assessment_status = ImpactAssessmentStatus.ASSESSED
    restricted_sources = {
        (label, value.id): value
        for label, value in (("SCHEDULE", schedule), ("COST", cost))
        if value is not None
    }
    restricted_sources.update(
        {key: value for key, value in forecast_sources.items() if key[0] != "PROGRESS"}
    )
    for (label, _), value in restricted_sources.items():
        if value and value.assessment_status != "ASSESSED":
            assessment_status = ImpactAssessmentStatus.VERIFICATION_REQUIRED
            limitations.append(
                {
                    "code": f"{label}_INPUT_RESTRICTED",
                    "source_id": str(value.id),
                    "upstream_status": value.assessment_status,
                    "upstream_limitations": value.limitations,
                    "description": "Upstream stop gates prevent supported consequence conclusions",
                }
            )
    for (label, source_id), source in forecast_sources.items():
        if source.limitations:
            if assessment_status == ImpactAssessmentStatus.ASSESSED:
                assessment_status = ImpactAssessmentStatus.LIMITED
            limitations.append(
                {
                    "code": "FORECAST_SOURCE_LIMITATIONS",
                    "source_type": label,
                    "source_id": str(source_id),
                    "upstream_limitations": list(source.limitations),
                    "description": "Forecast source limitations remain applicable",
                }
            )
    for forecast in forecasts:
        if forecast.limitations:
            if assessment_status == ImpactAssessmentStatus.ASSESSED:
                assessment_status = ImpactAssessmentStatus.LIMITED
            limitations.append(
                {
                    "code": "FORECAST_INPUT_LIMITATIONS",
                    "forecast_id": str(forecast.id),
                    "upstream_limitations": list(forecast.limitations),
                    "description": "Selected forecast limitations remain applicable",
                }
            )
        if forecast.semantic_state == "SCENARIO":
            if assessment_status == ImpactAssessmentStatus.ASSESSED:
                assessment_status = ImpactAssessmentStatus.LIMITED
            limitations.append(
                {
                    "code": "HYPOTHETICAL_SCENARIO_INPUT",
                    "forecast_id": str(forecast.id),
                    "description": (
                        "Hypothetical consequences depend on assumptions, not authorization"
                    ),
                }
            )
    if any(value == TruthType.CONTRADICTED for value in truth_types):
        assessment_status = ImpactAssessmentStatus.VERIFICATION_REQUIRED
        limitations.append(
            {"code": "CONTRADICTED_INPUT", "description": "A selected truth input is contradicted"}
        )
    non_current = [
        str(value.id)
        for value in forecasts
        if forecast_validities[str(value.id)] != ForecastValidity.CURRENT
    ]
    if non_current:
        assessment_status = ImpactAssessmentStatus.VERIFICATION_REQUIRED
        limitations.append({"code": "FORECAST_RECALCULATION_REQUIRED", "forecast_ids": non_current})
    if margin is None:
        if assessment_status == ImpactAssessmentStatus.ASSESSED:
            assessment_status = ImpactAssessmentStatus.LIMITED
        limitations.append(
            {
                "code": "NO_DECISION_DEADLINE",
                "description": "Urgency cannot be timed without a consequence or recovery date",
            }
        )

    number = (
        session.scalar(
            select(func.max(ImpactAssessment.assessment_number)).where(
                ImpactAssessment.case_id == case.id
            )
        )
        or 0
    ) + 1
    assessment = ImpactAssessment(
        id=uuid.uuid4(),
        organization_id=project.organization_id,
        project_id=project.id,
        case_id=case.id,
        snapshot_id=snapshot.id,
        controlled_object_id=data.controlled_object_id,
        progress_evaluation_id=data.progress_evaluation_id,
        schedule_assessment_id=data.schedule_assessment_id,
        cost_assessment_id=data.cost_assessment_id,
        forecast_projection_ids=[str(value) for value in data.forecast_projection_ids],
        confidence_override_id=data.confidence_override_id,
        assessment_number=number,
        consequence_paths=paths,
        consequence_severity=severity,
        decision_clocks=clocks,
        response_lead_days=response_lead,
        urgency_margin_days=margin,
        urgency=urgency,
        truth_confidence=truth_confidence,
        forecast_confidence=forecast_confidence,
        consequence_confidence=consequence_confidence,
        upstream_confidence_ceiling=upstream_ceiling,
        overall_confidence=overall_confidence,
        cross_cutting_reach=reach,
        active_response_count=len(active_responses),
        priority_score=score,
        priority_band=band,
        priority_reason_codes=reason_codes,
        assessment_status=assessment_status,
        limitations=limitations,
        policy_version=data.policy_version,
        formula_version=FORMULA_VERSION,
        idempotency_key=idempotency_key,
        request_hash=digest,
        assessed_by=actor.actor_id,
    )
    session.add(assessment)
    session.flush()
    case.last_impact_assessment_id = assessment.id
    case.version += 1
    add_ledger(
        session,
        actor,
        case,
        CaseLedgerEventType.IMPACT_ASSESSED,
        "Consequence, confidence, urgency, and priority assessed independently",
        details={
            "impact_assessment_id": str(assessment.id),
            "severity": severity.value,
            "urgency": urgency.value,
            "priority_band": band.value,
            "overall_confidence": str(overall_confidence),
        },
    )
    audit_case(
        session, actor, case, "IMPACT_ASSESSED", {"impact_assessment_id": str(assessment.id)}
    )
    return case, assessment
