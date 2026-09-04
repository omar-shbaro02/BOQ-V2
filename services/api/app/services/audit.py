import uuid
from typing import Any

from app.auth import ActorContext
from app.models import AuditEvent
from sqlalchemy.orm import Session


def record_audit(
    session: Session,
    actor: ActorContext,
    *,
    organization_id: uuid.UUID,
    project_id: uuid.UUID | None,
    action: str,
    object_type: str,
    object_id: str,
    object_version: int | None = None,
    authority_result: str = "AUTHORIZED",
    details: dict[str, Any] | None = None,
) -> AuditEvent:
    event = AuditEvent(
        organization_id=organization_id,
        project_id=project_id,
        actor_id=actor.actor_id,
        actor_type="HUMAN",
        action=action,
        object_type=object_type,
        object_id=object_id,
        object_version=object_version,
        correlation_id=uuid.uuid4(),
        authority_result=authority_result,
        details=details or {},
    )
    session.add(event)
    return event
