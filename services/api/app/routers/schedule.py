from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import ActorContext, get_actor
from app.database import get_db
from app.generated.taxonomies import AuthorizedContextType, ProjectRole, SemanticState
from app.models import AuthorizedContextVersion, ScheduleAnalysisPolicy, ScheduleAssessment
from app.schedule_schemas import (
    ScheduleAssessmentCreate,
    ScheduleAssessmentRead,
    ScheduleAssessmentResult,
    ScheduleNetworkRead,
    SchedulePolicyCreate,
    SchedulePolicyRead,
)
from app.services.access import get_scoped_project, require_project_roles
from app.services.schedule import (
    assess_schedule,
    create_policy,
    list_policies,
    schedule_network,
)

router = APIRouter(prefix="/api/v1/projects/{project_id}", tags=["schedule"])
SessionDep = Annotated[Session, Depends(get_db)]
ActorDep = Annotated[ActorContext, Depends(get_actor)]
READ_ROLES = set(ProjectRole)
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


@router.get("/schedule/policies", response_model=list[SchedulePolicyRead])
def get_schedule_policies(
    project_id: uuid.UUID, session: SessionDep, actor: ActorDep
) -> list[dict | ScheduleAnalysisPolicy]:
    project = scoped_project(session, actor, project_id, READ_ROLES)
    return list_policies(session, project)


@router.post("/schedule/policies", response_model=SchedulePolicyRead, status_code=201)
def add_schedule_policy(
    project_id: uuid.UUID,
    data: SchedulePolicyCreate,
    session: SessionDep,
    actor: ActorDep,
) -> ScheduleAnalysisPolicy:
    project = scoped_project(session, actor, project_id, POLICY_ROLES)
    policy = create_policy(session, actor, project, data)
    commit_or_conflict(session, "Schedule policy version conflict")
    session.refresh(policy)
    return policy


@router.get("/schedule/network", response_model=ScheduleNetworkRead)
def get_schedule_network(
    project_id: uuid.UUID,
    session: SessionDep,
    actor: ActorDep,
    context_id: uuid.UUID | None = None,
) -> dict:
    project = scoped_project(session, actor, project_id, READ_ROLES)
    if context_id:
        context = session.get(AuthorizedContextVersion, context_id)
        if context is None or context.project_id != project.id:
            raise HTTPException(status_code=404, detail="Schedule context not found")
    else:
        context = session.scalar(
            select(AuthorizedContextVersion).where(
                AuthorizedContextVersion.project_id == project.id,
                AuthorizedContextVersion.context_type == AuthorizedContextType.SCHEDULE,
                AuthorizedContextVersion.semantic_state == SemanticState.CURRENT_AUTHORIZED,
            )
        )
        if context is None:
            raise HTTPException(status_code=404, detail="Current authorized schedule not found")
    if context.context_type != AuthorizedContextType.SCHEDULE:
        raise HTTPException(status_code=422, detail="Context is not a schedule")
    if (
        context.semantic_state
        not in {
            SemanticState.CURRENT_AUTHORIZED,
            SemanticState.SUPERSEDED,
        }
        or context.activated_at is None
    ):
        raise HTTPException(status_code=422, detail="Schedule context was not authorized")
    return schedule_network(context)


@router.get(
    "/decision-cases/{case_id}/schedule-assessments",
    response_model=list[ScheduleAssessmentRead],
)
def get_schedule_assessments(
    project_id: uuid.UUID,
    case_id: uuid.UUID,
    session: SessionDep,
    actor: ActorDep,
) -> list[ScheduleAssessment]:
    project = scoped_project(session, actor, project_id, READ_ROLES)
    return list(
        session.scalars(
            select(ScheduleAssessment)
            .where(
                ScheduleAssessment.project_id == project.id,
                ScheduleAssessment.case_id == case_id,
            )
            .order_by(ScheduleAssessment.assessment_number)
        )
    )


@router.post(
    "/decision-cases/{case_id}/schedule-assessments",
    response_model=ScheduleAssessmentResult,
    status_code=201,
)
def add_schedule_assessment(
    project_id: uuid.UUID,
    case_id: uuid.UUID,
    data: ScheduleAssessmentCreate,
    session: SessionDep,
    actor: ActorDep,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=200)],
) -> ScheduleAssessmentResult:
    project = scoped_project(session, actor, project_id, ANALYSIS_ROLES)
    case, assessment = assess_schedule(session, actor, project, case_id, data, idempotency_key)
    commit_or_conflict(session, "Schedule assessment idempotency conflict")
    session.refresh(case)
    session.refresh(assessment)
    return ScheduleAssessmentResult(case=case, assessment=assessment)
