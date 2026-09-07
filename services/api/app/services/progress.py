from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from app.auth import ActorContext
from app.generated.taxonomies import (
    AuthorizedContextType,
    CaseLedgerEventType,
    CaseLifecycle,
    ContradictionStatus,
    DeviationDirection,
    ProgressBasis,
    ProgressMeasurementKind,
    ProgressReconciliationStatus,
    SemanticState,
    TrendDirection,
    TrendPersistence,
    TruthType,
)
from app.models import (
    AuthorizedContextVersion,
    CaseSnapshot,
    Contradiction,
    ControlledObject,
    DecisionCaseShell,
    ProgressEvaluation,
    ProgressMeasurement,
    ProgressThresholdPolicy,
    Project,
)
from app.progress_schemas import (
    ProgressEvaluationCreate,
    ProgressMeasurementCreate,
    ProgressPolicyCreate,
)
from app.services.audit import record_audit
from app.services.cases import add_ledger, audit_case, require_version, scoped_case
from app.services.evidence import scoped_item
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

DEFAULT_POLICY_VERSION = "PROGRESS-DEFAULT-1.0.0"
FORMULA_VERSION = "PROGRESS-DEVIATION-1.0.0"
DEFAULT_POLICY = {
    "id": None,
    "organization_id": None,
    "project_id": None,
    "policy_version": DEFAULT_POLICY_VERSION,
    "deviation_threshold": Decimal("0.05"),
    "on_plan_tolerance": Decimal("0.01"),
    "persistence_min_observations": 3,
    "persistence_min_duration_days": 7,
    "rationale": "Visible MVP default: 5% deviation and three observations across seven days",
    "supersedes_policy_id": None,
    "created_by": "SYSTEM",
    "created_at": None,
}

KIND_SEMANTICS = {
    ProgressMeasurementKind.PLANNED_AUTHORIZED: {SemanticState.CURRENT_AUTHORIZED},
    ProgressMeasurementKind.REPORTED: {SemanticState.REPORTED},
    ProgressMeasurementKind.EXECUTED: {SemanticState.ACTUAL},
    ProgressMeasurementKind.VERIFIED: {SemanticState.VERIFIED},
    ProgressMeasurementKind.ACCEPTED_RELEASED: {SemanticState.VERIFIED},
}
KIND_BASIS = {
    ProgressMeasurementKind.REPORTED: ProgressBasis.REPORTED_PERCENT_COMPLETE,
    ProgressMeasurementKind.EXECUTED: ProgressBasis.PHYSICAL_EXECUTED,
    ProgressMeasurementKind.VERIFIED: ProgressBasis.PHYSICAL_VERIFIED,
    ProgressMeasurementKind.ACCEPTED_RELEASED: ProgressBasis.ACCEPTED_RELEASED,
}


def utc_value(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def decimal_value(value: Any, label: str) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise HTTPException(status_code=422, detail=f"{label} must be numeric")
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"{label} must be numeric") from exc


def create_policy(
    session: Session,
    actor: ActorContext,
    project: Project,
    data: ProgressPolicyCreate,
) -> ProgressThresholdPolicy:
    if data.policy_version == DEFAULT_POLICY_VERSION:
        raise HTTPException(status_code=409, detail="Default policy version is reserved")
    if data.supersedes_policy_id:
        previous = session.get(ProgressThresholdPolicy, data.supersedes_policy_id)
        if previous is None or previous.project_id != project.id:
            raise HTTPException(status_code=422, detail="Superseded progress policy not found")
    policy = ProgressThresholdPolicy(
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
        action="PROGRESS_POLICY_CREATED",
        object_type="PROGRESS_THRESHOLD_POLICY",
        object_id=str(policy.id),
        details={"policy_version": policy.policy_version},
    )
    return policy


def list_policies(
    session: Session, project: Project
) -> list[dict[str, Any] | ProgressThresholdPolicy]:
    configured = list(
        session.scalars(
            select(ProgressThresholdPolicy)
            .where(ProgressThresholdPolicy.project_id == project.id)
            .order_by(ProgressThresholdPolicy.created_at)
        )
    )
    return [DEFAULT_POLICY, *configured]


