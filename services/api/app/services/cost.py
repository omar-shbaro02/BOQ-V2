from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from app.auth import ActorContext
from app.cost_schemas import CostAssessmentCreate, CostPolicyCreate, CostRecordCreate
from app.generated.taxonomies import (
    AuthorizedContextType,
    CaseLedgerEventType,
    CaseLifecycle,
    CommercialEffectType,
    ContradictionStatus,
    CostAlignmentStatus,
    CostAssessmentStatus,
    CostConclusion,
    CostForecastStatus,
    CostRecordKind,
    SemanticState,
    TruthType,
)
from app.models import (
    AuthorizedContextVersion,
    CaseSnapshot,
    Contradiction,
    ControlledObject,
    CostAnalysisPolicy,
    CostAssessment,
    CostRecord,
    ProgressMeasurement,
    Project,
)
from app.services.audit import record_audit
from app.services.cases import add_ledger, audit_case, require_version, scoped_case
from app.services.evidence import scoped_item
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

DEFAULT_POLICY_VERSION = "COST-DEFAULT-1.0.0"
FORMULA_VERSION = "COST-ALIGNMENT-1.0.0"
DEFAULT_POLICY = {
    "id": None,
    "organization_id": None,
    "project_id": None,
    "policy_version": DEFAULT_POLICY_VERSION,
    "alignment_tolerance": Decimal("0.05"),
    "minimum_earned_ratio_for_forecast": Decimal("0.10"),
    "include_accruals_in_recognized_cost": True,
    "rationale": "Visible MVP default: 5% alignment tolerance and 10% earned threshold",
    "supersedes_policy_id": None,
    "created_by": "SYSTEM",
    "created_at": None,
}
FIELD_ALIASES = {
    CostRecordKind.APPROVED_BUDGET: {"approved_budget"},
    CostRecordKind.AUTHORIZED_CHANGE: {"authorized_change", "authorized_changes"},
    CostRecordKind.COMMITMENT: {"commitment", "commitments", "committed_cost"},
    CostRecordKind.ACTUAL: {"actual", "actuals", "actual_cost"},
    CostRecordKind.ACCRUAL: {"accrual", "accruals", "accrued_cost"},
    CostRecordKind.BOQ_VALUE: {"boq_value"},
    CostRecordKind.EARNED_VALUE: {"earned_value", "value_earned"},
    CostRecordKind.PHYSICAL_VALUE: {"physical_value", "physical_progress_value"},
}
STRONG_TRUTH = {TruthType.VERIFIED_FACT, TruthType.CORROBORATED_FACT}


def utc_value(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def decimal_value(value: Any, label: str) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise HTTPException(status_code=422, detail=f"{label} must be numeric")
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"{label} must be numeric") from exc


def policy_value(policy: dict[str, Any] | CostAnalysisPolicy, name: str) -> Any:
    return policy[name] if isinstance(policy, dict) else getattr(policy, name)


def create_policy(
    session: Session, actor: ActorContext, project: Project, data: CostPolicyCreate
) -> CostAnalysisPolicy:
    if data.policy_version == DEFAULT_POLICY_VERSION:
        raise HTTPException(status_code=409, detail="Default cost policy version is reserved")
    if data.supersedes_policy_id:
        previous = session.get(CostAnalysisPolicy, data.supersedes_policy_id)
        if previous is None or previous.project_id != project.id:
            raise HTTPException(status_code=422, detail="Superseded cost policy not found")
    policy = CostAnalysisPolicy(
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
        action="COST_POLICY_CREATED",
        object_type="COST_ANALYSIS_POLICY",
        object_id=str(policy.id),
        details={"policy_version": policy.policy_version},
    )
    return policy


def list_policies(session: Session, project: Project) -> list[dict[str, Any] | CostAnalysisPolicy]:
    configured = list(
        session.scalars(
            select(CostAnalysisPolicy)
            .where(CostAnalysisPolicy.project_id == project.id)
            .order_by(CostAnalysisPolicy.created_at)
        )
    )
    return [DEFAULT_POLICY, *configured]


