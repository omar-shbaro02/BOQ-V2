from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from app.auth import ActorContext
from app.case_schemas import (
    ActiveResponseCreate,
    AttachEvidenceCreate,
    BaselineAssessmentCreate,
    CaseBlockCreate,
    CaseCloseCreate,
    CaseReopenCreate,
    CaseResumeCreate,
    LifecycleTransitionCreate,
    SnapshotCreate,
    SufficiencyAssessCreate,
)
from app.evidence_schemas import EvidenceRequestCreate
from app.generated.taxonomies import (
    ActiveResponseStatus,
    AuthorizedContextType,
    BaselineValidity,
    CaseLedgerEventType,
    CaseLifecycle,
    ConclusionType,
    DecisionReadiness,
    EvidenceItemStatus,
    GovernanceState,
    LimitationCode,
    LimitationStatus,
    SemanticState,
    TruthType,
    UrgencyLevel,
)
from app.models import (
    AuthorizedContextVersion,
    CaseActiveResponse,
    CaseBaselineAssessment,
    CaseEvidenceAttachment,
    CaseLedgerEvent,
    CaseLimitation,
    CaseSnapshot,
    CaseSufficiencyAssessment,
    Contradiction,
    DecisionCaseControlledObject,
    DecisionCaseShell,
    DecisionCaseSignal,
    EvidenceItem,
    EvidenceRequest,
    Project,
    ResponseExecutionObservation,
    ResponseOutcome,
)
from app.services.audit import record_audit
from app.services.events import publish_domain_event
from app.services.evidence import create_evidence_request, scoped_item
from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

POLICY_VERSION = "PHASE4-SUFFICIENCY-1.0.0"
SUFFICIENCY_POLICIES: dict[ConclusionType, dict[str, Any]] = {
    ConclusionType.VERIFY_EVIDENCE: {
        "field_groups": [],
        "contexts": [],
        "strong_truth": False,
    },
    ConclusionType.MONITOR_CONDITION: {
        "field_groups": [],
        "contexts": [],
        "strong_truth": False,
    },
    ConclusionType.PROGRESS_INTERVENTION: {
        "field_groups": [["progress_variance", "progress_variance_pct", "progress_variance_ratio"]],
        "contexts": [AuthorizedContextType.SCHEDULE],
        "strong_truth": True,
    },
    ConclusionType.SCHEDULE_INTERVENTION: {
        "field_groups": [["schedule_variance_days", "delay_days"]],
        "contexts": [AuthorizedContextType.SCHEDULE],
        "strong_truth": True,
    },
    ConclusionType.COST_INTERVENTION: {
        "field_groups": [["cost_variance_pct", "cost_variance_ratio", "cost_overrun_pct"]],
        "contexts": [AuthorizedContextType.BUDGET],
        "strong_truth": True,
    },
}

FORWARD_TRANSITIONS = {
    CaseLifecycle.OPEN: {CaseLifecycle.EVIDENCE_ASSEMBLY},
    CaseLifecycle.REOPENED: {CaseLifecycle.EVIDENCE_ASSEMBLY},
    CaseLifecycle.EVIDENCE_ASSEMBLY: {CaseLifecycle.ANALYSIS},
    CaseLifecycle.ANALYSIS: {CaseLifecycle.REVIEW},
    CaseLifecycle.REVIEW: {CaseLifecycle.DECISION_READY},
}


def scoped_case(
    session: Session,
    project: Project,
    case_id: uuid.UUID,
    *,
    for_update: bool = False,
) -> DecisionCaseShell:
    query = select(DecisionCaseShell).where(DecisionCaseShell.id == case_id)
    if for_update:
        query = query.with_for_update()
    case = session.scalar(query)
    if case is None or case.project_id != project.id:
        raise HTTPException(status_code=404, detail="Decision case not found")
    return case


def require_version(case: DecisionCaseShell, expected: int) -> None:
    if case.version != expected:
        raise HTTPException(status_code=409, detail="Decision case version is stale")


def add_ledger(
    session: Session,
    actor: ActorContext,
    case: DecisionCaseShell,
    event_type: CaseLedgerEventType,
    reason: str,
    *,
    from_lifecycle: str | None = None,
    to_lifecycle: str | None = None,
    details: dict[str, Any] | None = None,
) -> CaseLedgerEvent:
    event = CaseLedgerEvent(
        id=uuid.uuid4(),
        organization_id=case.organization_id,
        project_id=case.project_id,
        case_id=case.id,
        case_version=case.version,
        event_type=event_type,
        from_lifecycle=from_lifecycle,
        to_lifecycle=to_lifecycle,
        actor_id=actor.actor_id,
        reason=reason,
        details=details or {},
    )
    session.add(event)
    return event