def resolve_policy(
    session: Session, project: Project, version: str
) -> dict[str, Any] | ProgressThresholdPolicy:
    if version == DEFAULT_POLICY_VERSION:
        return DEFAULT_POLICY
    policy = session.scalar(
        select(ProgressThresholdPolicy).where(
            ProgressThresholdPolicy.project_id == project.id,
            ProgressThresholdPolicy.policy_version == version,
        )
    )
    if policy is None:
        raise HTTPException(status_code=422, detail="Unsupported progress policy version")
    return policy


def record_measurement(
    session: Session,
    actor: ActorContext,
    project: Project,
    data: ProgressMeasurementCreate,
) -> ProgressMeasurement:
    evidence = scoped_item(session, project, data.evidence_item_id)
    if evidence.controlled_object_id is None:
        raise HTTPException(
            status_code=422, detail="Progress evidence requires a controlled object"
        )
    if "progress" not in evidence.field_name.lower():
        raise HTTPException(status_code=422, detail="Evidence item is not a progress assertion")
    if evidence.measurement_basis is None:
        raise HTTPException(status_code=422, detail="Progress evidence has no measurement basis")
    try:
        basis = ProgressBasis(evidence.measurement_basis)
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail="Unsupported progress measurement basis"
        ) from exc
    required_basis = KIND_BASIS.get(data.measurement_kind)
    if required_basis and basis != required_basis:
        raise HTTPException(
            status_code=422,
            detail=f"{data.measurement_kind} requires measurement basis {required_basis}",
        )
    if evidence.semantic_state not in KIND_SEMANTICS[data.measurement_kind]:
        raise HTTPException(
            status_code=422,
            detail=(
                f"{data.measurement_kind} requires semantic state "
                f"{sorted(KIND_SEMANTICS[data.measurement_kind])[0]}"
            ),
        )
    if data.measurement_kind != ProgressMeasurementKind.PLANNED_AUTHORIZED and utc_value(
        evidence.as_of
    ) > datetime.now(UTC):
        raise HTTPException(status_code=422, detail="Observed progress cannot be future-dated")
    if decimal_value(evidence.value, "Evidence value") != data.numerator:
        raise HTTPException(
            status_code=422, detail="Numerator must equal the source evidence value"
        )
    if evidence.unit and evidence.unit != data.unit:
        raise HTTPException(status_code=422, detail="Measurement unit differs from source evidence")
    context = None
    if data.measurement_kind == ProgressMeasurementKind.PLANNED_AUTHORIZED:
        context = session.get(AuthorizedContextVersion, data.authorized_context_id)
        if (
            context is None
            or context.project_id != project.id
            or context.context_type != AuthorizedContextType.SCHEDULE
            or context.semantic_state != SemanticState.CURRENT_AUTHORIZED
            or utc_value(context.effective_from) > utc_value(evidence.as_of)
            or context.activated_at is None
            or utc_value(context.activated_at) > utc_value(evidence.as_of)
            or (
                context.superseded_at is not None
                and utc_value(context.superseded_at) <= utc_value(evidence.as_of)
            )
        ):
            raise HTTPException(
                status_code=422,
                detail="Planned progress requires the schedule authorized at its as-of time",
            )
        controlled_object = session.get(ControlledObject, evidence.controlled_object_id)
        matching_points = [
            point
            for activity in context.payload.get("activities", [])
            if activity.get("controlled_object_code") == controlled_object.code
            for point in activity.get("progress_plan", [])
            if point.get("as_of") == utc_value(evidence.as_of).date().isoformat()
            and point.get("measurement_basis") == basis
            and Decimal(str(point.get("numerator"))) == data.numerator
            and Decimal(str(point.get("denominator"))) == data.denominator
            and point.get("unit") == data.unit
        ]
        if not matching_points:
            raise HTTPException(
                status_code=422,
                detail="Planned progress is not present in the authorized schedule payload",
            )
    elif data.authorized_context_id is not None:
        raise HTTPException(
            status_code=422, detail="Only planned progress links authorized context"
        )
    existing = session.scalar(
        select(ProgressMeasurement).where(ProgressMeasurement.evidence_item_id == evidence.id)
    )
    ratio = data.numerator / data.denominator
    if ratio > 1:
        raise HTTPException(status_code=422, detail="Progress completion cannot exceed denominator")
    if existing:
        same = (
            existing.measurement_kind == data.measurement_kind
            and existing.authorized_context_id == data.authorized_context_id
            and existing.numerator == data.numerator
            and existing.denominator == data.denominator
            and existing.unit == data.unit
        )
        if not same:
            raise HTTPException(
                status_code=409, detail="Evidence already has another normalization"
            )
        return existing
    measurement = ProgressMeasurement(
        id=uuid.uuid4(),
        organization_id=project.organization_id,
        project_id=project.id,
        controlled_object_id=evidence.controlled_object_id,
        evidence_item_id=evidence.id,
        authorized_context_id=context.id if context else None,
        measurement_kind=data.measurement_kind,
        measurement_basis=basis,
        numerator=data.numerator,
        denominator=data.denominator,
        completion_ratio=ratio,
        unit=data.unit,
        as_of=evidence.as_of,
        semantic_state=evidence.semantic_state,
        truth_type=evidence.truth_type,
        confidence=evidence.confidence,
        recorded_by=actor.actor_id,
    )
    session.add(measurement)
    record_audit(
        session,
        actor,
        organization_id=project.organization_id,
        project_id=project.id,
        action="PROGRESS_MEASUREMENT_RECORDED",
        object_type="PROGRESS_MEASUREMENT",
        object_id=str(measurement.id),
        details={"evidence_item_id": str(evidence.id), "measurement_kind": data.measurement_kind},
    )
    return measurement


