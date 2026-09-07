from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import ActorContext, get_actor
from app.cost_schemas import (
    BudgetContextRead,
    CostAssessmentCreate,
    CostAssessmentRead,
    CostAssessmentResult,
    CostPolicyCreate,
    CostPolicyRead,
    CostRecordCreate,
    CostRecordRead,
)
from app.database import get_db
from app.generated.taxonomies import (
    AuthorizedContextType,
    CostRecordKind,
    ProjectRole,
    SemanticState,
)
from app.models import AuthorizedContextVersion, CostAnalysisPolicy, CostAssessment, CostRecord
from app.services.access import get_scoped_project, require_project_roles
from app.services.cost import (
    assess_cost,
    budget_projection,
    create_policy,
    list_policies,
    record_cost,
)

router = APIRouter(prefix="/api/v1/projects/{project_id}", tags=["cost"])
SessionDep = Annotated[Session, Depends(get_db)]
ActorDep = Annotated[ActorContext, Depends(get_actor)]
READ_ROLES = set(ProjectRole)
RECORD_ROLES = {
    ProjectRole.ORGANIZATION_ADMIN,
    ProjectRole.PROJECT_ADMIN,
    ProjectRole.DATA_CONTRIBUTOR,
    ProjectRole.VERIFIER,
    ProjectRole.ANALYST_CONTROLLER,
}
ANALYSIS_ROLES = {
    ProjectRole.ORGANIZATION_ADMIN,
    ProjectRole.PROJECT_ADMIN,
    ProjectRole.ANALYST_CONTROLLER,
    ProjectRole.DECISION_OWNER,
}
POLICY_ROLES = {ProjectRole.ORGANIZATION_ADMIN, ProjectRole.PROJECT_ADMIN}


def scoped_project(session: Session, actor: ActorContext, project_id: uuid.UUID, roles: set):
    project = get_scoped_project(session, actor, project_id)
    require_project_roles(session, actor, project, roles)
    return project


def commit_or_conflict(session: Session, detail: str) -> None:
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from exc


@router.get("/cost/policies", response_model=list[CostPolicyRead])
def get_cost_policies(project_id: uuid.UUID, session: SessionDep, actor: ActorDep):
    project = scoped_project(session, actor, project_id, READ_ROLES)
    return list_policies(session, project)


@router.post("/cost/policies", response_model=CostPolicyRead, status_code=201)
def add_cost_policy(
    project_id: uuid.UUID, data: CostPolicyCreate, session: SessionDep, actor: ActorDep
) -> CostAnalysisPolicy:
    project = scoped_project(session, actor, project_id, POLICY_ROLES)
    policy = create_policy(session, actor, project, data)
    commit_or_conflict(session, "Cost policy version conflict")
    session.refresh(policy)
    return policy


@router.get("/cost/budget", response_model=BudgetContextRead)
def get_budget(
    project_id: uuid.UUID,
    session: SessionDep,
    actor: ActorDep,
    context_id: uuid.UUID | None = None,
):
    project = scoped_project(session, actor, project_id, READ_ROLES)
    if context_id:
        context = session.get(AuthorizedContextVersion, context_id)
        if context is None or context.project_id != project.id:
            raise HTTPException(status_code=404, detail="Budget context not found")
    else:
        context = session.scalar(
            select(AuthorizedContextVersion).where(
                AuthorizedContextVersion.project_id == project.id,
                AuthorizedContextVersion.context_type == AuthorizedContextType.BUDGET,
                AuthorizedContextVersion.semantic_state == SemanticState.CURRENT_AUTHORIZED,
            )
        )
        if context is None:
            raise HTTPException(status_code=404, detail="Current authorized budget not found")
    if context.context_type != AuthorizedContextType.BUDGET:
        raise HTTPException(status_code=422, detail="Context is not a budget")
    if (
        context.semantic_state not in {SemanticState.CURRENT_AUTHORIZED, SemanticState.SUPERSEDED}
        or context.activated_at is None
    ):
        raise HTTPException(status_code=422, detail="Budget context was not authorized")
    return budget_projection(context)


@router.get("/cost/records", response_model=list[CostRecordRead])
def get_cost_records(
    project_id: uuid.UUID,
    session: SessionDep,
    actor: ActorDep,
    controlled_object_id: uuid.UUID | None = None,
    record_kind: CostRecordKind | None = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[CostRecord]:
    project = scoped_project(session, actor, project_id, READ_ROLES)
    query = select(CostRecord).where(CostRecord.project_id == project.id)
    if controlled_object_id:
        query = query.where(CostRecord.controlled_object_id == controlled_object_id)
    if record_kind:
        query = query.where(CostRecord.record_kind == record_kind)
    return list(
        session.scalars(query.order_by(CostRecord.as_of.desc()).offset(offset).limit(limit))
    )


@router.post("/cost/records", response_model=CostRecordRead, status_code=201)
def add_cost_record(
    project_id: uuid.UUID, data: CostRecordCreate, session: SessionDep, actor: ActorDep
) -> CostRecord:
    project = scoped_project(session, actor, project_id, RECORD_ROLES)
    record = record_cost(session, actor, project, data)
    commit_or_conflict(session, "Cost record normalization conflict")
    session.refresh(record)
    return record


@router.get("/decision-cases/{case_id}/cost-assessments", response_model=list[CostAssessmentRead])
def get_cost_assessments(
    project_id: uuid.UUID, case_id: uuid.UUID, session: SessionDep, actor: ActorDep
) -> list[CostAssessment]:
    project = scoped_project(session, actor, project_id, READ_ROLES)
    return list(
        session.scalars(
            select(CostAssessment)
            .where(CostAssessment.project_id == project.id, CostAssessment.case_id == case_id)
            .order_by(CostAssessment.assessment_number)
        )
    )


@router.post(
    "/decision-cases/{case_id}/cost-assessments",
    response_model=CostAssessmentResult,
    status_code=201,
)
def add_cost_assessment(
    project_id: uuid.UUID,
    case_id: uuid.UUID,
    data: CostAssessmentCreate,
    session: SessionDep,
    actor: ActorDep,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=200)],
) -> CostAssessmentResult:
    project = scoped_project(session, actor, project_id, ANALYSIS_ROLES)
    case, assessment = assess_cost(session, actor, project, case_id, data, idempotency_key)
    commit_or_conflict(session, "Cost assessment idempotency conflict")
    session.refresh(case)
    session.refresh(assessment)
    return CostAssessmentResult(case=case, assessment=assessment)
