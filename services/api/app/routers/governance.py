from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import ActorContext, get_actor
from app.database import get_db
from app.generated.taxonomies import ProjectRole
from app.governance_schemas import (
    HumanDecisionCreate,
    HumanDecisionRead,
    HumanDecisionResult,
    LearningRecordCreate,
    LearningRecordRead,
    ResponseAuthorizationCreate,
    ResponseAuthorizationRead,
    ResponseExecutionCreate,
    ResponseExecutionRead,
    ResponseOutcomeCreate,
    ResponseOutcomeRead,
    ResponseProposalCreate,
    ResponseProposalRead,
)
from app.models import (
    CaseLearningRecord,
    HumanDecision,
    ResponseExecutionObservation,
    ResponseOutcome,
    ResponseProposal,
)
from app.services.access import get_scoped_project, require_project_roles
from app.services.cases import scoped_case
from app.services.governance import (
    authorize_response,
    create_human_decision,
    create_learning_record,
    create_response_proposal,
    observe_response_execution,
    record_response_outcome,
)

router = APIRouter(prefix="/api/v1/projects/{project_id}", tags=["governance"])
SessionDep = Annotated[Session, Depends(get_db)]
ActorDep = Annotated[ActorContext, Depends(get_actor)]
READ_ROLES = set(ProjectRole)
DECISION_ROLES = {
    ProjectRole.ORGANIZATION_ADMIN,
    ProjectRole.PROJECT_ADMIN,
    ProjectRole.DECISION_OWNER,
    ProjectRole.APPROVER_ESCALATION_AUTHORITY,
}


def project_scope(session: Session, actor: ActorContext, project_id: uuid.UUID, roles: set):
    project = get_scoped_project(session, actor, project_id)
    require_project_roles(session, actor, project, roles)
    return project


@router.get("/decision-cases/{case_id}/human-decisions", response_model=list[HumanDecisionRead])
def get_decisions(
    project_id: uuid.UUID, case_id: uuid.UUID, session: SessionDep, actor: ActorDep
) -> list[HumanDecision]:
    project = project_scope(session, actor, project_id, READ_ROLES)
    scoped_case(session, project, case_id)
    return list(
        session.scalars(
            select(HumanDecision)
            .where(HumanDecision.project_id == project.id, HumanDecision.case_id == case_id)
            .order_by(HumanDecision.decision_number)
        )
    )


@router.post(
    "/decision-cases/{case_id}/human-decisions",
    response_model=HumanDecisionResult,
    status_code=201,
)
def add_decision(
    project_id: uuid.UUID,
    case_id: uuid.UUID,
    data: HumanDecisionCreate,
    session: SessionDep,
    actor: ActorDep,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=200)],
) -> HumanDecisionResult:
    project = project_scope(session, actor, project_id, DECISION_ROLES)
    case, decision = create_human_decision(session, actor, project, case_id, data, idempotency_key)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Decision conflict"
        ) from exc
    session.refresh(case)
    session.refresh(decision)
    return HumanDecisionResult(case=case, decision=decision)


def commit(session: Session, detail: str) -> None:
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail=detail) from exc


@router.get(
    "/decision-cases/{case_id}/response-proposals", response_model=list[ResponseProposalRead]
)
def get_response_proposals(
    project_id: uuid.UUID, case_id: uuid.UUID, session: SessionDep, actor: ActorDep
):
    project = project_scope(session, actor, project_id, READ_ROLES)
    scoped_case(session, project, case_id)
    return list(
        session.scalars(
            select(ResponseProposal)
            .where(ResponseProposal.case_id == case_id)
            .order_by(ResponseProposal.proposal_number)
        )
    )


@router.post(
    "/decision-cases/{case_id}/response-proposals",
    response_model=ResponseProposalRead,
    status_code=201,
)
def add_response_proposal(
    project_id: uuid.UUID,
    case_id: uuid.UUID,
    data: ResponseProposalCreate,
    session: SessionDep,
    actor: ActorDep,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=200)],
):
    project = project_scope(session, actor, project_id, DECISION_ROLES)
    case, proposal = create_response_proposal(
        session, actor, project, case_id, data, idempotency_key
    )
    commit(session, "Response proposal conflict")
    session.refresh(case)
    session.refresh(proposal)
    return proposal