def audit_case(
    session: Session,
    actor: ActorContext,
    case: DecisionCaseShell,
    action: str,
    details: dict[str, Any] | None = None,
) -> None:
    record_audit(
        session,
        actor,
        organization_id=case.organization_id,
        project_id=case.project_id,
        action=action,
        object_type="DECISION_CASE",
        object_id=str(case.id),
        object_version=case.version,
        details=details,
    )


def attach_evidence(
    session: Session,
    actor: ActorContext,
    project: Project,
    case_id: uuid.UUID,
    data: AttachEvidenceCreate,
) -> tuple[DecisionCaseShell, list[uuid.UUID]]:
    case = scoped_case(session, project, case_id, for_update=True)
    require_version(case, data.expected_version)
    if case.lifecycle == CaseLifecycle.CLOSED:
        raise HTTPException(
            status_code=409, detail="Closed case must be reopened before attachment"
        )
    attached: list[uuid.UUID] = []
    for item_id in dict.fromkeys(data.evidence_item_ids):
        item = scoped_item(session, project, item_id)
        if item.status != EvidenceItemStatus.ACTIVE:
            raise HTTPException(status_code=422, detail="Only active evidence can be attached")
        if session.get(CaseEvidenceAttachment, (case.id, item.id)) is None:
            session.add(
                CaseEvidenceAttachment(
                    case_id=case.id,
                    evidence_item_id=item.id,
                    attachment_reason=data.attachment_reason,
                    attached_by=actor.actor_id,
                )
            )
            attached.append(item.id)
    if attached:
        case.version += 1
        add_ledger(
            session,
            actor,
            case,
            CaseLedgerEventType.EVIDENCE_ATTACHED,
            data.attachment_reason,
            details={"evidence_item_ids": [str(value) for value in attached]},
        )
        audit_case(session, actor, case, "CASE_EVIDENCE_ATTACHED")
    return case, attached


def record_active_response(
    session: Session,
    actor: ActorContext,
    project: Project,
    case_id: uuid.UUID,
    data: ActiveResponseCreate,
) -> tuple[DecisionCaseShell, CaseActiveResponse]:
    case = scoped_case(session, project, case_id, for_update=True)
    require_version(case, data.expected_version)
    if case.lifecycle == CaseLifecycle.CLOSED:
        raise HTTPException(status_code=409, detail="Cannot link response to closed case")
    response = CaseActiveResponse(
        id=uuid.uuid4(),
        organization_id=project.organization_id,
        project_id=project.id,
        case_id=case.id,
        recorded_by=actor.actor_id,
        **data.model_dump(exclude={"expected_version"}),
    )
    session.add(response)
    case.version += 1
    add_ledger(
        session,
        actor,
        case,
        CaseLedgerEventType.RESPONSE_LINKED,
        "Authorized response reference linked",
        details={
            "response_id": str(response.id),
            "authorization_reference": response.authorization_reference,
        },
    )
    audit_case(session, actor, case, "CASE_ACTIVE_RESPONSE_LINKED")
    return case, response


def snapshot_request_hash(data: SnapshotCreate) -> str:
    return hashlib.sha256(data.model_dump_json(exclude={"expected_version"}).encode()).hexdigest()


def effective_contexts(
    session: Session, project: Project, data_date: datetime
) -> list[AuthorizedContextVersion]:
    candidates = list(
        session.scalars(
            select(AuthorizedContextVersion)
            .where(
                AuthorizedContextVersion.project_id == project.id,
                AuthorizedContextVersion.semantic_state.in_(
                    [SemanticState.CURRENT_AUTHORIZED, SemanticState.SUPERSEDED]
                ),
                AuthorizedContextVersion.activated_at <= data_date,
                or_(
                    AuthorizedContextVersion.superseded_at.is_(None),
                    AuthorizedContextVersion.superseded_at > data_date,
                ),
            )
            .order_by(
                AuthorizedContextVersion.context_type,
                AuthorizedContextVersion.activated_at.desc(),
            )
        )
    )
    selected: dict[str, AuthorizedContextVersion] = {}
    for context in candidates:
        selected.setdefault(context.context_type, context)
    return list(selected.values())


