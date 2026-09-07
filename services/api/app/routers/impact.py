from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import ActorContext, get_actor
from app.database import get_db
from app.generated.taxonomies import ImpactAssessmentStatus, PriorityBand, ProjectRole
from app.impact_schemas import (
    ConfidenceOverrideCreate,
    ConfidenceOverrideRead,
    ConfidenceOverrideResult,
    ImpactAssessmentCreate,
    ImpactAssessmentRead,
    ImpactAssessmentResult,
    ImpactPolicyCreate,
    ImpactPolicyRead,
)
from app.models import ConfidenceOverride, ImpactAssessment, ImpactPriorityPolicy
from app.services.access import get_scoped_project, require_project_roles
from app.services.impact import (
    create_confidence_override,
    create_impact_assessment,
    create_policy,
    list_policies,
)

router = APIRouter(prefix="/api/v1/projects/{project_id}", tags=["impact"])
SessionDep = Annotated[Session, Depends(get_db)]
ActorDep = Annotated[ActorContext, Depends(get_actor)]
READ_ROLES = set(ProjectRole)
ANALYSIS_ROLES = {
    ProjectRole.ORGANIZATION_ADMIN,
    ProjectRole.PROJECT_ADMIN,
    ProjectRole.ANALYST_CONTROLLER,
    ProjectRole.DECISION_OWNER,
}
ADMIN_ROLES = {ProjectRole.ORGANIZATION_ADMIN, ProjectRole.PROJECT_ADMIN}


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


@router.get("/impact/policies", response_model=list[ImpactPolicyRead])
def get_impact_policies(project_id: uuid.UUID, session: SessionDep, actor: ActorDep):
    project = scoped_project(session, actor, project_id, READ_ROLES)
    return list_policies(session, project)


@router.post("/impact/policies", response_model=ImpactPolicyRead, status_code=201)
def add_impact_policy(
    project_id: uuid.UUID, data: ImpactPolicyCreate, session: SessionDep, actor: ActorDep
) -> ImpactPriorityPolicy:
    project = scoped_project(session, actor, project_id, ADMIN_ROLES)
    policy = create_policy(session, actor, project, data)
    commit_or_conflict(session, "Impact policy version conflict")
    session.refresh(policy)
    return policy


@router.get(
    "/decision-cases/{case_id}/confidence-overrides",
    response_model=list[ConfidenceOverrideRead],
)
def get_confidence_overrides(
    project_id: uuid.UUID,
    case_id: uuid.UUID,
    session: SessionDep,
    actor: ActorDep,
) -> list[ConfidenceOverride]:
    project = scoped_project(session, actor, project_id, READ_ROLES)
    return list(
        session.scalars(
            select(ConfidenceOverride)
            .where(
                ConfidenceOverride.project_id == project.id, ConfidenceOverride.case_id == case_id
            )
            .order_by(ConfidenceOverride.approved_at)
        )
    )


@router.post(
    "/decision-cases/{case_id}/confidence-overrides",
    response_model=ConfidenceOverrideResult,
    status_code=201,
)
def add_confidence_override(
    project_id: uuid.UUID,
    case_id: uuid.UUID,
    data: ConfidenceOverrideCreate,
    session: SessionDep,
    actor: ActorDep,
) -> ConfidenceOverrideResult:
    project = scoped_project(session, actor, project_id, ADMIN_ROLES)
    case, override = create_confidence_override(session, actor, project, case_id, data)
    commit_or_conflict(session, "Confidence override conflict")
    session.refresh(case)
    session.refresh(override)
    return ConfidenceOverrideResult(case=case, override=override)


@router.get(
    "/decision-cases/{case_id}/impact-assessments",
    response_model=list[ImpactAssessmentRead],
)
def get_impact_assessments(
    project_id: uuid.UUID,
    case_id: uuid.UUID,
    session: SessionDep,
    actor: ActorDep,
    assessment_status: ImpactAssessmentStatus | None = None,
    priority_band: PriorityBand | None = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[ImpactAssessment]:
    project = scoped_project(session, actor, project_id, READ_ROLES)
    query = select(ImpactAssessment).where(
        ImpactAssessment.project_id == project.id, ImpactAssessment.case_id == case_id
    )
    if assessment_status:
        query = query.where(ImpactAssessment.assessment_status == assessment_status)
    if priority_band:
        query = query.where(ImpactAssessment.priority_band == priority_band)
    return list(
        session.scalars(
            query.order_by(ImpactAssessment.assessment_number).offset(offset).limit(limit)
        )
    )


@router.post(
    "/decision-cases/{case_id}/impact-assessments",
    response_model=ImpactAssessmentResult,
    status_code=201,
)
def add_impact_assessment(
    project_id: uuid.UUID,
    case_id: uuid.UUID,
    data: ImpactAssessmentCreate,
    session: SessionDep,
    actor: ActorDep,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=200)],
) -> ImpactAssessmentResult:
    project = scoped_project(session, actor, project_id, ANALYSIS_ROLES)
    case, assessment = create_impact_assessment(
        session, actor, project, case_id, data, idempotency_key
    )
    commit_or_conflict(session, "Impact assessment idempotency conflict")
    session.refresh(case)
    session.refresh(assessment)
    return ImpactAssessmentResult(case=case, assessment=assessment)