@router.post(
    "/decision-cases/{case_id}/response-proposals/{proposal_id}/authorization",
    response_model=ResponseAuthorizationRead,
    status_code=201,
)
def add_response_authorization(
    project_id: uuid.UUID,
    case_id: uuid.UUID,
    proposal_id: uuid.UUID,
    data: ResponseAuthorizationCreate,
    session: SessionDep,
    actor: ActorDep,
):
    project = project_scope(session, actor, project_id, DECISION_ROLES)
    case, authorization = authorize_response(session, actor, project, case_id, proposal_id, data)
    commit(session, "Response authorization conflict")
    session.refresh(case)
    session.refresh(authorization)
    return authorization


@router.get(
    "/decision-cases/{case_id}/response-proposals/{proposal_id}/execution",
    response_model=list[ResponseExecutionRead],
)
def get_response_execution(
    project_id: uuid.UUID,
    case_id: uuid.UUID,
    proposal_id: uuid.UUID,
    session: SessionDep,
    actor: ActorDep,
):
    project = project_scope(session, actor, project_id, READ_ROLES)
    scoped_case(session, project, case_id)
    return list(
        session.scalars(
            select(ResponseExecutionObservation)
            .where(
                ResponseExecutionObservation.case_id == case_id,
                ResponseExecutionObservation.proposal_id == proposal_id,
            )
            .order_by(ResponseExecutionObservation.sequence_number)
        )
    )


@router.post(
    "/decision-cases/{case_id}/response-proposals/{proposal_id}/execution",
    response_model=ResponseExecutionRead,
    status_code=201,
)
def add_response_execution(
    project_id: uuid.UUID,
    case_id: uuid.UUID,
    proposal_id: uuid.UUID,
    data: ResponseExecutionCreate,
    session: SessionDep,
    actor: ActorDep,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=200)],
):
    project = project_scope(session, actor, project_id, DECISION_ROLES)
    case, observation = observe_response_execution(
        session, actor, project, case_id, proposal_id, data, idempotency_key
    )
    commit(session, "Response execution observation conflict")
    session.refresh(case)
    session.refresh(observation)
    return observation


@router.get(
    "/decision-cases/{case_id}/response-proposals/{proposal_id}/outcomes",
    response_model=list[ResponseOutcomeRead],
)
def get_response_outcomes(
    project_id: uuid.UUID,
    case_id: uuid.UUID,
    proposal_id: uuid.UUID,
    session: SessionDep,
    actor: ActorDep,
):
    project = project_scope(session, actor, project_id, READ_ROLES)
    scoped_case(session, project, case_id)
    return list(
        session.scalars(
            select(ResponseOutcome)
            .where(ResponseOutcome.case_id == case_id, ResponseOutcome.proposal_id == proposal_id)
            .order_by(ResponseOutcome.assessed_at)
        )
    )


@router.post(
    "/decision-cases/{case_id}/response-proposals/{proposal_id}/outcomes",
    response_model=ResponseOutcomeRead,
    status_code=201,
)
def add_response_outcome(
    project_id: uuid.UUID,
    case_id: uuid.UUID,
    proposal_id: uuid.UUID,
    data: ResponseOutcomeCreate,
    session: SessionDep,
    actor: ActorDep,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=200)],
):
    project = project_scope(session, actor, project_id, DECISION_ROLES)
    case, outcome = record_response_outcome(
        session, actor, project, case_id, proposal_id, data, idempotency_key
    )
    commit(session, "Response outcome conflict")
    session.refresh(case)
    session.refresh(outcome)
    return outcome


@router.get("/decision-cases/{case_id}/learning-records", response_model=list[LearningRecordRead])
def get_learning_records(
    project_id: uuid.UUID, case_id: uuid.UUID, session: SessionDep, actor: ActorDep
):
    project = project_scope(session, actor, project_id, READ_ROLES)
    scoped_case(session, project, case_id)
    return list(
        session.scalars(
            select(CaseLearningRecord)
            .where(CaseLearningRecord.case_id == case_id)
            .order_by(CaseLearningRecord.recorded_at)
        )
    )


@router.post(
    "/decision-cases/{case_id}/learning-records",
    response_model=LearningRecordRead,
    status_code=201,
)
def add_learning_record(
    project_id: uuid.UUID,
    case_id: uuid.UUID,
    data: LearningRecordCreate,
    session: SessionDep,
    actor: ActorDep,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=200)],
):
    project = project_scope(session, actor, project_id, DECISION_ROLES)
    case, record = create_learning_record(session, actor, project, case_id, data, idempotency_key)
    commit(session, "Learning record conflict")
    session.refresh(case)
    session.refresh(record)
    return record