def create_snapshot(
    session: Session,
    actor: ActorContext,
    project: Project,
    case_id: uuid.UUID,
    data: SnapshotCreate,
    idempotency_key: str,
) -> tuple[DecisionCaseShell, CaseSnapshot]:
    case = scoped_case(session, project, case_id, for_update=True)
    digest = snapshot_request_hash(data)
    existing = session.scalar(
        select(CaseSnapshot).where(
            CaseSnapshot.case_id == case.id,
            CaseSnapshot.idempotency_key == idempotency_key,
        )
    )
    if existing:
        if existing.request_hash != digest:
            raise HTTPException(status_code=409, detail="Idempotency key payload mismatch")
        return case, existing
    require_version(case, data.expected_version)
    if data.policy_version != POLICY_VERSION:
        raise HTTPException(status_code=422, detail="Unsupported sufficiency policy version")
    if case.lifecycle == CaseLifecycle.CLOSED:
        raise HTTPException(status_code=409, detail="Cannot snapshot a closed case")

    object_ids = list(
        session.scalars(
            select(DecisionCaseControlledObject.controlled_object_id).where(
                DecisionCaseControlledObject.case_id == case.id
            )
        )
    )
    signal_ids = list(
        session.scalars(
            select(DecisionCaseSignal.signal_id).where(DecisionCaseSignal.case_id == case.id)
        )
    )
    evidence_ids = list(
        session.scalars(
            select(CaseEvidenceAttachment.evidence_item_id)
            .join(
                EvidenceItem,
                EvidenceItem.id == CaseEvidenceAttachment.evidence_item_id,
            )
            .where(
                CaseEvidenceAttachment.case_id == case.id,
                EvidenceItem.as_of <= data.data_date,
            )
        )
    )
    contradiction_ids: list[uuid.UUID] = []
    if evidence_ids:
        contradiction_ids = list(
            session.scalars(
                select(Contradiction.id).where(
                    Contradiction.project_id == project.id,
                    Contradiction.created_at <= data.data_date,
                    or_(
                        Contradiction.left_item_id.in_(evidence_ids),
                        Contradiction.right_item_id.in_(evidence_ids),
                    ),
                )
            )
        )
    contexts = effective_contexts(session, project, data.data_date)
    context_refs = [
        {
            "id": str(context.id),
            "context_type": context.context_type,
            "version_number": context.version_number,
            "effective_from": context.effective_from.isoformat(),
        }
        for context in contexts
    ]
    schedule_present = any(
        context.context_type == AuthorizedContextType.SCHEDULE for context in contexts
    )
    active_responses = list(
        session.scalars(
            select(CaseActiveResponse).where(
                CaseActiveResponse.case_id == case.id,
                CaseActiveResponse.status == ActiveResponseStatus.ACTIVE,
                CaseActiveResponse.effective_from <= data.data_date,
                or_(
                    CaseActiveResponse.effective_until.is_(None),
                    CaseActiveResponse.effective_until >= data.data_date,
                ),
            )
        )
    )
    payload = {
        "case_id": str(case.id),
        "case_version": case.version,
        "data_date": data.data_date.isoformat(),
        "controlled_object_ids": sorted(str(value) for value in object_ids),
        "signal_ids": sorted(str(value) for value in signal_ids),
        "evidence_item_ids": sorted(str(value) for value in evidence_ids),
        "contradiction_ids": sorted(str(value) for value in contradiction_ids),
        "authorized_context_refs": sorted(context_refs, key=lambda value: value["context_type"]),
        "active_response_ids": sorted(str(value.id) for value in active_responses),
        "policy_version": data.policy_version,
    }
    snapshot_number = (
        session.scalar(
            select(func.max(CaseSnapshot.snapshot_number)).where(CaseSnapshot.case_id == case.id)
        )
        or 0
    ) + 1
    snapshot = CaseSnapshot(
        id=uuid.uuid4(),
        organization_id=project.organization_id,
        project_id=project.id,
        case_id=case.id,
        snapshot_number=snapshot_number,
        case_version=case.version,
        data_date=data.data_date,
        baseline_validity=(
            BaselineValidity.VALID if schedule_present else BaselineValidity.MISSING
        ),
        snapshot_hash=hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        idempotency_key=idempotency_key,
        request_hash=digest,
        created_by=actor.actor_id,
        **{
            key: value
            for key, value in payload.items()
            if key not in {"case_id", "case_version", "data_date"}
        },
    )
    session.add(snapshot)
    session.flush()
    case.last_snapshot_id = snapshot.id
    case.version += 1
    add_ledger(
        session,
        actor,
        case,
        CaseLedgerEventType.SNAPSHOT_CREATED,
        "Immutable case snapshot created",
        details={"snapshot_id": str(snapshot.id), "snapshot_hash": snapshot.snapshot_hash},
    )
    audit_case(session, actor, case, "CASE_SNAPSHOT_CREATED")
    return case, snapshot


