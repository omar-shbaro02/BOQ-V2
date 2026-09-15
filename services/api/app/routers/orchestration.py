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
from app.models import OrchestrationRun, SpecialistContradictionResolution, SpecialistRun
from app.orchestration_schemas import (
    ContradictionResolutionCreate,
    ContradictionResolutionRead,
    ContradictionResolutionResult,
    NarrativeValidationCreate,
    NarrativeValidationRead,
    OrchestrationCreate,
    OrchestrationResult,
    OrchestrationRunRead,
)
from app.services.access import get_scoped_project, require_project_roles
from app.services.cases import scoped_case
from app.services.orchestration import (
    create_contradiction_resolution,
    create_orchestration_run,
    validate_narrative,
)

router = APIRouter(prefix="/api/v1/projects/{project_id}", tags=["orchestration"])
SessionDep = Annotated[Session, Depends(get_db)]
ActorDep = Annotated[ActorContext, Depends(get_actor)]
READ_ROLES = set(ProjectRole)
RUN_ROLES = {
    ProjectRole.ORGANIZATION_ADMIN,
    ProjectRole.PROJECT_ADMIN,
    ProjectRole.ANALYST_CONTROLLER,
    ProjectRole.DECISION_OWNER,
}
RESOLUTION_ROLES = {
    ProjectRole.ORGANIZATION_ADMIN,
    ProjectRole.PROJECT_ADMIN,
    ProjectRole.DECISION_OWNER,
    ProjectRole.APPROVER_ESCALATION_AUTHORITY,
}


def project_scope(session: Session, actor: ActorContext, project_id: uuid.UUID, roles: set):
    project = get_scoped_project(session, actor, project_id)
    require_project_roles(session, actor, project, roles)
    return project


def run_read(session: Session, run: OrchestrationRun) -> dict:
    specialists = list(
        session.scalars(
            select(SpecialistRun)
            .where(SpecialistRun.orchestration_run_id == run.id)
            .order_by(SpecialistRun.specialist_kind)
        )
    )
    value = {column.name: getattr(run, column.name) for column in run.__table__.columns}
    value["specialist_runs"] = specialists
    return value


@router.get(
    "/decision-cases/{case_id}/orchestration-runs",
    response_model=list[OrchestrationRunRead],
)
def get_runs(
    project_id: uuid.UUID, case_id: uuid.UUID, session: SessionDep, actor: ActorDep
) -> list[dict]:
    project = project_scope(session, actor, project_id, READ_ROLES)
    scoped_case(session, project, case_id)
    runs = list(
        session.scalars(
            select(OrchestrationRun)
            .where(OrchestrationRun.project_id == project.id, OrchestrationRun.case_id == case_id)
            .order_by(OrchestrationRun.run_number)
        )
    )
    return [run_read(session, run) for run in runs]


@router.get(
    "/decision-cases/{case_id}/contradiction-resolutions",
    response_model=list[ContradictionResolutionRead],
)
def get_resolutions(
    project_id: uuid.UUID, case_id: uuid.UUID, session: SessionDep, actor: ActorDep
) -> list[SpecialistContradictionResolution]:
    project = project_scope(session, actor, project_id, READ_ROLES)
    scoped_case(session, project, case_id)
    return list(
        session.scalars(
            select(SpecialistContradictionResolution)
            .where(
                SpecialistContradictionResolution.project_id == project.id,
                SpecialistContradictionResolution.case_id == case_id,
            )
            .order_by(SpecialistContradictionResolution.resolved_at)
        )
    )


@router.post(
    "/decision-cases/{case_id}/orchestration-runs/{run_id}/validate-narrative",
    response_model=NarrativeValidationRead,
)
def check_narrative(
    project_id: uuid.UUID,
    case_id: uuid.UUID,
    run_id: uuid.UUID,
    data: NarrativeValidationCreate,
    session: SessionDep,
    actor: ActorDep,
) -> dict:
    project = project_scope(session, actor, project_id, READ_ROLES)
    scoped_case(session, project, case_id)
    run = session.get(OrchestrationRun, run_id)
    if run is None or run.case_id != case_id:
        raise HTTPException(status_code=404, detail="Orchestration run not found")
    return validate_narrative(run, data.narrative)


@router.post(
    "/decision-cases/{case_id}/orchestration-runs/{run_id}/contradiction-resolutions",
    response_model=ContradictionResolutionResult,
    status_code=201,
)
def add_resolution(
    project_id: uuid.UUID,
    case_id: uuid.UUID,
    run_id: uuid.UUID,
    data: ContradictionResolutionCreate,
    session: SessionDep,
    actor: ActorDep,
) -> ContradictionResolutionResult:
    project = project_scope(session, actor, project_id, RESOLUTION_ROLES)
    case, resolution = create_contradiction_resolution(
        session, actor, project, case_id, run_id, data
    )
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Resolution conflict"
        ) from exc
    session.refresh(case)
    session.refresh(resolution)
    return ContradictionResolutionResult(case=case, resolution=resolution)


@router.post(
    "/decision-cases/{case_id}/orchestration-runs",
    response_model=OrchestrationResult,
    status_code=201,
)
def add_run(
    project_id: uuid.UUID,
    case_id: uuid.UUID,
    data: OrchestrationCreate,
    session: SessionDep,
    actor: ActorDep,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=200)],
) -> OrchestrationResult:
    project = project_scope(session, actor, project_id, RUN_ROLES)
    case, run, _ = create_orchestration_run(session, actor, project, case_id, data, idempotency_key)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Run conflict") from exc
    session.refresh(case)
    session.refresh(run)
    return OrchestrationResult(case=case, run=run_read(session, run))
