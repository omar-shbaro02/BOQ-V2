import uuid
from dataclasses import dataclass
from typing import Annotated

from fastapi import Header, HTTPException, status

from app.config import get_settings
from app.generated.taxonomies import ProjectRole


@dataclass(frozen=True, slots=True)
class ActorContext:
    actor_id: str
    organization_id: uuid.UUID | None
    asserted_roles: frozenset[ProjectRole]


def get_actor(
    actor_id: Annotated[str | None, Header(alias="X-VAI-Actor-ID")] = None,
    organization_header: Annotated[uuid.UUID | None, Header(alias="X-VAI-Organization-ID")] = None,
    roles: Annotated[str | None, Header(alias="X-VAI-Roles")] = None,
) -> ActorContext:
    if get_settings().environment not in {"development", "test"}:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OIDC identity adapter is required outside development/test",
        )
    if not actor_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Actor identity required"
        )
    try:
        asserted = frozenset(ProjectRole(role.strip()) for role in (roles or "").split(",") if role)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Unknown asserted role") from exc
    return ActorContext(
        actor_id=actor_id,
        organization_id=organization_header,
        asserted_roles=asserted,
    )