def resolve_policy(
    session: Session, project: Project, version: str
) -> dict[str, Any] | CostAnalysisPolicy:
    if version == DEFAULT_POLICY_VERSION:
        return DEFAULT_POLICY
    policy = session.scalar(
        select(CostAnalysisPolicy).where(
            CostAnalysisPolicy.project_id == project.id,
            CostAnalysisPolicy.policy_version == version,
        )
    )
    if policy is None:
        raise HTTPException(status_code=422, detail="Unsupported cost policy version")
    return policy


def budget_projection(context: AuthorizedContextVersion) -> dict[str, Any]:
    payload = context.payload
    approved = Decimal(str(payload["approved_budget"]))
    changes = Decimal(str(payload.get("authorized_changes", "0")))
    return {
        "context_id": context.id,
        "version_number": context.version_number,
        "effective_from": context.effective_from,
        "currency": payload["currency"],
        "approved_budget": approved,
        "authorized_changes": changes,
        "current_authorized_budget": approved + changes,
        "data_date": payload.get("data_date"),
        "reporting_period_start": payload.get("reporting_period_start"),
        "reporting_period_end": payload.get("reporting_period_end"),
        "controlled_object_code": payload.get("controlled_object_code"),
        "measurement_basis": payload.get("measurement_basis", "COST_VALUE"),
    }


def record_cost(
    session: Session,
    actor: ActorContext,
    project: Project,
    data: CostRecordCreate,
) -> CostRecord:
    evidence = scoped_item(session, project, data.evidence_item_id)
    if evidence.controlled_object_id is None:
        raise HTTPException(status_code=422, detail="Cost evidence requires a controlled object")
    if evidence.field_name.lower() not in FIELD_ALIASES[data.record_kind]:
        raise HTTPException(
            status_code=422, detail="Evidence field does not match cost record kind"
        )
    if decimal_value(evidence.value, "Cost evidence value") != data.amount:
        raise HTTPException(status_code=422, detail="Amount must equal the source evidence value")
    if (evidence.unit or "").upper() != data.currency:
        raise HTTPException(status_code=422, detail="Currency differs from source evidence unit")
    if evidence.measurement_basis and evidence.measurement_basis != data.measurement_basis:
        raise HTTPException(
            status_code=422, detail="Measurement basis differs from source evidence"
        )
    if utc_value(evidence.as_of).date() > data.reporting_period_end:
        raise HTTPException(status_code=422, detail="Evidence as-of date is after reporting period")
    context = None
    if data.authorized_context_id:
        context = session.get(AuthorizedContextVersion, data.authorized_context_id)
        expected_type = (
            AuthorizedContextType.BOQ
            if data.record_kind == CostRecordKind.BOQ_VALUE
            else AuthorizedContextType.BUDGET
        )
        if (
            context is None
            or context.project_id != project.id
            or context.context_type != expected_type
            or context.semantic_state
            not in {SemanticState.CURRENT_AUTHORIZED, SemanticState.SUPERSEDED}
            or context.activated_at is None
        ):
            raise HTTPException(
                status_code=422, detail="Cost record requires the matching authorized context"
            )
        if data.record_kind == CostRecordKind.BOQ_VALUE:
            controlled_object = session.get(ControlledObject, evidence.controlled_object_id)
            matching_items = [
                item
                for item in context.payload.get("items", [])
                if item.get("controlled_object_code") in {None, controlled_object.code}
            ]
            currencies = {item["currency"] for item in matching_items}
            expected = sum(
                (
                    Decimal(str(item["quantity"])) * Decimal(str(item["rate"]))
                    for item in matching_items
                ),
                Decimal("0"),
            )
            if not matching_items or len(currencies) != 1:
                raise HTTPException(
                    status_code=422, detail="Authorized BOQ has no unambiguous value for scope"
                )
            if data.amount != expected or data.currency not in currencies:
                raise HTTPException(
                    status_code=422, detail="BOQ value or currency differs from authorized context"
                )
        else:
            projection = budget_projection(context)
            expected = (
                projection["approved_budget"]
                if data.record_kind == CostRecordKind.APPROVED_BUDGET
                else projection["authorized_changes"]
            )
            if data.amount != expected:
                raise HTTPException(
                    status_code=422, detail="Budget amount differs from authorized context"
                )
            if data.currency != projection["currency"]:
                raise HTTPException(status_code=422, detail="Budget currency mismatch")
    existing = session.scalar(select(CostRecord).where(CostRecord.evidence_item_id == evidence.id))
    if existing:
        same = (
            existing.record_kind == data.record_kind
            and existing.amount == data.amount
            and existing.currency == data.currency
            and existing.reporting_period_start == data.reporting_period_start
            and existing.reporting_period_end == data.reporting_period_end
        )
        if not same:
            raise HTTPException(
                status_code=409, detail="Evidence already has another cost normalization"
            )
        return existing
    record = CostRecord(
        id=uuid.uuid4(),
        organization_id=project.organization_id,
        project_id=project.id,
        controlled_object_id=evidence.controlled_object_id,
        evidence_item_id=evidence.id,
        authorized_context_id=context.id if context else None,
        as_of=evidence.as_of,
        semantic_state=evidence.semantic_state,
        truth_type=evidence.truth_type,
        confidence=evidence.confidence,
        recorded_by=actor.actor_id,
        **data.model_dump(exclude={"evidence_item_id", "authorized_context_id"}),
    )
    session.add(record)
    record_audit(
        session,
        actor,
        organization_id=project.organization_id,
        project_id=project.id,
        action="COST_RECORD_NORMALIZED",
        object_type="COST_RECORD",
        object_id=str(record.id),
        details={"record_kind": str(record.record_kind), "evidence_item_id": str(evidence.id)},
    )
    return record


