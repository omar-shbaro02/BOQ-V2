from __future__ import annotations

import uuid
from typing import Any

from app.auth import ActorContext
from app.models import OutboxEvent, Project
from sqlalchemy.orm import Session


def publish_domain_event(
    session: Session,
    actor: ActorContext,
    project: Project,
    *,
    event_type: str,
    aggregate_type: str,
    aggregate_id: uuid.UUID,
    aggregate_version: int,
    payload: dict[str, Any],
    causation_id: uuid.UUID | None = None,
) -> OutboxEvent:
    event = OutboxEvent(
        event_id=uuid.uuid4(),
        organization_id=project.organization_id,
        project_id=project.id,
        event_type=event_type,
        schema_version="1.0.0",
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        aggregate_version=aggregate_version,
        actor_id=actor.actor_id,
        correlation_id=uuid.uuid4(),
        causation_id=causation_id,
        data_classification="INTERNAL",
        payload=payload,
    )
    session.add(event)
    return event
