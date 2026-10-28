import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import ActorContext, get_actor
from app.database import get_db
from app.generated.taxonomies import ProjectRole
from app.models import PresentationArtifact
from app.presentation_schemas import (
    PresentationCreate,
    PresentationEventRead,
    PresentationRead,
    PresentationTransition,
)
from app.routers.control_context import commit_or_conflict
from app.services.access import get_scoped_project, require_project_roles
from app.services.audit import record_audit
from app.services.presentations import (
    create_presentation,
    presentation_read,
    read_presentation_content,
    scoped_presentation,
    transition_presentation,
)
from app.storage import EvidenceStore, get_evidence_store

router = APIRouter(prefix="/api/v1/projects/{project_id}/decision-center", tags=["presentations"])
SessionDep = Annotated[Session, Depends(get_db)]
ActorDep = Annotated[ActorContext, Depends(get_actor)]
StoreDep = Annotated[EvidenceStore, Depends(get_evidence_store)]
Key = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=200)]
WRITE_ROLES = {
    ProjectRole.ORGANIZATION_ADMIN,
    ProjectRole.PROJECT_ADMIN,
    ProjectRole.ANALYST_CONTROLLER,
    ProjectRole.DECISION_OWNER,
    ProjectRole.APPROVER_ESCALATION_AUTHORITY,
}


def project_scope(session, actor, project_id, roles):
    project = get_scoped_project(session, actor, project_id)
    require_project_roles(session, actor, project, roles)
    return project


@router.post("/presentations", response_model=PresentationRead, status_code=201)
def add_presentation(
    project_id: uuid.UUID,
    data: PresentationCreate,
    session: SessionDep,
    actor: ActorDep,
    store: StoreDep,
    idempotency_key: Key,
) -> dict:
    project = project_scope(session, actor, project_id, WRITE_ROLES)
    record, created = create_presentation(session, actor, project, data, idempotency_key, store)
    storage_key = record.storage_key
    try:
        commit_or_conflict(session, "Presentation request conflict")
    except Exception:
        if created:
            store.delete(storage_key)
        raise
    return presentation_read(session, record)


@router.get("/presentations", response_model=list[PresentationRead])
def list_presentations(project_id: uuid.UUID, session: SessionDep, actor: ActorDep) -> list[dict]:
    project = project_scope(session, actor, project_id, set(ProjectRole))
    return [
        presentation_read(session, item)
        for item in session.scalars(
            select(PresentationArtifact)
            .where(PresentationArtifact.project_id == project.id)
            .order_by(PresentationArtifact.generated_at.desc())
        )
    ]


@router.get("/presentations/{presentation_id}", response_model=PresentationRead)
def get_presentation(
    project_id: uuid.UUID, presentation_id: uuid.UUID, session: SessionDep, actor: ActorDep
) -> dict:
    project = project_scope(session, actor, project_id, set(ProjectRole))
    return presentation_read(session, scoped_presentation(session, project, presentation_id))


@router.post(
    "/presentations/{presentation_id}/lifecycle-events",
    response_model=PresentationEventRead,
    status_code=201,
)
def add_presentation_transition(
    project_id: uuid.UUID,
    presentation_id: uuid.UUID,
    data: PresentationTransition,
    session: SessionDep,
    actor: ActorDep,
    store: StoreDep,
    idempotency_key: Key,
) -> object:
    project = project_scope(session, actor, project_id, WRITE_ROLES)
    event = transition_presentation(
        session,
        actor,
        project,
        scoped_presentation(session, project, presentation_id),
        data,
        idempotency_key,
        store,
    )
    commit_or_conflict(session, "Presentation lifecycle conflict")
    return event


def content_response(project_id, presentation_id, session, actor, store, approved):
    project = project_scope(session, actor, project_id, set(ProjectRole))
    record = scoped_presentation(session, project, presentation_id)
    if approved and presentation_read(session, record)["lifecycle_status"] != "APPROVED":
        raise HTTPException(409, "Presentation is not approved for external use")
    content = read_presentation_content(record, store)
    record_audit(
        session,
        actor,
        organization_id=project.organization_id,
        project_id=project.id,
        action="PRESENTATION_APPROVED_DOWNLOAD" if approved else "PRESENTATION_REVIEW_DOWNLOAD",
        object_type="PRESENTATION_ARTIFACT",
        object_id=str(record.id),
        details={"content_hash": record.content_hash},
    )
    commit_or_conflict(session, "Presentation export audit failed")
    return Response(
        content,
        media_type="text/html",
        headers={
            "Content-Disposition": f'attachment; filename="project-presentation-{record.id}.html"',
            "X-Content-Type-Options": "nosniff",
            "X-VAI-Content-SHA256": record.content_hash,
            "X-VAI-Source-Report": str(record.report_snapshot_id),
            "Cache-Control": "private, no-store",
        },
    )


@router.get("/presentations/{presentation_id}/content")
def get_review_content(
    project_id: uuid.UUID,
    presentation_id: uuid.UUID,
    session: SessionDep,
    actor: ActorDep,
    store: StoreDep,
) -> Response:
    return content_response(project_id, presentation_id, session, actor, store, False)


@router.get("/approved-presentations/{presentation_id}/content")
def get_approved_content(
    project_id: uuid.UUID,
    presentation_id: uuid.UUID,
    session: SessionDep,
    actor: ActorDep,
    store: StoreDep,
) -> Response:
    return content_response(project_id, presentation_id, session, actor, store, True)