def assessment_digest(data: CostAssessmentCreate) -> str:
    return hashlib.sha256(
        json.dumps(data.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def assess_cost(
    session: Session,
    actor: ActorContext,
    project: Project,
    case_id: uuid.UUID,
    data: CostAssessmentCreate,
    idempotency_key: str,
) -> tuple[Any, CostAssessment]:
    digest = assessment_digest(data)
    existing = session.scalar(
        select(CostAssessment).where(
            CostAssessment.case_id == case_id,
            CostAssessment.idempotency_key == idempotency_key,
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
        raise HTTPException(status_code=422, detail="Cost object is outside the case snapshot")
    controlled_object = session.get(ControlledObject, data.controlled_object_id)
    if controlled_object is None or controlled_object.project_id != project.id:
        raise HTTPException(status_code=404, detail="Controlled object not found")
    budget_ref = next(
        (
            r
            for r in snapshot.authorized_context_refs
            if r["context_type"] == AuthorizedContextType.BUDGET
        ),
        None,
    )
    if budget_ref is None:
        raise HTTPException(status_code=422, detail="Snapshot has no effective authorized budget")
    budget_context = session.get(AuthorizedContextVersion, uuid.UUID(budget_ref["id"]))
    if budget_context is None or budget_context.project_id != project.id:
        raise HTTPException(status_code=422, detail="Snapshot budget context is unavailable")
    budget = budget_projection(budget_context)
    if budget["controlled_object_code"] not in {None, controlled_object.code}:
        raise HTTPException(status_code=422, detail="Authorized budget belongs to another scope")
    policy = resolve_policy(session, project, data.policy_version)
    records = list(
        session.scalars(
            select(CostRecord).where(CostRecord.id.in_(list(dict.fromkeys(data.cost_record_ids))))
        )
    )
    if len(records) != len(set(data.cost_record_ids)) or any(
        r.project_id != project.id for r in records
    ):
        raise HTTPException(status_code=404, detail="One or more cost records were not found")
    if any(r.controlled_object_id != controlled_object.id for r in records):
        raise HTTPException(status_code=422, detail="Cost records span incompatible scopes")
    if any(str(r.evidence_item_id) not in snapshot.evidence_item_ids for r in records):
        raise HTTPException(status_code=422, detail="Cost evidence is not frozen in snapshot")
    currencies = {r.currency for r in records} | {budget["currency"]}
    bases = {r.measurement_basis for r in records} | {budget["measurement_basis"]}
    periods = {(r.reporting_period_start, r.reporting_period_end) for r in records}
    if len(currencies) != 1:
        raise HTTPException(status_code=422, detail="Cost records use incompatible currencies")
    if len(bases) != 1:
        raise HTTPException(
            status_code=422, detail="Cost records use incompatible measurement bases"
        )
    if len(periods) != 1:
        raise HTTPException(
            status_code=422, detail="Cost records use incompatible reporting periods"
        )
    period_start, period_end = next(iter(periods))
    if any(utc_value(r.as_of) > utc_value(snapshot.data_date) for r in records):
        raise HTTPException(
            status_code=422, detail="Cost evidence is later than snapshot data date"
        )
    for r in records:
        if (
            r.record_kind in {CostRecordKind.APPROVED_BUDGET, CostRecordKind.AUTHORIZED_CHANGE}
            and r.authorized_context_id != budget_context.id
        ):
            raise HTTPException(
                status_code=422, detail="Budget record differs from snapshot authorization"
            )

    def total(kind: CostRecordKind) -> Decimal:
        return sum((r.amount for r in records if r.record_kind == kind), Decimal("0"))

    commitments = total(CostRecordKind.COMMITMENT)
    actuals = total(CostRecordKind.ACTUAL)
    accruals = total(CostRecordKind.ACCRUAL)
    earned = total(CostRecordKind.EARNED_VALUE)
    physical_value = total(CostRecordKind.PHYSICAL_VALUE)
    recognized = actuals + (
        accruals if policy_value(policy, "include_accruals_in_recognized_cost") else Decimal("0")
    )
    authorized_budget = budget["current_authorized_budget"]
    limitations: list[dict[str, Any]] = []
    if authorized_budget <= 0:
        limitations.append(
            {
                "code": "ZERO_AUTHORIZED_BUDGET",
                "description": "Cost ratios require a positive current authorized budget",
            }
        )
    progress_ratio = data.physical_progress_ratio
    progress_evidence_id: uuid.UUID | None = None
    if data.progress_measurement_id:
        progress = session.get(ProgressMeasurement, data.progress_measurement_id)
        if progress is None or progress.project_id != project.id:
            raise HTTPException(status_code=404, detail="Progress measurement not found")
        if progress.controlled_object_id != controlled_object.id:
            raise HTTPException(status_code=422, detail="Progress and cost scopes differ")
        if str(progress.evidence_item_id) not in snapshot.evidence_item_ids:
            raise HTTPException(
                status_code=422, detail="Progress evidence is not frozen in snapshot"
            )
        if utc_value(progress.as_of) > utc_value(snapshot.data_date) or not (
            period_start <= progress.as_of.date() <= period_end
        ):
            raise HTTPException(
                status_code=422, detail="Progress and cost reporting periods differ"
            )
        progress_ratio = progress.completion_ratio
        progress_evidence_id = progress.evidence_item_id
    elif progress_ratio is not None:
        limitations.append(
            {
                "code": "UNSUPPORTED_PHYSICAL_RATIO",
                "description": "Explicit physical ratio has no immutable evidence lineage",
            }
        )
    selected_progress_bases = sum((earned > 0, physical_value > 0, progress_ratio is not None))
    if selected_progress_bases > 1:
        raise HTTPException(
            status_code=422,
            detail="Earned, physical-value, and progress measurement bases cannot be combined",
        )
    progress_value_ratio = None
    if authorized_budget > 0:
        if earned > 0:
            progress_value_ratio = earned / authorized_budget
        elif physical_value > 0:
            progress_value_ratio = physical_value / authorized_budget
        elif progress_ratio is not None:
            progress_value_ratio = progress_ratio
    cost_ratio = recognized / authorized_budget if authorized_budget > 0 else None
    variance = (
        cost_ratio - progress_value_ratio
        if cost_ratio is not None and progress_value_ratio is not None
        else None
    )
    tolerance = Decimal(str(policy_value(policy, "alignment_tolerance")))
    if variance is None:
        alignment = CostAlignmentStatus.NOT_COMPARABLE
        limitations.append(
            {
                "code": "MISSING_PROGRESS_VALUE_BASIS",
                "description": (
                    "No compatible earned, physical-value, or progress basis is available"
                ),
            }
        )
    elif abs(variance) <= tolerance:
        alignment = CostAlignmentStatus.ALIGNED
    elif variance > 0:
        alignment = CostAlignmentStatus.COST_AHEAD
    else:
        alignment = CostAlignmentStatus.COST_BEHIND
    effects = [
        {
            "type": r.commercial_effect,
            "amount": str(r.amount),
            "record_id": str(r.id),
            "explanation": r.effect_explanation,
            "boundary": "Operational explanation only; no contractual liability is asserted.",
        }
        for r in records
        if r.commercial_effect != CommercialEffectType.NONE
    ]
    recognized_effect_kinds = {CostRecordKind.ACTUAL}
    if policy_value(policy, "include_accruals_in_recognized_cost"):
        recognized_effect_kinds.add(CostRecordKind.ACCRUAL)
    explained_ratio = (
        sum(
            (
                r.amount
                for r in records
                if r.commercial_effect != CommercialEffectType.NONE
                and r.record_kind in recognized_effect_kinds
            ),
            Decimal("0"),
        )
        / authorized_budget
        if authorized_budget > 0
        else Decimal("0")
    )
    unexplained = (
        max(Decimal("0"), abs(variance) - explained_ratio) if variance is not None else None
    )

    critical_records = [
        r
        for r in records
        if r.record_kind
        in {
            CostRecordKind.ACTUAL,
            CostRecordKind.ACCRUAL,
            CostRecordKind.EARNED_VALUE,
            CostRecordKind.PHYSICAL_VALUE,
        }
    ]
    weak = [r for r in critical_records if r.truth_type not in STRONG_TRUTH]
    contradiction_ids = [uuid.UUID(value) for value in snapshot.contradiction_ids]
    conflicting = set(
        session.scalars(
            select(Contradiction.left_item_id).where(
                Contradiction.id.in_(contradiction_ids),
                Contradiction.status == ContradictionStatus.OPEN,
            )
        )
    ) | set(
        session.scalars(
            select(Contradiction.right_item_id).where(
                Contradiction.id.in_(contradiction_ids),
                Contradiction.status == ContradictionStatus.OPEN,
            )
        )
    )
    selected_evidence = {r.evidence_item_id for r in records}
    contradicted = bool(conflicting & selected_evidence)
    if weak:
        limitations.append(
            {
                "code": "WEAK_COST_EVIDENCE",
                "description": (
                    "Decision-critical cost/value evidence is not verified or corroborated"
                ),
            }
        )
    if contradicted:
        limitations.append(
            {
                "code": "UNRESOLVED_COST_CONTRADICTION",
                "description": "Selected cost evidence participates in an unresolved contradiction",
            }
        )

    earned_ratio = earned / authorized_budget if authorized_budget > 0 else Decimal("0")
    forecast_supported = (
        earned > 0
        and earned_ratio >= Decimal(str(policy_value(policy, "minimum_earned_ratio_for_forecast")))
        and recognized > 0
        and not weak
        and not contradicted
        and not effects
    )
    if forecast_supported:
        eac = recognized / earned_ratio
        ftc = max(Decimal("0"), eac - recognized)
        forecast_status = CostForecastStatus.CALCULATED
    else:
        eac = ftc = None
        forecast_status = CostForecastStatus.NOT_SUPPORTED
        limitations.append(
            {
                "code": "FORECAST_INPUTS_UNSUPPORTED",
                "description": (
                    "EAC needs sufficient verified recognized cost and earned value without "
                    "unadjusted commercial timing effects"
                ),
            }
        )

    if contradicted or weak or data.physical_progress_ratio is not None:
        status = CostAssessmentStatus.VERIFICATION_REQUIRED
        alignment = CostAlignmentStatus.VERIFICATION_REQUIRED
    elif variance is None:
        status = CostAssessmentStatus.INSUFFICIENT
    else:
        status = CostAssessmentStatus.ASSESSED
    conclusion = CostConclusion.COST_ONLY_VARIANCE
    if (
        status == CostAssessmentStatus.ASSESSED
        and variance is not None
        and abs(variance) > tolerance
        and unexplained is not None
        and unexplained <= tolerance
        and effects
    ):
        conclusion = CostConclusion.EXPLAINED_DIVERGENCE
    if (
        status == CostAssessmentStatus.ASSESSED
        and eac is not None
        and authorized_budget > 0
        and (eac - authorized_budget) / authorized_budget > tolerance
    ):
        conclusion = CostConclusion.FORECAST_EXPOSURE
    confidence = min((r.confidence for r in critical_records), default=Decimal("0"))
    truth = TruthType.CONTRADICTED if contradicted else TruthType.DERIVED_METRIC
    assessment_number = (
        session.scalar(
            select(func.max(CostAssessment.assessment_number)).where(
                CostAssessment.case_id == case.id
            )
        )
        or 0
    ) + 1
    input_evidence = [str(r.evidence_item_id) for r in records]
    if progress_evidence_id:
        input_evidence.append(str(progress_evidence_id))
    assessment = CostAssessment(
        id=uuid.uuid4(),
        organization_id=project.organization_id,
        project_id=project.id,
        case_id=case.id,
        snapshot_id=snapshot.id,
        budget_context_id=budget_context.id,
        controlled_object_id=controlled_object.id,
        assessment_number=assessment_number,
        data_date=snapshot.data_date,
        reporting_period_start=period_start,
        reporting_period_end=period_end,
        currency=budget["currency"],
        measurement_basis=budget["measurement_basis"],
        approved_budget=budget["approved_budget"],
        authorized_changes=budget["authorized_changes"],
        current_authorized_budget=authorized_budget,
        commitments=commitments,
        actuals=actuals,
        accruals=accruals,
        recognized_cost=recognized,
        earned_value=earned or None,
        physical_progress_ratio=progress_ratio,
        cost_consumption_ratio=cost_ratio,
        progress_value_ratio=progress_value_ratio,
        alignment_variance_ratio=variance,
        alignment_status=alignment,
        explained_effects=effects,
        unexplained_variance_ratio=unexplained,
        forecast_status=forecast_status,
        forecast_to_complete=ftc,
        estimate_at_completion=eac,
        assessment_status=status,
        maximum_supported_conclusion=conclusion,
        input_cost_record_ids=[str(r.id) for r in records],
        input_evidence_ids=input_evidence,
        truth_type=truth,
        confidence=confidence,
        limitations=limitations,
        policy_version=data.policy_version,
        formula_version=FORMULA_VERSION,
        idempotency_key=idempotency_key,
        request_hash=digest,
        assessed_by=actor.actor_id,
    )
    session.add(assessment)
    session.flush()
    case.last_cost_assessment_id = assessment.id
    case.version += 1
    add_ledger(
        session,
        actor,
        case,
        CaseLedgerEventType.COST_ASSESSED,
        "Cost and commercial assessment completed",
        details={
            "assessment_id": str(assessment.id),
            "alignment_status": str(alignment),
            "maximum_supported_conclusion": str(conclusion),
        },
    )
    audit_case(session, actor, case, "COST_ASSESSED", {"assessment_id": str(assessment.id)})
    return case, assessment
