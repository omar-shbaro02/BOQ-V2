"""Uniform tenant/membership boundary before protected route payloads and resource lookups."""

import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import ActorContext, get_actor
from app.config import get_settings
from app.database import get_db
from app.generated.taxonomies import ProjectRole
from app.human_commands import is_human_command
from app.models import Membership, Project
from app.services.access import get_scoped_project, require_organization, require_project_roles


def require_local_preview() -> None:
    if get_settings().environment not in {"development", "test"}:
        raise HTTPException(403, "Local preview tools are unavailable outside development/test")


def require_route_scope(
    request: Request,
    actor: Annotated[ActorContext, Depends(get_actor)],
    session: Annotated[Session, Depends(get_db)],
) -> Project | None:
    project_value = request.path_params.get("project_id")
    organization_value = request.path_params.get("organization_id")
    try:
        if project_value is not None:
            project = get_scoped_project(session, actor, uuid.UUID(str(project_value)))
            roles = require_project_roles(session, actor, project, set(ProjectRole))
            if is_human_command(request.method, request.url.path) and (
                actor.principal_type != "HUMAN" or ProjectRole.SYSTEM_SERVICE in roles
            ):
                raise HTTPException(403, "Human principal required for this reserved command")
            return project
        if organization_value is not None:
            organization_id = uuid.UUID(str(organization_value))
            require_organization(actor, organization_id)
            member = session.scalar(
                select(Membership.id)
                .where(
                    Membership.organization_id == organization_id,
                    Membership.actor_id == actor.actor_id,
                    Membership.active.is_(True),
                    Membership.role.in_([role.value for role in ProjectRole]),
                )
                .limit(1)
            )
            if member is None:
                raise HTTPException(403, "Organization membership denied")
            if is_human_command(request.method, request.url.path):
                service = session.scalar(
                    select(Membership.id)
                    .where(
                        Membership.organization_id == organization_id,
                        Membership.actor_id == actor.actor_id,
                        Membership.active.is_(True),
                        Membership.role == ProjectRole.SYSTEM_SERVICE,
                    )
                    .limit(1)
                )
                if actor.principal_type != "HUMAN" or service is not None:
                    raise HTTPException(403, "Human principal required for this reserved command")
    except ValueError as exc:
        raise HTTPException(422, "Invalid project or organization identifier") from exc
    return None
