import uuid
from dataclasses import dataclass
from typing import Annotated

from fastapi import Cookie, Header, HTTPException, status

from app.config import get_settings
from app.generated.taxonomies import ProjectRole


@dataclass(frozen=True, slots=True)
class ActorContext:
    actor_id: str
    organization_id: uuid.UUID | None
    asserted_roles: frozenset[ProjectRole]
    principal_type: str = "HUMAN"


def get_actor(
    actor_id: Annotated[str | None, Header(alias="X-VAI-Actor-ID")] = None,
    organization_header: Annotated[uuid.UUID | None, Header(alias="X-VAI-Organization-ID")] = None,
    roles: Annotated[str | None, Header(alias="X-VAI-Roles")] = None,
    authorization: Annotated[str | None, Header()] = None,
    session_cookie: Annotated[str | None, Cookie(alias="__Host-vai-session")] = None,
) -> ActorContext:
    settings = get_settings()
    if settings.environment not in {"development", "test"}:
        from app.oidc import principal_type, verified_claims
        from app.web_sessions import session_access_token

        browser_session = authorization is None and bool(session_cookie)
        if browser_session:
            authorization = f"Bearer {session_access_token(settings, session_cookie)}"
        claims = verified_claims(settings, authorization)
        subject = claims["sub"]
        organization_id = uuid.UUID(claims[settings.oidc_organization_claim])
        identity_kind = principal_type(settings, claims)
        if browser_session and identity_kind != "SERVICE":
            # Only the code/nonce/ID-token verified callback can issue this encrypted cookie.
            identity_kind = "HUMAN"
        if organization_header is not None and organization_header != organization_id:
            raise HTTPException(403, "Organization scope denied")
        return ActorContext(subject, organization_id, frozenset(), identity_kind)
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
        principal_type="SERVICE" if ProjectRole.SYSTEM_SERVICE in asserted else "HUMAN",
    )
