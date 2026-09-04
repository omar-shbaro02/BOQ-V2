import uuid
from collections.abc import Iterable

from app.auth import ActorContext
from app.generated.taxonomies import ProjectRole
from app.models import Membership, Project
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session


def require_organization(actor: ActorContext, organization_id: uuid.UUID) -> None:
    if actor.organization_id != organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Organization scope denied"
        )


def require_project_roles(
    session: Session,
    actor: ActorContext,
    project: Project,
    roles: Iterable[ProjectRole],
) -> set[ProjectRole]:
    require_organization(actor, project.organization_id)
    allowed = {role.value for role in roles}
    query = select(Membership.role).where(
        Membership.organization_id == project.organization_id,
        Membership.actor_id == actor.actor_id,
        Membership.active.is_(True),
        Membership.role.in_(allowed),
        (Membership.project_id == project.id) | (Membership.project_id.is_(None)),
    )
    found = {ProjectRole(value) for value in session.scalars(query)}
    if not found:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Project role denied")
    return found


def get_scoped_project(session: Session, actor: ActorContext, project_id: uuid.UUID) -> Project:
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    require_organization(actor, project.organization_id)
    return project