def assess_baseline(
    session: Session,
    actor: ActorContext,
    project: Project,
    case_id: uuid.UUID,
    data: BaselineAssessmentCreate,
) -> tuple[DecisionCaseShell, CaseBaselineAssessment]:
    case = scoped_case(session, project, case_id, for_update=True)
    require_version(case, data.expected_version)
    if case.lifecycle == CaseLifecycle.CLOSED:
        raise HTTPException(
            status_code=409, detail="Closed case must be reopened before assessment"
        )
    snapshot = session.get(CaseSnapshot, data.snapshot_id)
    if snapshot is None or snapshot.case_id != case.id:
        raise HTTPException(status_code=404, detail="Case snapshot not found")
    if data.authorized_context_id:
        context = session.get(AuthorizedContextVersion, data.authorized_context_id)
        if context is None or context.project_id != project.id:
            raise HTTPException(
                status_code=422, detail="Authorized context does not belong to project"
            )
    assessment = CaseBaselineAssessment(
        id=uuid.uuid4(),
        organization_id=project.organization_id,
        project_id=project.id,
        case_id=case.id,
        assessed_by=actor.actor_id,
        **data.model_dump(exclude={"expected_version"}),
    )
    session.add(assessment)
    case.version += 1
    add_ledger(
        session,
        actor,
        case,
        CaseLedgerEventType.BASELINE_CHALLENGED,
        data.rationale,
        details={"snapshot_id": str(snapshot.id), "validity": data.validity},
    )
    audit_case(session, actor, case, "CASE_BASELINE_ASSESSED")
    return case, assessment


def add_limitation(
    session: Session,
    project: Project,
    case: DecisionCaseShell,
    snapshot: CaseSnapshot,
    *,
    code: LimitationCode,
    description: str,
    material: bool,
    owner: str,
    due_at: datetime,
) -> CaseLimitation:
    limitation = CaseLimitation(
        id=uuid.uuid4(),
        organization_id=project.organization_id,
        project_id=project.id,
        case_id=case.id,
        snapshot_id=snapshot.id,
        code=code,
        description=description,
        material=material,
        owner_actor_id=owner,
        due_at=due_at,
        status=LimitationStatus.OPEN,
    )
    session.add(limitation)
    return limitation