def scoped_measurement(
    session: Session, project: Project, measurement_id: uuid.UUID
) -> ProgressMeasurement:
    measurement = session.get(ProgressMeasurement, measurement_id)
    if measurement is None or measurement.project_id != project.id:
        raise HTTPException(status_code=404, detail="Progress measurement not found")
    return measurement


def evaluation_digest(data: ProgressEvaluationCreate) -> str:
    return hashlib.sha256(
        json.dumps(data.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def measure_projection(measurement: ProgressMeasurement) -> dict[str, Any]:
    return {
        "measurement_id": str(measurement.id),
        "evidence_item_id": str(measurement.evidence_item_id),
        "measurement_kind": measurement.measurement_kind,
        "measurement_basis": measurement.measurement_basis,
        "completion_ratio": str(measurement.completion_ratio),
        "as_of": utc_value(measurement.as_of).isoformat(),
        "semantic_state": measurement.semantic_state,
        "truth_type": measurement.truth_type,
        "confidence": str(measurement.confidence),
    }


def calculate_productivity(
    current: ProgressMeasurement, prior: ProgressMeasurement | None
) -> Decimal | None:
    if prior is None:
        return None
    elapsed = (utc_value(current.as_of) - utc_value(prior.as_of)).total_seconds() / 86400
    if elapsed <= 0 or current.completion_ratio < prior.completion_ratio:
        raise HTTPException(
            status_code=422,
            detail="Prior progress must be earlier and cumulative progress cannot decrease",
        )
    return (current.completion_ratio - prior.completion_ratio) / Decimal(str(elapsed))


def evaluate_progress(
    session: Session,
    actor: ActorContext,
    project: Project,
    case_id: uuid.UUID,
    data: ProgressEvaluationCreate,
    idempotency_key: str,
) -> tuple[DecisionCaseShell, ProgressEvaluation]:
    request_hash = evaluation_digest(data)
    existing = session.scalar(
        select(ProgressEvaluation).where(
            ProgressEvaluation.case_id == case_id,
            ProgressEvaluation.idempotency_key == idempotency_key,
        )
    )
    if existing:
        if existing.request_hash != request_hash:
            raise HTTPException(status_code=409, detail="Idempotency key payload mismatch")
        return scoped_case(session, project, case_id), existing

    case = scoped_case(session, project, case_id, for_update=True)
    require_version(case, data.expected_version)
    if case.lifecycle == CaseLifecycle.CLOSED:
        raise HTTPException(
            status_code=409, detail="Closed case must be reopened before evaluation"
        )
    snapshot = session.get(CaseSnapshot, data.snapshot_id)
    if snapshot is None or snapshot.case_id != case.id:
        raise HTTPException(status_code=404, detail="Case snapshot not found")
    policy = resolve_policy(session, project, data.policy_version)
    planned = scoped_measurement(session, project, data.planned_measurement_id)
    actual = scoped_measurement(session, project, data.actual_measurement_id)
    if planned.measurement_kind != ProgressMeasurementKind.PLANNED_AUTHORIZED:
        raise HTTPException(
            status_code=422, detail="Planned input is not authorized planned progress"
        )
    if actual.measurement_kind == ProgressMeasurementKind.PLANNED_AUTHORIZED:
        raise HTTPException(
            status_code=422, detail="Actual input must use an observed progress gate"
        )
    if planned.controlled_object_id != actual.controlled_object_id:
        raise HTTPException(status_code=422, detail="Progress inputs refer to different objects")
    if str(actual.controlled_object_id) not in snapshot.controlled_object_ids:
        raise HTTPException(status_code=422, detail="Progress object is outside the case snapshot")
    if planned.measurement_basis != actual.measurement_basis:
        raise HTTPException(status_code=422, detail="Progress measurement bases are incomparable")
    if planned.unit != actual.unit or planned.denominator != actual.denominator:
        raise HTTPException(
            status_code=422, detail="Progress units or denominators are incomparable"
        )
    snapshot_evidence = set(snapshot.evidence_item_ids)
    if not {str(planned.evidence_item_id), str(actual.evidence_item_id)} <= snapshot_evidence:
        raise HTTPException(
            status_code=422, detail="Progress inputs are not frozen in the snapshot"
        )
    if utc_value(planned.recorded_at) > utc_value(snapshot.created_at) or utc_value(
        actual.recorded_at
    ) > utc_value(snapshot.created_at):
        raise HTTPException(
            status_code=422, detail="Progress normalization was not frozen before the snapshot"
        )
    context_ids = {value["id"] for value in snapshot.authorized_context_refs}
    if str(planned.authorized_context_id) not in context_ids:
        raise HTTPException(status_code=422, detail="Planned progress context is not in snapshot")
    if utc_value(planned.as_of) > utc_value(snapshot.data_date) or utc_value(
        actual.as_of
    ) > utc_value(snapshot.data_date):
        raise HTTPException(
            status_code=422, detail="Progress input is later than snapshot data date"
        )

    prior_planned = (
        scoped_measurement(session, project, data.prior_planned_measurement_id)
        if data.prior_planned_measurement_id
        else None
    )
    prior_actual = (
        scoped_measurement(session, project, data.prior_actual_measurement_id)
        if data.prior_actual_measurement_id
        else None
    )
    for prior, current in ((prior_planned, planned), (prior_actual, actual)):
        if prior and (
            prior.controlled_object_id != current.controlled_object_id
            or prior.measurement_basis != current.measurement_basis
            or prior.measurement_kind != current.measurement_kind
            or prior.unit != current.unit
            or prior.denominator != current.denominator
            or str(prior.evidence_item_id) not in snapshot_evidence
            or utc_value(prior.recorded_at) > utc_value(snapshot.created_at)
        ):
            raise HTTPException(status_code=422, detail="Prior progress input is incompatible")

    all_measurements = list(
        session.scalars(
            select(ProgressMeasurement).where(
                ProgressMeasurement.project_id == project.id,
                ProgressMeasurement.controlled_object_id == actual.controlled_object_id,
                ProgressMeasurement.evidence_item_id.in_(
                    [uuid.UUID(value) for value in snapshot.evidence_item_ids]
                ),
            )
        )
    )
    latest_by_kind: dict[str, ProgressMeasurement] = {}
    for measurement in sorted(all_measurements, key=lambda value: utc_value(value.as_of)):
        key = (
            f"{measurement.measurement_kind}:{measurement.measurement_basis}"
            if measurement.measurement_kind == ProgressMeasurementKind.PLANNED_AUTHORIZED
            else measurement.measurement_kind
        )
        latest_by_kind[key] = measurement
    reconciled = {kind: measure_projection(value) for kind, value in latest_by_kind.items()}

    contradiction_ids = [uuid.UUID(value) for value in snapshot.contradiction_ids]
    contradictions = list(
        session.scalars(
            select(Contradiction).where(
                Contradiction.id.in_(contradiction_ids),
                Contradiction.status == ContradictionStatus.OPEN,
            )
        )
    )
    critical_evidence = {planned.evidence_item_id, actual.evidence_item_id}
    relevant_contradictions = [
        value
        for value in contradictions
        if value.left_item_id in critical_evidence or value.right_item_id in critical_evidence
    ]
    strong_truth = {TruthType.VERIFIED_FACT, TruthType.CORROBORATED_FACT}
    limitations: list[dict[str, Any]] = []
    if actual.truth_type not in strong_truth:
        limitations.append(
            {
                "code": "WEAK_ACTUAL_TRUTH",
                "description": "Selected actual progress is not verified or corroborated",
                "evidence_item_id": str(actual.evidence_item_id),
            }
        )
    for contradiction in relevant_contradictions:
        limitations.append(
            {
                "code": "UNRESOLVED_PROGRESS_CONTRADICTION",
                "description": f"Progress input participates in contradiction {contradiction.id}",
                "contradiction_id": str(contradiction.id),
            }
        )
    reconciliation = (
        ProgressReconciliationStatus.VERIFICATION_REQUIRED
        if limitations
        else ProgressReconciliationStatus.RECONCILED
    )

    planned_ratio = Decimal(planned.completion_ratio)
    actual_ratio = Decimal(actual.completion_ratio)
    variance = actual_ratio - planned_ratio
    tolerance = (
        Decimal(str(policy["on_plan_tolerance"]))
        if isinstance(policy, dict)
        else Decimal(policy.on_plan_tolerance)
    )
    threshold = (
        Decimal(str(policy["deviation_threshold"]))
        if isinstance(policy, dict)
        else Decimal(policy.deviation_threshold)
    )
    if abs(variance) <= tolerance:
        direction = DeviationDirection.ON_PLAN
    elif variance < 0:
        direction = DeviationDirection.BEHIND
    else:
        direction = DeviationDirection.AHEAD
    threshold_crossed = abs(variance) >= threshold

    previous = session.scalar(
        select(ProgressEvaluation)
        .where(
            ProgressEvaluation.case_id == case.id,
            ProgressEvaluation.controlled_object_id == actual.controlled_object_id,
            ProgressEvaluation.measurement_basis == actual.measurement_basis,
            ProgressEvaluation.data_date < snapshot.data_date,
        )
        .order_by(ProgressEvaluation.data_date.desc(), ProgressEvaluation.evaluation_number.desc())
    )
    if previous is None:
        trend = TrendDirection.FIRST_OBSERVATION
    elif abs(abs(variance) - Decimal(previous.variance_magnitude)) <= tolerance:
        trend = TrendDirection.STABLE
    elif abs(variance) > Decimal(previous.variance_magnitude):
        trend = TrendDirection.DETERIORATING
    else:
        trend = TrendDirection.RECOVERING

    supporting = [snapshot.data_date]
    if (
        reconciliation == ProgressReconciliationStatus.RECONCILED
        and threshold_crossed
        and direction != DeviationDirection.ON_PLAN
    ):
        history = list(
            session.scalars(
                select(ProgressEvaluation)
                .where(
                    ProgressEvaluation.case_id == case.id,
                    ProgressEvaluation.controlled_object_id == actual.controlled_object_id,
                    ProgressEvaluation.measurement_basis == actual.measurement_basis,
                    ProgressEvaluation.data_date < snapshot.data_date,
                )
                .order_by(
                    ProgressEvaluation.data_date.desc(),
                    ProgressEvaluation.evaluation_number.desc(),
                )
            )
        )
        seen_snapshots: set[uuid.UUID] = set()
        for item in history:
            if item.snapshot_id in seen_snapshots:
                continue
            seen_snapshots.add(item.snapshot_id)
            if (
                item.reconciliation_status != ProgressReconciliationStatus.RECONCILED
                or abs(Decimal(item.variance_ratio)) < threshold
                or item.direction != direction
            ):
                break
            supporting.append(item.data_date)
    duration_days = max(
        0,
        int((utc_value(snapshot.data_date) - min(utc_value(value) for value in supporting)).days),
    )
    minimum_observations = (
        policy["persistence_min_observations"]
        if isinstance(policy, dict)
        else policy.persistence_min_observations
    )
    minimum_duration = (
        policy["persistence_min_duration_days"]
        if isinstance(policy, dict)
        else policy.persistence_min_duration_days
    )
    persistence = (
        TrendPersistence.PERSISTENT
        if threshold_crossed
        and len(supporting) >= minimum_observations
        and duration_days >= minimum_duration
        else TrendPersistence.TRANSIENT
    )

    planned_productivity = calculate_productivity(planned, prior_planned)
    actual_productivity = calculate_productivity(actual, prior_actual)
    productivity_variance = None
    if planned_productivity is not None and actual_productivity is not None:
        if planned_productivity == 0:
            limitations.append(
                {
                    "code": "ZERO_PLANNED_PRODUCTIVITY",
                    "description": (
                        "Productivity variance is undefined because planned productivity is zero"
                    ),
                }
            )
        else:
            productivity_variance = (
                actual_productivity - planned_productivity
            ) / planned_productivity

    input_measurements = [planned, actual]
    if prior_planned and prior_actual:
        input_measurements.extend([prior_planned, prior_actual])
    evaluation_number = (
        session.scalar(
            select(func.coalesce(func.max(ProgressEvaluation.evaluation_number), 0)).where(
                ProgressEvaluation.case_id == case.id
            )
        )
        + 1
    )
    output_truth = (
        TruthType.CONTRADICTED
        if relevant_contradictions
        or any(value.truth_type == TruthType.CONTRADICTED for value in input_measurements)
        else TruthType.DERIVED_METRIC
    )
    evaluation = ProgressEvaluation(
        id=uuid.uuid4(),
        organization_id=project.organization_id,
        project_id=project.id,
        case_id=case.id,
        snapshot_id=snapshot.id,
        controlled_object_id=actual.controlled_object_id,
        evaluation_number=evaluation_number,
        data_date=snapshot.data_date,
        planned_measurement_id=planned.id,
        actual_measurement_id=actual.id,
        prior_planned_measurement_id=prior_planned.id if prior_planned else None,
        prior_actual_measurement_id=prior_actual.id if prior_actual else None,
        measurement_basis=actual.measurement_basis,
        reconciliation_status=reconciliation,
        reconciled_measurements=reconciled,
        planned_ratio=planned_ratio,
        actual_ratio=actual_ratio,
        variance_ratio=variance,
        variance_magnitude=abs(variance),
        direction=direction,
        duration_days=duration_days,
        threshold_crossed=threshold_crossed,
        persistence=persistence,
        trend_direction=trend,
        supporting_observation_count=len(supporting),
        planned_productivity=planned_productivity,
        actual_productivity=actual_productivity,
        productivity_variance_ratio=productivity_variance,
        input_evidence_ids=[str(value.evidence_item_id) for value in input_measurements],
        input_truth_types=[value.truth_type for value in input_measurements],
        truth_type=output_truth,
        confidence=min(Decimal(value.confidence) for value in input_measurements),
        limitations=limitations,
        policy_version=data.policy_version,
        formula_version=FORMULA_VERSION,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
        evaluated_by=actor.actor_id,
    )
    session.add(evaluation)
    session.flush()
    case.last_progress_evaluation_id = evaluation.id
    case.version += 1
    add_ledger(
        session,
        actor,
        case,
        CaseLedgerEventType.PROGRESS_EVALUATED,
        f"Progress deviation evaluated as {direction}",
        details={
            "progress_evaluation_id": str(evaluation.id),
            "variance_ratio": str(variance),
            "persistence": persistence,
        },
    )
    audit_case(
        session,
        actor,
        case,
        "CASE_PROGRESS_EVALUATED",
        {"progress_evaluation_id": str(evaluation.id)},
    )
    return case, evaluation
