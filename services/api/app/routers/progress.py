from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import ActorContext, get_actor
from app.database import get_db
from app.generated.taxonomies import ProgressBasis, ProgressMeasurementKind, ProjectRole
from app.models import ProgressEvaluation, ProgressMeasurement, ProgressThresholdPolicy
from app.progress_schemas import (
    ProgressEvaluationCreate,
    ProgressEvaluationRead,
    ProgressEvaluationResult,
    ProgressMeasurementCreate,
    ProgressMeasurementRead,
    ProgressPolicyCreate,
    ProgressPolicyRead,
)
from app.services.access import get_scoped_project, require_project_roles
from app.services.progress import (
    create_policy,
    evaluate_progress,
    list_policies,
    record_measurement,
)

router = APIRouter(prefix="/api/v1/projects/{project_id}", tags=["progress"])
SessionDep = Annotated[Session, Depends(get_db)]
ActorDep = Annotated[ActorContext, Depends(get_actor)]

READ_ROLES = set(ProjectRole)
MEASUREMENT_ROLES = {
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


@router.get("/progress/policies", response_model=list[ProgressPolicyRead])
def get_progress_policies(
    project_id: uuid.UUID, session: SessionDep, actor: ActorDep
) -> list[dict | ProgressThresholdPolicy]:
    project = scoped_project(session, actor, project_id, READ_ROLES)
    return list_policies(session, project)


@router.post("/progress/policies", response_model=ProgressPolicyRead, status_code=201)
def add_progress_policy(
    project_id: uuid.UUID,
    data: ProgressPolicyCreate,
    session: SessionDep,
    actor: ActorDep,
) -> ProgressThresholdPolicy:
    project = scoped_project(session, actor, project_id, POLICY_ROLES)
    policy = create_policy(session, actor, project, data)
    commit_or_conflict(session, "Progress policy version conflict")
    session.refresh(policy)
    return policy


@router.get("/progress/measurements", response_model=list[ProgressMeasurementRead])
def get_progress_measurements(
    project_id: uuid.UUID,
    session: SessionDep,
    actor: ActorDep,
    controlled_object_id: uuid.UUID | None = None,
    measurement_kind: ProgressMeasurementKind | None = None,
    measurement_basis: ProgressBasis | None = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[ProgressMeasurement]:
    project = scoped_project(session, actor, project_id, READ_ROLES)
    query = select(ProgressMeasurement).where(ProgressMeasurement.project_id == project.id)
    if controlled_object_id:
        query = query.where(ProgressMeasurement.controlled_object_id == controlled_object_id)
    if measurement_kind:
        query = query.where(ProgressMeasurement.measurement_kind == measurement_kind)
    if measurement_basis:
        query = query.where(ProgressMeasurement.measurement_basis == measurement_basis)
    return list(
        session.scalars(
            query.order_by(ProgressMeasurement.as_of.desc()).offset(offset).limit(limit)
        )
    )


@router.post("/progress/measurements", response_model=ProgressMeasurementRead, status_code=201)
def add_progress_measurement(
    project_id: uuid.UUID,
    data: ProgressMeasurementCreate,
    session: SessionDep,
    actor: ActorDep,
) -> ProgressMeasurement:
    project = scoped_project(session, actor, project_id, MEASUREMENT_ROLES)
    measurement = record_measurement(session, actor, project, data)
    commit_or_conflict(session, "Progress measurement normalization conflict")
    session.refresh(measurement)
    return measurement


@router.get(
    "/decision-cases/{case_id}/progress-evaluations",
    response_model=list[ProgressEvaluationRead],
)
def get_progress_evaluations(
    project_id: uuid.UUID,
    case_id: uuid.UUID,
    session: SessionDep,
    actor: ActorDep,
) -> list[ProgressEvaluation]:
    project = scoped_project(session, actor, project_id, READ_ROLES)
    return list(
        session.scalars(
            select(ProgressEvaluation)
            .where(
                ProgressEvaluation.project_id == project.id,
                ProgressEvaluation.case_id == case_id,
            )
            .order_by(ProgressEvaluation.evaluation_number)
        )
    )


@router.post(
    "/decision-cases/{case_id}/progress-evaluations",
    response_model=ProgressEvaluationResult,
    status_code=201,
)
def add_progress_evaluation(
    project_id: uuid.UUID,
    case_id: uuid.UUID,
    data: ProgressEvaluationCreate,
    session: SessionDep,
    actor: ActorDep,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=200)],
) -> ProgressEvaluationResult:
    project = scoped_project(session, actor, project_id, ANALYSIS_ROLES)
    case, evaluation = evaluate_progress(session, actor, project, case_id, data, idempotency_key)
    commit_or_conflict(session, "Progress evaluation idempotency conflict")
    session.refresh(case)
    session.refresh(evaluation)
    return ProgressEvaluationResult(case=case, evaluation=evaluation)