def assess_sufficiency(
    session: Session,
    actor: ActorContext,
    project: Project,
    case_id: uuid.UUID,
    data: SufficiencyAssessCreate,
) -> tuple[
    DecisionCaseShell,
    CaseSufficiencyAssessment,
    list[CaseLimitation],
    list[EvidenceRequest],
]:
    case = scoped_case(session, project, case_id, for_update=True)
    require_version(case, data.expected_version)
    if case.lifecycle == CaseLifecycle.CLOSED:
        raise HTTPException(
            status_code=409, detail="Closed case must be reopened before assessment"
        )
    snapshot = session.get(CaseSnapshot, data.snapshot_id)
    if snapshot is None or snapshot.case_id != case.id:
        raise HTTPException(status_code=404, detail="Case snapshot not found")
    existing = session.scalar(
        select(CaseSufficiencyAssessment).where(
            CaseSufficiencyAssessment.snapshot_id == snapshot.id,
            CaseSufficiencyAssessment.conclusion_type == data.conclusion_type,
        )
    )
    if existing:
        raise HTTPException(status_code=409, detail="Snapshot conclusion already assessed")
    if data.gap_due_at <= datetime.now(UTC):
        raise HTTPException(status_code=422, detail="Gap due date must be in the future")

    policy = SUFFICIENCY_POLICIES[data.conclusion_type]
    evidence_ids = [uuid.UUID(value) for value in snapshot.evidence_item_ids]
    evidence = list(session.scalars(select(EvidenceItem).where(EvidenceItem.id.in_(evidence_ids))))
    by_field = {item.field_name.lower(): item for item in evidence}
    missing: list[dict[str, Any]] = []
    present: list[dict[str, Any]] = []
    matched_required: list[EvidenceItem] = []
    for group in policy["field_groups"]:
        matches = [by_field[field] for field in group if field in by_field]
        if not matches:
            missing.append({"acceptable_fields": group, "reason": "required field absent"})
        else:
            item = matches[0]
            matched_required.append(item)
            present.append({"field_name": item.field_name, "evidence_item_id": str(item.id)})
    if not policy["field_groups"] and evidence:
        present.extend(
            {"field_name": item.field_name, "evidence_item_id": str(item.id)} for item in evidence
        )
    if data.conclusion_type == ConclusionType.MONITOR_CONDITION and not evidence:
        missing.append({"acceptable_fields": ["any_relevant_evidence"], "reason": "no evidence"})
    if (
        data.conclusion_type == ConclusionType.VERIFY_EVIDENCE
        and not evidence
        and not snapshot.contradiction_ids
    ):
        missing.append(
            {"acceptable_fields": ["verification_evidence"], "reason": "no evidence to verify"}
        )

    available_contexts = {value["context_type"] for value in snapshot.authorized_context_refs}
    missing_contexts = [
        context for context in policy["contexts"] if context not in available_contexts
    ]
    baseline = session.scalar(
        select(CaseBaselineAssessment)
        .where(CaseBaselineAssessment.snapshot_id == snapshot.id)
        .order_by(CaseBaselineAssessment.assessed_at.desc())
    )
    baseline_validity = baseline.validity if baseline else snapshot.baseline_validity
    stale = [str(item.id) for item in evidence if item.is_stale]
    strong_truth = {TruthType.VERIFIED_FACT, TruthType.CORROBORATED_FACT}
    weak = [
        str(item.id)
        for item in matched_required
        if policy["strong_truth"] and item.truth_type not in strong_truth
    ]
    contradictions = list(
        session.scalars(
            select(Contradiction).where(
                Contradiction.id.in_([uuid.UUID(value) for value in snapshot.contradiction_ids]),
                Contradiction.status == "OPEN",
            )
        )
    )
    contradiction_data = [
        {
            "contradiction_id": str(value.id),
            "field_name": value.field_name,
            "material": value.material,
        }
        for value in contradictions
    ]

    limitations: list[CaseLimitation] = []
    for gap in missing:
        limitations.append(
            add_limitation(
                session,
                project,
                case,
                snapshot,
                code=LimitationCode.MISSING_REQUIRED_FIELD,
                description=f"Missing required evidence: {gap['acceptable_fields']}",
                material=True,
                owner=data.gap_owner_actor_id,
                due_at=data.gap_due_at,
            )
        )
    for context in missing_contexts:
        limitations.append(
            add_limitation(
                session,
                project,
                case,
                snapshot,
                code=LimitationCode.MISSING_AUTHORIZED_CONTEXT,
                description=f"Missing effective authorized {context} context",
                material=True,
                owner=data.gap_owner_actor_id,
                due_at=data.gap_due_at,
            )
        )
    for item_id in stale:
        limitations.append(
            add_limitation(
                session,
                project,
                case,
                snapshot,
                code=LimitationCode.STALE_EVIDENCE,
                description=f"Evidence {item_id} expired before assessment",
                material=True,
                owner=data.gap_owner_actor_id,
                due_at=data.gap_due_at,
            )
        )
    for item_id in weak:
        limitations.append(
            add_limitation(
                session,
                project,
                case,
                snapshot,
                code=LimitationCode.WEAK_TRUTH_SUPPORT,
                description=f"Decision-critical evidence {item_id} is not verified/corroborated",
                material=True,
                owner=data.gap_owner_actor_id,
                due_at=data.gap_due_at,
            )
        )
    for contradiction in contradictions:
        limitations.append(
            add_limitation(
                session,
                project,
                case,
                snapshot,
                code=LimitationCode.UNRESOLVED_CONTRADICTION,
                description=f"Unresolved contradiction {contradiction.id}",
                material=contradiction.material,
                owner=data.gap_owner_actor_id,
                due_at=data.gap_due_at,
            )
        )
    invalid_baseline = baseline_validity != BaselineValidity.VALID
    if invalid_baseline and policy["contexts"]:
        limitations.append(
            add_limitation(
                session,
                project,
                case,
                snapshot,
                code=LimitationCode.INVALID_BASELINE,
                description=f"Baseline validity is {baseline_validity}",
                material=True,
                owner=data.gap_owner_actor_id,
                due_at=data.gap_due_at,
            )
        )
    if snapshot.active_response_ids:
        limitations.append(
            add_limitation(
                session,
                project,
                case,
                snapshot,
                code=LimitationCode.ACTIVE_RESPONSE_UNASSESSED,
                description=(
                    "An active authorized response exists and its effect is not yet assessed"
                ),
                material=False,
                owner=case.owner_actor_id,
                due_at=data.gap_due_at,
            )
        )

    hard_missing = bool(
        missing
        or missing_contexts
        or (policy["contexts"] and baseline_validity == BaselineValidity.MISSING)
    )
    verification_needed = bool(
        stale
        or weak
        or any(item.material for item in contradictions)
        or (
            policy["contexts"]
            and baseline_validity in {BaselineValidity.STALE, BaselineValidity.DISPUTED}
        )
    )
    if hard_missing:
        readiness = DecisionReadiness.INSUFFICIENT
    elif verification_needed:
        readiness = DecisionReadiness.VERIFICATION_REQUIRED
    elif limitations:
        readiness = DecisionReadiness.DECISION_READY_WITH_LIMITATIONS
    else:
        readiness = DecisionReadiness.DECISION_READY
    max_conclusion = (
        data.conclusion_type
        if readiness
        in {DecisionReadiness.DECISION_READY, DecisionReadiness.DECISION_READY_WITH_LIMITATIONS}
        else ConclusionType.VERIFY_EVIDENCE
    )
    requests: list[EvidenceRequest] = []
    if readiness in {DecisionReadiness.INSUFFICIENT, DecisionReadiness.VERIFICATION_REQUIRED}:
        fields = sorted(
            {
                field
                for gap in missing
                for field in gap["acceptable_fields"]
                if field != "any_relevant_evidence"
            }
        ) or ["verification_evidence"]
        request = create_evidence_request(
            session,
            actor,
            project,
            EvidenceRequestCreate(
                controlled_object_id=(
                    uuid.UUID(snapshot.controlled_object_ids[0])
                    if snapshot.controlled_object_ids
                    else None
                ),
                requested_fields=fields,
                reason=f"Close {readiness} gaps for case {case.case_number}",
                urgency=UrgencyLevel.ELEVATED,
                owner_actor_id=data.gap_owner_actor_id,
                due_at=data.gap_due_at,
            ),
        )
        requests.append(request)
    assessment = CaseSufficiencyAssessment(
        id=uuid.uuid4(),
        organization_id=project.organization_id,
        project_id=project.id,
        case_id=case.id,
        snapshot_id=snapshot.id,
        conclusion_type=data.conclusion_type,
        readiness=readiness,
        present_evidence=present,
        missing_evidence=missing,
        stale_evidence_ids=stale,
        weak_evidence_ids=weak,
        contradictory_evidence=contradiction_data,
        limitation_ids=[str(value.id) for value in limitations],
        evidence_request_ids=[str(value.id) for value in requests],
        maximum_supported_conclusion=max_conclusion,
        policy_version=snapshot.policy_version,
        assessed_by=actor.actor_id,
    )
    session.add(assessment)
    case.readiness = readiness
    case.governance_state = (
        GovernanceState.VERIFICATION_REQUIRED
        if readiness in {DecisionReadiness.INSUFFICIENT, DecisionReadiness.VERIFICATION_REQUIRED}
        else GovernanceState.HUMAN_REVIEW_REQUIRED
    )
    case.version += 1
    add_ledger(
        session,
        actor,
        case,
        CaseLedgerEventType.SUFFICIENCY_ASSESSED,
        f"Sufficiency assessed for {data.conclusion_type}",
        details={"assessment_id": str(assessment.id), "readiness": readiness},
    )
    audit_case(session, actor, case, "CASE_SUFFICIENCY_ASSESSED")
    return case, assessment, limitations, requests


