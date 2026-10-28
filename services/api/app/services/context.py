import hashlib
import json
import uuid
from datetime import UTC, datetime

from app.auth import ActorContext
from app.generated.taxonomies import AuthorizedContextType, ControlledObjectType, SemanticState
from app.models import (
    AuditEvent,
    AuthorityGrant,
    AuthorizedContextVersion,
    ControlledObject,
    Project,
)
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
    if data.context_type == AuthorizedContextType.PROGRESS_WEIGHTING:
        requested_codes = {entry["controlled_object_code"] for entry in data.payload["entries"]}
        valid_codes = set(
            session.scalars(
                select(ControlledObject.code).where(
                    ControlledObject.project_id == project.id,
                    ControlledObject.object_type == ControlledObjectType.WORK_PACKAGE,
                    ControlledObject.active.is_(True),
                    ControlledObject.code.in_(requested_codes),
                )
            )
        )
        unknown_codes = sorted(requested_codes - valid_codes)
        if unknown_codes:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Progress weights require active project work packages; unknown codes: "
                    + ", ".join(unknown_codes)
                ),
            )
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
    session: Session,
    actor: ActorContext,
    project: Project,
    data: ContextActivation,
    *,
    idempotency_key: str,
    governed_change_grant: AuthorityGrant | None = None,
) -> AuthorizedContextVersion:
    session.execute(select(Project.id).where(Project.id == project.id).with_for_update())
    request_hash = hashlib.sha256(
        json.dumps(
            {
                "actor_id": actor.actor_id,
                "command": data.model_dump(mode="json"),
                "governed_change_grant_id": str(governed_change_grant.id)
                if governed_change_grant
                else None,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    replay = session.scalar(
        select(AuditEvent).where(
            AuditEvent.project_id == project.id,
            AuditEvent.action == "AUTHORIZED_CONTEXT_ACTIVATED",
            AuditEvent.details["idempotency_key"].as_string() == idempotency_key,
        )
    )
    if replay:
        if replay.details.get("request_hash") != request_hash:
            raise HTTPException(409, "Idempotency key payload or actor mismatch")
        previous = session.get(AuthorizedContextVersion, uuid.UUID(replay.object_id))
        if previous is None:
            raise HTTPException(409, "Activation replay provenance is unavailable")
        return previous
    source = session.get(AuthorizedContextVersion, data.source_version_id)
    if source is None or source.project_id != project.id:
        raise HTTPException(status_code=404, detail="Context source version not found")
    if source.semantic_state not in {SemanticState.BASELINE, SemanticState.PROPOSED}:
        raise HTTPException(
            status_code=409, detail="Only BASELINE or PROPOSED sources can activate"
        )

    expected_type = {
        "SCHEDULE": "BASELINE_SCHEDULE_APPROVAL"
        if source.semantic_state == SemanticState.BASELINE
        else "CURRENT_SCHEDULE_APPROVAL",
        "BUDGET": "BUDGET_APPROVAL",
        "BOQ": "BOQ_APPROVAL",
        "PROGRESS_WEIGHTING": "PROGRESS_WEIGHTING_APPROVAL",
    }[source.context_type]
    grant = governed_change_grant or (
        session.get(AuthorityGrant, data.authority_grant_id) if data.authority_grant_id else None
    )
    if governed_change_grant is not None:
        expected_type = "CHANGE_APPROVAL"
    today = datetime.now(UTC).date()
    if (
        actor.principal_type != "HUMAN"
        or grant is None
        or grant.project_id != project.id
        or grant.organization_id != project.organization_id
        or grant.actor_id != actor.actor_id
        or not grant.active
        or grant.authority_type != expected_type
        or grant.controlled_object_id is not None
        or grant.max_amount is not None
        or (grant.valid_from and today < grant.valid_from)
        or (grant.valid_until and today > grant.valid_until)
    ):
        raise HTTPException(
            403, "Matching active project-wide context approval authority is required"
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
    if (current.id if current else None) != data.expected_current_context_id:
        raise HTTPException(
            409, "Authorized context changed; review the current version before approval"
        )
    if current is not None:
        current.semantic_state = SemanticState.SUPERSEDED
        current.superseded_at = now
        session.flush()

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
            "authority_grant_id": str(grant.id),
            "idempotency_key": idempotency_key,
            "request_hash": request_hash,
            "authority_scope": {
                "authority_type": grant.authority_type,
                "actor_id": grant.actor_id,
                "project_id": str(grant.project_id),
                "controlled_object_id": None,
                "max_amount": None,
                "valid_from": grant.valid_from.isoformat() if grant.valid_from else None,
                "valid_until": grant.valid_until.isoformat() if grant.valid_until else None,
            },
        },
    )
    return activated
