import uuid
from datetime import UTC, datetime

from app.auth import ActorContext
from app.generated.taxonomies import SemanticState
from app.models import AuthorizedContextVersion, Project
from app.schemas import ContextActivation, ContextVersionCreate
from app.services.audit import record_audit
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session


def next_version_number(session: Session, project_id: uuid.UUID, context_type: str) -> int:
    current = session.scalar(
        select(func.max(AuthorizedContextVersion.version_number)).where(
            AuthorizedContextVersion.project_id == project_id,
            AuthorizedContextVersion.context_type == context_type,
        )
    )
    return (current or 0) + 1


def create_source_version(
    session: Session, actor: ActorContext, project: Project, data: ContextVersionCreate
) -> AuthorizedContextVersion:
    version = AuthorizedContextVersion(
        id=uuid.uuid4(),
        organization_id=project.organization_id,
        project_id=project.id,
        context_type=data.context_type.value,
        version_number=next_version_number(session, project.id, data.context_type.value),
        semantic_state=data.semantic_state.value,
        effective_from=data.effective_from,
        payload=data.payload,
        created_by=actor.actor_id,
    )
    session.add(version)
    record_audit(
        session,
        actor,
        organization_id=project.organization_id,
        project_id=project.id,
        action="AUTHORIZED_CONTEXT_SOURCE_CREATED",
        object_type="AUTHORIZED_CONTEXT_VERSION",
        object_id=str(version.id),
        object_version=version.version_number,
        details={"state": version.semantic_state, "context_type": version.context_type},
    )
    return version


def activate_source_version(
    session: Session, actor: ActorContext, project: Project, data: ContextActivation
) -> AuthorizedContextVersion:
    source = session.get(AuthorizedContextVersion, data.source_version_id)
    if source is None or source.project_id != project.id:
        raise HTTPException(status_code=404, detail="Context source version not found")
    if source.semantic_state not in {SemanticState.BASELINE, SemanticState.PROPOSED}:
        raise HTTPException(
            status_code=409, detail="Only BASELINE or PROPOSED sources can activate"
        )

    now = datetime.now(UTC)
    current = session.scalar(
        select(AuthorizedContextVersion)
        .where(
            AuthorizedContextVersion.project_id == project.id,
            AuthorizedContextVersion.context_type == source.context_type,
            AuthorizedContextVersion.semantic_state == SemanticState.CURRENT_AUTHORIZED,
        )
        .with_for_update()
    )
    if current is not None:
        current.semantic_state = SemanticState.SUPERSEDED
        current.superseded_at = now

    activated = AuthorizedContextVersion(
        id=uuid.uuid4(),
        organization_id=project.organization_id,
        project_id=project.id,
        context_type=source.context_type,
        version_number=next_version_number(session, project.id, source.context_type),
        semantic_state=SemanticState.CURRENT_AUTHORIZED,
        effective_from=source.effective_from,
        payload=source.payload,
        created_by=source.created_by,
        source_version_id=source.id,
        approval_reference=data.approval_reference,
        activation_reason=data.reason,
        activated_by=actor.actor_id,
        activated_at=now,
    )
    session.add(activated)
    record_audit(
        session,
        actor,
        organization_id=project.organization_id,
        project_id=project.id,
        action="AUTHORIZED_CONTEXT_ACTIVATED",
        object_type="AUTHORIZED_CONTEXT_VERSION",
        object_id=str(activated.id),
        object_version=activated.version_number,
        details={
            "source_version_id": str(source.id),
            "approval_reference": data.approval_reference,
            "superseded_version_id": str(current.id) if current else None,
        },
    )
    return activated
