from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from app.auth import ActorContext
from app.generated.taxonomies import (
    AuthorityValidationOutcome,
    CaseLedgerEventType,
    CaseLifecycle,
    DecisionReadiness,
    Disposition,
    GovernanceState,
    HumanDecisionAgreement,
    LearningCategory,
    OrchestrationStatus,
    OutcomeClassification,
    ResponseExecutionStatus,
)
from app.governance_schemas import (
    HumanDecisionCreate,
    LearningRecordCreate,
    ResponseAuthorizationCreate,
    ResponseExecutionCreate,
    ResponseOutcomeCreate,
    ResponseProposalCreate,
)
from app.models import (
    AuthorityGrant,
    CaseEvidenceAttachment,
    CaseLearningRecord,
    DecisionCaseControlledObject,
    EvidenceItem,
    HumanDecision,
    ImpactAssessment,
    OrchestrationRun,
    Project,
    ResponseAuthorization,
    ResponseExecutionObservation,
    ResponseOutcome,
    ResponseProposal,
)
from app.services.cases import add_ledger, audit_case, require_version, scoped_case
from app.services.events import publish_domain_event
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session


def request_digest(data: HumanDecisionCreate) -> str:
    return hashlib.sha256(
        json.dumps(data.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _digest(data: Any) -> str:
    return hashlib.sha256(
        json.dumps(data.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _scope(grant: AuthorityGrant) -> dict[str, Any]:
    return {
        "authority_type": grant.authority_type,
        "controlled_object_id": str(grant.controlled_object_id)
        if grant.controlled_object_id
        else None,
        "max_amount": str(grant.max_amount) if grant.max_amount is not None else None,
        "currency": grant.currency,
        "valid_from": grant.valid_from.isoformat() if grant.valid_from else None,
        "valid_until": grant.valid_until.isoformat() if grant.valid_until else None,
    }


def _attached_evidence(
    session: Session, project: Project, case_id: uuid.UUID, ids: list[uuid.UUID]
) -> list[str]:
    unique = list(dict.fromkeys(ids))
    for item_id in unique:
        item = session.get(EvidenceItem, item_id)
        attached = session.get(CaseEvidenceAttachment, (case_id, item_id))
        if item is None or item.project_id != project.id or attached is None:
            raise HTTPException(
                status_code=422, detail="Response evidence must be attached to this case"
            )
    return [str(value) for value in unique]


def validate_authority(
    session: Session,
    actor: ActorContext,
    project: Project,
    case_id: uuid.UUID,
    data: HumanDecisionCreate,
) -> tuple[AuthorityValidationOutcome, AuthorityGrant, dict[str, Any]]:
    grant = session.get(AuthorityGrant, data.authority_grant_id)
    if (
        grant is None
        or grant.project_id != project.id
        or grant.actor_id != actor.actor_id
        or not grant.active
    ):
        raise HTTPException(status_code=403, detail="Active authority grant denied")
    today = datetime.now(UTC).date()
    if (grant.valid_from and today < grant.valid_from) or (
        grant.valid_until and today > grant.valid_until
    ):
        raise HTTPException(
            status_code=403, detail="Authority grant is outside its validity window"
        )
    accepted_types = {
        "CASE_DISPOSITION",
        f"DISPOSITION_{data.disposition.value}",
        data.disposition.value,
    }
    if grant.authority_type not in accepted_types:
        raise HTTPException(
            status_code=403, detail="Authority grant does not cover this disposition"
        )
    case_objects = set(
        session.scalars(
            select(DecisionCaseControlledObject.controlled_object_id).where(
                DecisionCaseControlledObject.case_id == case_id
            )
        )
    )
    if grant.controlled_object_id and grant.controlled_object_id not in case_objects:
        raise HTTPException(
            status_code=403, detail="Authority grant is outside the case object scope"
        )
    if data.decision_amount is not None:
        if grant.max_amount is None:
            raise HTTPException(status_code=403, detail="Authority grant has no amount authority")
        if grant.currency != data.currency:
            raise HTTPException(status_code=403, detail="Authority grant currency mismatch")
        if Decimal(data.decision_amount) > Decimal(grant.max_amount):
            raise HTTPException(status_code=403, detail="Decision amount exceeds authority grant")
    scope = {
        "authority_type": grant.authority_type,
        "controlled_object_id": str(grant.controlled_object_id)
        if grant.controlled_object_id
        else None,
        "max_amount": str(grant.max_amount) if grant.max_amount is not None else None,
        "currency": grant.currency,
        "valid_from": grant.valid_from.isoformat() if grant.valid_from else None,
        "valid_until": grant.valid_until.isoformat() if grant.valid_until else None,
        "escalation_level": grant.escalation_level,
        "escalates_to_actor_id": grant.escalates_to_actor_id,
    }
    return AuthorityValidationOutcome.AUTHORIZED, grant, scope


def create_human_decision(
    session: Session,
    actor: ActorContext,
    project: Project,
    case_id: uuid.UUID,
    data: HumanDecisionCreate,
    idempotency_key: str,
) -> tuple[Any, HumanDecision]:
    case = scoped_case(session, project, case_id, for_update=True)
    digest = request_digest(data)
    existing = session.scalar(
        select(HumanDecision).where(
            HumanDecision.case_id == case.id,
            HumanDecision.idempotency_key == idempotency_key,
        )
    )
    if existing:
        if existing.request_hash != digest:
            raise HTTPException(status_code=409, detail="Idempotency key payload mismatch")
        return case, existing
    require_version(case, data.expected_version)
    if case.lifecycle == CaseLifecycle.CLOSED:
        raise HTTPException(status_code=409, detail="Closed case cannot receive a human decision")
    run = session.get(OrchestrationRun, data.orchestration_run_id)
    if run is None or run.case_id != case.id:
        raise HTTPException(status_code=404, detail="Orchestration run not found")
    if run.status in {OrchestrationStatus.STOPPED, OrchestrationStatus.FAILED} and (
        data.disposition != Disposition.VERIFY
    ):
        raise HTTPException(status_code=409, detail="Stopped orchestration only supports VERIFY")
    if (
        run.readiness
        in {
            DecisionReadiness.INSUFFICIENT,
            DecisionReadiness.VERIFICATION_REQUIRED,
        }
        and data.disposition != Disposition.VERIFY
    ):
        raise HTTPException(status_code=409, detail="Case readiness only supports VERIFY")
    recommendation = run.recommended_disposition
    if data.recommendation_agreement == HumanDecisionAgreement.AGREE and (
        data.disposition != recommendation
    ):
        raise HTTPException(status_code=422, detail="AGREE requires the recommended disposition")
    if data.recommendation_agreement == HumanDecisionAgreement.DISAGREE and (
        data.disposition == recommendation
    ):
        raise HTTPException(status_code=422, detail="DISAGREE requires a different disposition")
    if data.response_authorization_reference and data.disposition != Disposition.INTERVENE:
        raise HTTPException(
            status_code=422,
            detail="Response authorization reference is only valid for INTERVENE",
        )
    outcome, grant, scope = validate_authority(session, actor, project, case.id, data)
    number = (
        session.scalar(
            select(func.max(HumanDecision.decision_number)).where(HumanDecision.case_id == case.id)
        )
        or 0
    ) + 1
    decision = HumanDecision(
        id=uuid.uuid4(),
        organization_id=project.organization_id,
        project_id=project.id,
        case_id=case.id,
        orchestration_run_id=run.id,
        authority_grant_id=grant.id,
        decision_number=number,
        disposition=data.disposition,
        recommendation_agreement=data.recommendation_agreement,
        rationale=data.rationale,
        authority_outcome=outcome,
        authority_scope=scope,
        decision_amount=data.decision_amount,
        currency=data.currency,
        limitations=data.limitations,
        response_authorization_reference=data.response_authorization_reference,
        idempotency_key=idempotency_key,
        request_hash=digest,
        decided_by=actor.actor_id,
    )
    session.add(decision)
    session.flush()
    case.last_human_decision_id = decision.id
    case.lifecycle = CaseLifecycle.HUMAN_DISPOSITION
    case.governance_state = {
        Disposition.INTERVENE: GovernanceState.APPROVAL_REQUIRED,
        Disposition.ESCALATE: GovernanceState.ESCALATION_REQUIRED,
        Disposition.NO_ACTION: GovernanceState.AUTHORIZED_TO_PROCEED,
    }.get(data.disposition, GovernanceState.ANALYSIS_AUTHORIZED)
    case.version += 1
    add_ledger(
        session,
        actor,
        case,
        CaseLedgerEventType.HUMAN_DECISION_RECORDED,
        "Authorized human disposition recorded separately from recommendation",
        details={
            "decision_id": str(decision.id),
            "orchestration_run_id": str(run.id),
            "disposition": data.disposition.value,
            "recommendation_agreement": data.recommendation_agreement.value,
            "authority_grant_id": str(grant.id),
        },
    )
    audit_case(
        session,
        actor,
        case,
        "HUMAN_DECISION_RECORDED",
        {"decision_id": str(decision.id), "authority_grant_id": str(grant.id)},
    )
    return case, decision


def create_response_proposal(
    session: Session,
    actor: ActorContext,
    project: Project,
    case_id: uuid.UUID,
    data: ResponseProposalCreate,
    key: str,
):
    case = scoped_case(session, project, case_id, for_update=True)
    digest = _digest(data)
    existing = session.scalar(
        select(ResponseProposal).where(
            ResponseProposal.case_id == case.id, ResponseProposal.idempotency_key == key
        )
    )
    if existing:
        if existing.request_hash != digest:
            raise HTTPException(status_code=409, detail="Idempotency key payload mismatch")
        return case, existing
    require_version(case, data.expected_version)
    decision = session.get(HumanDecision, data.human_decision_id)
    if decision is None or decision.case_id != case.id:
        raise HTTPException(status_code=404, detail="Human decision not found")
    if decision.disposition != Disposition.INTERVENE:
        raise HTTPException(
            status_code=409, detail="Only an INTERVENE decision supports a response proposal"
        )
    if case.lifecycle == CaseLifecycle.CLOSED:
        raise HTTPException(
            status_code=409, detail="Closed case cannot receive a response proposal"
        )
    number = (
        session.scalar(
            select(func.max(ResponseProposal.proposal_number)).where(
                ResponseProposal.case_id == case.id
            )
        )
        or 0
    ) + 1
    proposal = ResponseProposal(
        id=uuid.uuid4(),
        organization_id=project.organization_id,
        project_id=project.id,
        case_id=case.id,
        human_decision_id=decision.id,
        proposal_number=number,
        response_type=data.response_type,
        objective=data.objective,
        actions=data.actions,
        assumptions=data.assumptions,
        simulated_effects=data.simulated_effects,
        requested_amount=data.requested_amount,
        currency=data.currency,
        idempotency_key=key,
        request_hash=digest,
        proposed_by=actor.actor_id,
    )
    session.add(proposal)
    case.version += 1
    add_ledger(
        session,
        actor,
        case,
        CaseLedgerEventType.RESPONSE_PROPOSED,
        "Human response proposed with explicit simulation",
        details={"proposal_id": str(proposal.id), "human_decision_id": str(decision.id)},
    )
    audit_case(session, actor, case, "RESPONSE_PROPOSED", {"proposal_id": str(proposal.id)})
    return case, proposal


def authorize_response(
    session: Session,
    actor: ActorContext,
    project: Project,
    case_id: uuid.UUID,
    proposal_id: uuid.UUID,
    data: ResponseAuthorizationCreate,
):
    case = scoped_case(session, project, case_id, for_update=True)
    require_version(case, data.expected_version)
    proposal = session.get(ResponseProposal, proposal_id)
    if proposal is None or proposal.case_id != case.id:
        raise HTTPException(status_code=404, detail="Response proposal not found")
    existing = session.scalar(
        select(ResponseAuthorization).where(ResponseAuthorization.proposal_id == proposal.id)
    )
    if existing:
        if (
            existing.authorization_reference != data.authorization_reference
            or existing.authority_grant_id != data.authority_grant_id
        ):
            raise HTTPException(
                status_code=409, detail="Response proposal already has a different authorization"
            )
        return case, existing
    decision = session.get(HumanDecision, proposal.human_decision_id)
    grant = session.get(AuthorityGrant, data.authority_grant_id)
    today = datetime.now(UTC).date()
    if (
        grant is None
        or grant.project_id != project.id
        or grant.actor_id != actor.actor_id
        or not grant.active
    ):
        raise HTTPException(status_code=403, detail="Active response authority grant denied")
    if grant.authority_type not in {"RESPONSE_AUTHORIZATION", "CONTROLLED_EXECUTION"}:
        raise HTTPException(
            status_code=403, detail="Authority grant does not authorize response execution"
        )
    if (grant.valid_from and today < grant.valid_from) or (
        grant.valid_until and today > grant.valid_until
    ):
        raise HTTPException(
            status_code=403, detail="Authority grant is outside its validity window"
        )
    case_objects = set(
        session.scalars(
            select(DecisionCaseControlledObject.controlled_object_id).where(
                DecisionCaseControlledObject.case_id == case.id
            )
        )
    )
    if grant.controlled_object_id and grant.controlled_object_id not in case_objects:
        raise HTTPException(
            status_code=403, detail="Authority grant is outside the case object scope"
        )
    if proposal.requested_amount is not None and (
        grant.max_amount is None
        or grant.currency != proposal.currency
        or proposal.requested_amount > grant.max_amount
    ):
        raise HTTPException(status_code=403, detail="Response amount exceeds authority grant")
    if (
        decision.response_authorization_reference
        and decision.response_authorization_reference != data.authorization_reference
    ):
        raise HTTPException(
            status_code=422, detail="Authorization reference differs from the human decision"
        )
    authorization = ResponseAuthorization(
        id=uuid.uuid4(),
        organization_id=project.organization_id,
        project_id=project.id,
        case_id=case.id,
        proposal_id=proposal.id,
        human_decision_id=decision.id,
        authority_grant_id=grant.id,
        authorization_reference=data.authorization_reference,
        authority_scope=_scope(grant),
        authorized_by=actor.actor_id,
    )
    session.add(authorization)
    case.governance_state = GovernanceState.AUTHORIZED_TO_PROCEED
    case.lifecycle = CaseLifecycle.RESPONSE_ESCALATION
    case.version += 1
    add_ledger(
        session,
        actor,
        case,
        CaseLedgerEventType.RESPONSE_AUTHORIZED,
        "Explicit human response authorization recorded",
        details={
            "proposal_id": str(proposal.id),
            "authorization_id": str(authorization.id),
            "authority_grant_id": str(grant.id),
        },
    )
    audit_case(
        session, actor, case, "RESPONSE_AUTHORIZED", {"authorization_id": str(authorization.id)}
    )
    publish_domain_event(
        session,
        actor,
        project,
        event_type="ResponseAuthorized",
        aggregate_type="DECISION_CASE",
        aggregate_id=case.id,
        aggregate_version=case.version,
        payload={
            "proposal_id": str(proposal.id),
            "authorization_id": str(authorization.id),
            "human_decision_id": str(decision.id),
            "authority_grant_id": str(grant.id),
            "authorization_reference": data.authorization_reference,
        },
    )
    return case, authorization


TRANSITIONS = {
    None: {
        ResponseExecutionStatus.MOBILIZING,
        ResponseExecutionStatus.IN_PROGRESS,
        ResponseExecutionStatus.CANCELLED,
    },
    ResponseExecutionStatus.MOBILIZING: {
        ResponseExecutionStatus.IN_PROGRESS,
        ResponseExecutionStatus.CANCELLED,
        ResponseExecutionStatus.FAILED,
    },
    ResponseExecutionStatus.IN_PROGRESS: {
        ResponseExecutionStatus.COMPLETED,
        ResponseExecutionStatus.FAILED,
        ResponseExecutionStatus.CANCELLED,
    },
}


def observe_response_execution(
    session: Session,
    actor: ActorContext,
    project: Project,
    case_id: uuid.UUID,
    proposal_id: uuid.UUID,
    data: ResponseExecutionCreate,
    key: str,
):
    case = scoped_case(session, project, case_id, for_update=True)
    digest = _digest(data)
    existing = session.scalar(
        select(ResponseExecutionObservation).where(
            ResponseExecutionObservation.proposal_id == proposal_id,
            ResponseExecutionObservation.idempotency_key == key,
        )
    )
    if existing:
        if existing.request_hash != digest:
            raise HTTPException(status_code=409, detail="Idempotency key payload mismatch")
        return case, existing
    require_version(case, data.expected_version)
    authorization = session.scalar(
        select(ResponseAuthorization).where(
            ResponseAuthorization.proposal_id == proposal_id,
            ResponseAuthorization.case_id == case.id,
        )
    )
    if authorization is None:
        raise HTTPException(
            status_code=409, detail="Response execution requires explicit authorization"
        )
    latest = session.scalar(
        select(ResponseExecutionObservation)
        .where(ResponseExecutionObservation.proposal_id == proposal_id)
        .order_by(ResponseExecutionObservation.sequence_number.desc())
    )
    previous = ResponseExecutionStatus(latest.status) if latest else None
    if data.status not in TRANSITIONS.get(previous, set()):
        raise HTTPException(status_code=409, detail="Invalid response execution transition")
    evidence_ids = _attached_evidence(session, project, case.id, data.evidence_item_ids)
    sequence = (latest.sequence_number if latest else 0) + 1
    observation = ResponseExecutionObservation(
        id=uuid.uuid4(),
        organization_id=project.organization_id,
        project_id=project.id,
        case_id=case.id,
        proposal_id=proposal_id,
        authorization_id=authorization.id,
        sequence_number=sequence,
        status=data.status,
        observed_at=data.observed_at,
        details=data.details,
        evidence_item_ids=evidence_ids,
        idempotency_key=key,
        request_hash=digest,
        recorded_by=actor.actor_id,
    )
    session.add(observation)
    case.lifecycle = CaseLifecycle.OUTCOME_MONITORING
    case.version += 1
    add_ledger(
        session,
        actor,
        case,
        CaseLedgerEventType.RESPONSE_EXECUTION_OBSERVED,
        "Response execution status observed; no execution command was issued",
        details={
            "proposal_id": str(proposal_id),
            "observation_id": str(observation.id),
            "status": data.status.value,
        },
    )
    audit_case(
        session,
        actor,
        case,
        "RESPONSE_EXECUTION_OBSERVED",
        {"observation_id": str(observation.id), "status": data.status.value},
    )
    return case, observation


def record_response_outcome(
    session: Session,
    actor: ActorContext,
    project: Project,
    case_id: uuid.UUID,
    proposal_id: uuid.UUID,
    data: ResponseOutcomeCreate,
    key: str,
):
    case = scoped_case(session, project, case_id, for_update=True)
    digest = _digest(data)
    existing = session.scalar(
        select(ResponseOutcome).where(
            ResponseOutcome.proposal_id == proposal_id, ResponseOutcome.idempotency_key == key
        )
    )
    if existing:
        if existing.request_hash != digest:
            raise HTTPException(status_code=409, detail="Idempotency key payload mismatch")
        return case, existing
    require_version(case, data.expected_version)
    authorization = session.scalar(
        select(ResponseAuthorization).where(
            ResponseAuthorization.proposal_id == proposal_id,
            ResponseAuthorization.case_id == case.id,
        )
    )
    latest = session.scalar(
        select(ResponseExecutionObservation)
        .where(ResponseExecutionObservation.proposal_id == proposal_id)
        .order_by(ResponseExecutionObservation.sequence_number.desc())
    )
    if (
        authorization is None
        or latest is None
        or latest.status not in {ResponseExecutionStatus.COMPLETED, ResponseExecutionStatus.FAILED}
    ):
        raise HTTPException(
            status_code=409, detail="Outcome requires a completed or failed authorized response"
        )
    evidence_ids = _attached_evidence(session, project, case.id, data.evidence_item_ids)
    if data.classification != OutcomeClassification.NOT_YET_OBSERVABLE and not evidence_ids:
        raise HTTPException(
            status_code=422, detail="Realized outcome classification requires attached evidence"
        )
    outcome = ResponseOutcome(
        id=uuid.uuid4(),
        organization_id=project.organization_id,
        project_id=project.id,
        case_id=case.id,
        proposal_id=proposal_id,
        authorization_id=authorization.id,
        classification=data.classification,
        evidence_item_ids=evidence_ids,
        rationale=data.rationale,
        idempotency_key=key,
        request_hash=digest,
        assessed_by=actor.actor_id,
    )
    session.add(outcome)
    case.outcome_reference = str(outcome.id)
    case.version += 1
    add_ledger(
        session,
        actor,
        case,
        CaseLedgerEventType.RESPONSE_OUTCOME_RECORDED,
        "Evidence-backed realized response outcome recorded",
        details={
            "proposal_id": str(proposal_id),
            "outcome_id": str(outcome.id),
            "classification": data.classification.value,
            "evidence_item_ids": evidence_ids,
        },
    )
    audit_case(session, actor, case, "RESPONSE_OUTCOME_RECORDED", {"outcome_id": str(outcome.id)})
    publish_domain_event(
        session,
        actor,
        project,
        event_type="OutcomeObserved",
        aggregate_type="DECISION_CASE",
        aggregate_id=case.id,
        aggregate_version=case.version,
        payload={
            "proposal_id": str(proposal_id),
            "authorization_id": str(authorization.id),
            "outcome_id": str(outcome.id),
            "classification": data.classification.value,
            "evidence_item_ids": evidence_ids,
        },
    )
    return case, outcome


def create_learning_record(
    session: Session,
    actor: ActorContext,
    project: Project,
    case_id: uuid.UUID,
    data: LearningRecordCreate,
    key: str,
):
    case = scoped_case(session, project, case_id, for_update=True)
    digest = _digest(data)
    existing = session.scalar(
        select(CaseLearningRecord).where(
            CaseLearningRecord.case_id == case.id,
            CaseLearningRecord.idempotency_key == key,
        )
    )
    if existing:
        if existing.request_hash != digest:
            raise HTTPException(status_code=409, detail="Idempotency key payload mismatch")
        return case, existing
    require_version(case, data.expected_version)
    outcome = session.get(ResponseOutcome, data.response_outcome_id)
    if outcome is None or outcome.case_id != case.id:
        raise HTTPException(status_code=404, detail="Response outcome not found")
    proposal = session.get(ResponseProposal, outcome.proposal_id)
    decision = session.get(HumanDecision, proposal.human_decision_id) if proposal else None
    run = session.get(OrchestrationRun, decision.orchestration_run_id) if decision else None
    if proposal is None or decision is None or run is None:
        raise HTTPException(status_code=409, detail="Learning lineage is incomplete")
    impact = session.scalar(
        select(ImpactAssessment)
        .where(
            ImpactAssessment.case_id == case.id,
            ImpactAssessment.snapshot_id == run.snapshot_id,
        )
        .order_by(ImpactAssessment.assessment_number.desc())
    )
    calibration = {
        "recommended_disposition": run.recommended_disposition,
        "human_disposition": decision.disposition,
        "recommendation_agreement": decision.recommendation_agreement,
        "predicted_overall_confidence": str(impact.overall_confidence) if impact else None,
        "realized_outcome": outcome.classification,
        "orchestration_policy_versions": run.policy_versions,
        "orchestration_formula_version": run.formula_version,
    }
    record = CaseLearningRecord(
        id=uuid.uuid4(),
        organization_id=project.organization_id,
        project_id=project.id,
        case_id=case.id,
        response_outcome_id=outcome.id,
        human_decision_id=decision.id,
        orchestration_run_id=run.id,
        category=LearningCategory(data.category),
        finding=data.finding,
        contributing_factors=data.contributing_factors,
        calibration=calibration,
        calibration_notes=data.calibration_notes,
        idempotency_key=key,
        request_hash=digest,
        recorded_by=actor.actor_id,
    )
    session.add(record)
    case.version += 1
    add_ledger(
        session,
        actor,
        case,
        CaseLedgerEventType.LEARNING_RECORDED,
        "Immutable outcome-linked learning and calibration recorded",
        details={
            "learning_record_id": str(record.id),
            "response_outcome_id": str(outcome.id),
            "category": data.category.value,
        },
    )
    audit_case(session, actor, case, "LEARNING_RECORDED", {"learning_record_id": str(record.id)})
    return case, record
