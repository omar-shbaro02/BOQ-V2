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
from app.governance_schemas import HumanDecisionCreate, HumanDecisionRead, HumanDecisionResult
from app.models import HumanDecision
from app.services.access import get_scoped_project, require_project_roles
from app.services.cases import scoped_case
from app.services.governance import create_human_decision

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