def transition_case(
    session: Session,
    actor: ActorContext,
    project: Project,
    case_id: uuid.UUID,
    data: LifecycleTransitionCreate,
) -> DecisionCaseShell:
    case = scoped_case(session, project, case_id, for_update=True)
    require_version(case, data.expected_version)
    current = CaseLifecycle(case.lifecycle)
    if data.target_lifecycle not in FORWARD_TRANSITIONS.get(current, set()):
        raise HTTPException(status_code=409, detail="Forbidden lifecycle transition")
    if data.target_lifecycle == CaseLifecycle.ANALYSIS and case.readiness in {
        None,
        DecisionReadiness.INSUFFICIENT,
    }:
        raise HTTPException(status_code=409, detail="Sufficient evidence assessment required")
    if data.target_lifecycle == CaseLifecycle.DECISION_READY and case.readiness not in {
        DecisionReadiness.DECISION_READY,
        DecisionReadiness.DECISION_READY_WITH_LIMITATIONS,
    }:
        raise HTTPException(status_code=409, detail="Decision-ready evidence state required")
    case.lifecycle = data.target_lifecycle
    case.version += 1
    add_ledger(
        session,
        actor,
        case,
        CaseLedgerEventType.LIFECYCLE_TRANSITIONED,
        data.reason,
        from_lifecycle=current,
        to_lifecycle=data.target_lifecycle,
    )
    audit_case(session, actor, case, "CASE_LIFECYCLE_TRANSITIONED")
    return case


