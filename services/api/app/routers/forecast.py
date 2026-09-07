from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import ActorContext, get_actor
from app.database import get_db
from app.forecast_schemas import (
    ForecastCreate,
    ForecastPolicyCreate,
    ForecastPolicyRead,
    ForecastRead,
    ForecastResult,
)
from app.generated.taxonomies import ForecastScenarioType, ForecastTarget, ProjectRole
from app.models import ForecastPolicy, ForecastProjection
from app.services.access import get_scoped_project, require_project_roles
from app.services.forecast import (
    create_forecast,
    create_policy,
    forecast_read,
    list_policies,
)

router = APIRouter(prefix="/api/v1/projects/{project_id}", tags=["forecast"])
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


@router.get("/forecast/policies", response_model=list[ForecastPolicyRead])
def get_forecast_policies(project_id: uuid.UUID, session: SessionDep, actor: ActorDep):
    project = scoped_project(session, actor, project_id, READ_ROLES)
    return list_policies(session, project)


@router.post("/forecast/policies", response_model=ForecastPolicyRead, status_code=201)
def add_forecast_policy(
    project_id: uuid.UUID, data: ForecastPolicyCreate, session: SessionDep, actor: ActorDep
) -> ForecastPolicy:
    project = scoped_project(session, actor, project_id, POLICY_ROLES)
    policy = create_policy(session, actor, project, data)
    commit_or_conflict(session, "Forecast policy version conflict")
    session.refresh(policy)
    return policy


@router.get(
    "/decision-cases/{case_id}/forecasts",
    response_model=list[ForecastRead],
)
def get_forecasts(
    project_id: uuid.UUID,
    case_id: uuid.UUID,
    session: SessionDep,
    actor: ActorDep,
    target: ForecastTarget | None = None,
    scenario_type: ForecastScenarioType | None = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[dict]:
    project = scoped_project(session, actor, project_id, READ_ROLES)
    query = select(ForecastProjection).where(
        ForecastProjection.project_id == project.id, ForecastProjection.case_id == case_id
    )
    if target:
        query = query.where(ForecastProjection.target == target)
    if scenario_type:
        query = query.where(ForecastProjection.scenario_type == scenario_type)
    forecasts = list(
        session.scalars(
            query.order_by(ForecastProjection.forecast_number).offset(offset).limit(limit)
        )
    )
    return [forecast_read(session, value) for value in forecasts]


@router.post(
    "/decision-cases/{case_id}/forecasts",
    response_model=ForecastResult,
    status_code=201,
)
def add_forecast(
    project_id: uuid.UUID,
    case_id: uuid.UUID,
    data: ForecastCreate,
    session: SessionDep,
    actor: ActorDep,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=200)],
) -> ForecastResult:
    project = scoped_project(session, actor, project_id, ANALYSIS_ROLES)
    case, forecast = create_forecast(session, actor, project, case_id, data, idempotency_key)
    commit_or_conflict(session, "Forecast idempotency conflict")
    session.refresh(case)
    session.refresh(forecast)
    return ForecastResult(case=case, forecast=forecast_read(session, forecast))
