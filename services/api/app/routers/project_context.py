import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import ActorContext, get_actor
from app.database import get_db
from app.generated.taxonomies import ProjectRole
from app.models import ProjectContextRecord
from app.project_context_schemas import (
    ProjectContextLifecycleRead,
    ProjectContextRecordCreate,
    ProjectContextRecordRead,
    ProjectContextTransitionCreate,
)
from app.routers.control_context import commit_or_conflict
from app.services.access import get_scoped_project, require_project_roles
from app.services.project_context import create_record, events, scoped_record, transition_record

router = APIRouter(prefix="/api/v1/projects/{project_id}/project-context", tags=["project-context"])
SessionDep = Annotated[Session, Depends(get_db)]
ActorDep = Annotated[ActorContext, Depends(get_actor)]
Key = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=200)]
WRITERS = {
    ProjectRole.ORGANIZATION_ADMIN,
    ProjectRole.PROJECT_ADMIN,
    ProjectRole.DATA_CONTRIBUTOR,
    ProjectRole.ANALYST_CONTROLLER,
}
REVIEWERS = {
    ProjectRole.ORGANIZATION_ADMIN,
    ProjectRole.PROJECT_ADMIN,
    ProjectRole.DECISION_OWNER,
    ProjectRole.APPROVER_ESCALATION_AUTHORITY,
}


def projection(session: Session, record: ProjectContextRecord) -> dict:
    history = events(session, record)
    return {
        **{column.name: getattr(record, column.name) for column in record.__table__.columns},
        "current_status": history[-1].to_status if history else record.initial_status,
        "lifecycle_events": history,
    }


@router.post("/records", response_model=ProjectContextRecordRead, status_code=201)
def post_record(
    project_id: uuid.UUID,
    data: ProjectContextRecordCreate,
    session: SessionDep,
    actor: ActorDep,
    idempotency_key: Key,
) -> dict:
    project = get_scoped_project(session, actor, project_id)
    require_project_roles(session, actor, project, WRITERS)
    record = create_record(session, actor, project, data, idempotency_key)
    commit_or_conflict(session, "Concurrent project context version; reload and retry")
    return projection(session, record)


@router.get("/records", response_model=list[ProjectContextRecordRead])
def list_records(project_id: uuid.UUID, session: SessionDep, actor: ActorDep) -> list[dict]:
    project = get_scoped_project(session, actor, project_id)
    require_project_roles(session, actor, project, set(ProjectRole))
    records = session.scalars(
        select(ProjectContextRecord)
        .where(
            ProjectContextRecord.project_id == project.id,
        )
        .order_by(
            ProjectContextRecord.record_type,
            ProjectContextRecord.record_key,
            ProjectContextRecord.version_number,
        )
    )
    return [projection(session, record) for record in records]


@router.get("/records/{record_id}", response_model=ProjectContextRecordRead)
def read_record(
    project_id: uuid.UUID, record_id: uuid.UUID, session: SessionDep, actor: ActorDep
) -> dict:
    project = get_scoped_project(session, actor, project_id)
    require_project_roles(session, actor, project, set(ProjectRole))
    return projection(session, scoped_record(session, project, record_id))


@router.post(
    "/records/{record_id}/transitions", response_model=ProjectContextLifecycleRead, status_code=201
)
def post_transition(
    project_id: uuid.UUID,
    record_id: uuid.UUID,
    data: ProjectContextTransitionCreate,
    session: SessionDep,
    actor: ActorDep,
    idempotency_key: Key,
    expected_version: Annotated[int, Query(ge=0)],
) -> object:
    project = get_scoped_project(session, actor, project_id)
    require_project_roles(session, actor, project, REVIEWERS)
    event = transition_record(
        session,
        actor,
        project,
        scoped_record(session, project, record_id),
        data,
        idempotency_key,
        expected_version,
    )
    commit_or_conflict(session, "Concurrent context lifecycle; reload and retry")
    return event