def block_case(
    session: Session,
    actor: ActorContext,
    project: Project,
    case_id: uuid.UUID,
    data: CaseBlockCreate,
) -> DecisionCaseShell:
    case = scoped_case(session, project, case_id, for_update=True)
    require_version(case, data.expected_version)
    if case.lifecycle in {CaseLifecycle.BLOCKED, CaseLifecycle.CLOSED}:
        raise HTTPException(status_code=409, detail="Case cannot be blocked in current state")
    previous = case.lifecycle
    case.blocked_from_lifecycle = previous
    case.lifecycle = CaseLifecycle.BLOCKED
    case.blocker_code = data.blocker_code
    case.blocker_description = data.blocker_description
    case.governance_state = GovernanceState.GOVERNANCE_BLOCKED
    case.version += 1
    add_ledger(
        session,
        actor,
        case,
        CaseLedgerEventType.CASE_BLOCKED,
        data.blocker_description,
        from_lifecycle=previous,
        to_lifecycle=CaseLifecycle.BLOCKED,
        details={"blocker_code": data.blocker_code},
    )
    audit_case(session, actor, case, "CASE_BLOCKED")
    return case


def resume_case(
    session: Session,
    actor: ActorContext,
    project: Project,
    case_id: uuid.UUID,
    data: CaseResumeCreate,
) -> DecisionCaseShell:
    case = scoped_case(session, project, case_id, for_update=True)
    require_version(case, data.expected_version)
    if case.lifecycle != CaseLifecycle.BLOCKED:
        raise HTTPException(status_code=409, detail="Only blocked cases can resume")
    target = case.blocked_from_lifecycle or CaseLifecycle.EVIDENCE_ASSEMBLY
    case.lifecycle = target
    case.blocked_from_lifecycle = None
    case.blocker_code = None
    case.blocker_description = None
    case.governance_state = GovernanceState.HUMAN_REVIEW_REQUIRED
    case.version += 1
    add_ledger(
        session,
        actor,
        case,
        CaseLedgerEventType.CASE_RESUMED,
        data.reason,
        from_lifecycle=CaseLifecycle.BLOCKED,
        to_lifecycle=target,
    )
    audit_case(session, actor, case, "CASE_RESUMED")
    return case


def close_case(
    session: Session,
    actor: ActorContext,
    project: Project,
    case_id: uuid.UUID,
    data: CaseCloseCreate,
) -> DecisionCaseShell:
    case = scoped_case(session, project, case_id, for_update=True)
    require_version(case, data.expected_version)
    if case.lifecycle == CaseLifecycle.CLOSED:
        raise HTTPException(status_code=409, detail="Case is already closed")
    if data.outcome_reference:
        try:
            response_outcome_id = uuid.UUID(data.outcome_reference)
        except ValueError:
            response_outcome_id = None
        governed_outcomes_exist = session.scalar(
            select(ResponseOutcome.id).where(ResponseOutcome.case_id == case.id).limit(1)
        )
        if governed_outcomes_exist:
            response_outcome = (
                session.get(ResponseOutcome, response_outcome_id) if response_outcome_id else None
            )
            if response_outcome is None or response_outcome.case_id != case.id:
                raise HTTPException(
                    status_code=422,
                    detail="Closure must reference a governed response outcome for this case",
                )
    previous = case.lifecycle
    case.lifecycle = CaseLifecycle.CLOSED
    case.blocked_from_lifecycle = None
    case.blocker_code = None
    case.blocker_description = None
    case.outcome_reference = data.outcome_reference
    case.close_reason = data.administrative_rationale or "Outcome recorded"
    case.closed_at = datetime.now(UTC)
    case.version += 1
    add_ledger(
        session,
        actor,
        case,
        CaseLedgerEventType.CASE_CLOSED,
        case.close_reason,
        from_lifecycle=previous,
        to_lifecycle=CaseLifecycle.CLOSED,
        details={"outcome_reference": data.outcome_reference},
    )
    audit_case(session, actor, case, "CASE_CLOSED")
    publish_domain_event(
        session,
        actor,
        project,
        event_type="CaseClosed",
        aggregate_type="DECISION_CASE",
        aggregate_id=case.id,
        aggregate_version=case.version,
        payload={"outcome_reference": data.outcome_reference, "reason": case.close_reason},
    )
    return case


