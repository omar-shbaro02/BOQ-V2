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
    OrchestrationStatus,
)
from app.governance_schemas import HumanDecisionCreate
from app.models import (
    AuthorityGrant,
    DecisionCaseControlledObject,
    HumanDecision,
    OrchestrationRun,
    Project,
)
from app.services.cases import add_ledger, audit_case, require_version, scoped_case
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session


def request_digest(data: HumanDecisionCreate) -> str:
    return hashlib.sha256(
        json.dumps(data.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


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