def reopen_case(
    session: Session,
    actor: ActorContext,
    project: Project,
    case_id: uuid.UUID,
    data: CaseReopenCreate,
) -> DecisionCaseShell:
    case = scoped_case(session, project, case_id, for_update=True)
    require_version(case, data.expected_version)
    if case.lifecycle != CaseLifecycle.CLOSED:
        raise HTTPException(status_code=409, detail="Only closed cases can reopen")
    if data.new_evidence_item_id:
        item = scoped_item(session, project, data.new_evidence_item_id)
        if session.get(CaseEvidenceAttachment, (case.id, item.id)) is None:
            session.add(
                CaseEvidenceAttachment(
                    case_id=case.id,
                    evidence_item_id=item.id,
                    attachment_reason=f"Reopen trigger: {data.trigger}",
                    attached_by=actor.actor_id,
                )
            )
    if data.trigger == "RESPONSE_FAILED":
        failed_active_response = session.scalar(
            select(CaseActiveResponse.id).where(
                CaseActiveResponse.case_id == case.id,
                CaseActiveResponse.status == ActiveResponseStatus.FAILED,
            )
        )
        failed_execution = session.scalar(
            select(ResponseExecutionObservation.id).where(
                ResponseExecutionObservation.case_id == case.id,
                ResponseExecutionObservation.status == "FAILED",
            )
        )
        if failed_active_response is None and failed_execution is None:
            raise HTTPException(
                status_code=422, detail="Response-failed reopening requires a failed response"
            )
    case.lifecycle = CaseLifecycle.REOPENED
    case.reopen_trigger = data.trigger
    case.reopen_reason = data.reason
    case.reopened_at = datetime.now(UTC)
    case.closed_at = None
    case.readiness = None
    case.governance_state = GovernanceState.HUMAN_REVIEW_REQUIRED
    case.version += 1
    add_ledger(
        session,
        actor,
        case,
        CaseLedgerEventType.CASE_REOPENED,
        data.reason,
        from_lifecycle=CaseLifecycle.CLOSED,
        to_lifecycle=CaseLifecycle.REOPENED,
        details={"trigger": data.trigger, "new_evidence_item_id": str(data.new_evidence_item_id)},
    )
    audit_case(session, actor, case, "CASE_REOPENED")
    publish_domain_event(
        session,
        actor,
        project,
        event_type="CaseReopened",
        aggregate_type="DECISION_CASE",
        aggregate_id=case.id,
        aggregate_version=case.version,
        payload={"trigger": data.trigger, "reason": data.reason},
    )
    return case


def resolve_limitation(
    session: Session,
    actor: ActorContext,
    project: Project,
    case_id: uuid.UUID,
    limitation_id: uuid.UUID,
    expected_version: int,
    resolution: str,
) -> tuple[DecisionCaseShell, CaseLimitation]:
    case = scoped_case(session, project, case_id, for_update=True)
    require_version(case, expected_version)
    if case.lifecycle == CaseLifecycle.CLOSED:
        raise HTTPException(
            status_code=409, detail="Closed case must be reopened before resolution"
        )
    limitation = session.get(CaseLimitation, limitation_id)
    if limitation is None or limitation.case_id != case.id:
        raise HTTPException(status_code=404, detail="Case limitation not found")
    if limitation.status != LimitationStatus.OPEN:
        raise HTTPException(status_code=409, detail="Case limitation already resolved")
    limitation.status = LimitationStatus.RESOLVED
    limitation.resolution = resolution
    limitation.resolved_by = actor.actor_id
    limitation.resolved_at = datetime.now(UTC)
    case.version += 1
    add_ledger(
        session,
        actor,
        case,
        CaseLedgerEventType.LIMITATION_RESOLVED,
        resolution,
        details={"limitation_id": str(limitation.id)},
    )
    audit_case(session, actor, case, "CASE_LIMITATION_RESOLVED")
    return case, limitation


def policy_projection() -> list[dict[str, Any]]:
    return [
        {
            "conclusion_type": conclusion,
            "policy_version": POLICY_VERSION,
            "required_field_groups": policy["field_groups"],
            "required_authorized_contexts": policy["contexts"],
            "requires_strong_truth": policy["strong_truth"],
        }
        for conclusion, policy in SUFFICIENCY_POLICIES.items()
    ]
