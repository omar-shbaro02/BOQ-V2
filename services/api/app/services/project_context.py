"""Immutable reported context and explicit, separately authorized human lifecycle commands."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from app.auth import ActorContext
from app.models import (
    AuthorityGrant,
    AuthorizedContextVersion,
    EvidenceItem,
    Project,
    ProjectContextLifecycleEvent,
    ProjectContextRecord,
)
from app.project_context_schemas import ProjectContextRecordCreate, ProjectContextTransitionCreate
from app.schemas import ContextActivation
from app.services.audit import record_audit
from app.services.context import activate_source_version
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

TRANSITIONS = {
    "CHARTER": {"DRAFT": {"REVIEWED"}, "REVIEWED": {"APPROVED", "REJECTED"}},
    "STAKEHOLDER": {"ACTIVE": {"RETIRED"}},
    "DAILY_UPDATE": {"REPORTED": {"REVIEWED"}},
    "RISK": {"OPEN": {"MITIGATING", "CLOSED"}, "MITIGATING": {"CLOSED"}, "CLOSED": {"OPEN"}},
    "ISSUE": {"OPEN": {"IN_REVIEW", "RESOLVED"}, "IN_REVIEW": {"RESOLVED"}, "RESOLVED": {"OPEN"}},
    "CHANGE_REQUEST": {"DRAFT": {"REVIEWED"}, "REVIEWED": {"APPROVED", "REJECTED"}},
}


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def scoped_record(session: Session, project: Project, record_id: uuid.UUID) -> ProjectContextRecord:
    record = session.get(ProjectContextRecord, record_id)
    if record is None or record.project_id != project.id:
        raise HTTPException(404, "Project context record not found")
    return record


def events(session: Session, record: ProjectContextRecord) -> list[ProjectContextLifecycleEvent]:
    return list(
        session.scalars(
            select(ProjectContextLifecycleEvent)
            .where(
                ProjectContextLifecycleEvent.record_id == record.id,
            )
            .order_by(ProjectContextLifecycleEvent.event_number)
        )
    )


def project_lock(session: Session, project: Project) -> None:
    session.execute(select(Project).where(Project.id == project.id).with_for_update()).scalar_one()


def create_record(
    session: Session,
    actor: ActorContext,
    project: Project,
    data: ProjectContextRecordCreate,
    key: str,
) -> ProjectContextRecord:
    project_lock(session, project)
    request_hash = digest(data.model_dump(mode="json"))
    existing = session.scalar(
        select(ProjectContextRecord).where(
            ProjectContextRecord.project_id == project.id,
            ProjectContextRecord.idempotency_key == key,
        )
    )
    if existing:
        if existing.request_hash != request_hash:
            raise HTTPException(409, "Idempotency key payload mismatch")
        return existing
    latest = session.scalar(
        select(ProjectContextRecord)
        .where(
            ProjectContextRecord.project_id == project.id,
            ProjectContextRecord.record_type == data.record_type,
            ProjectContextRecord.record_key == data.record_key,
        )
        .order_by(ProjectContextRecord.version_number.desc())
        .limit(1)
    )
    if (latest.id if latest else None) != data.supersedes_record_id:
        raise HTTPException(409, "Exact latest predecessor is required for a new context version")
    if (
        data.record_type in {"DAILY_UPDATE", "RISK", "ISSUE", "CHANGE_REQUEST"}
        and not data.evidence_item_ids
    ):
        raise HTTPException(
            422, "Operational context requires evidence; reported context is not verified"
        )
    cutoff = None
    if data.record_type == "DAILY_UPDATE":
        cutoff = datetime.fromisoformat(data.payload["reporting_cutoff"])
        if (
            cutoff.astimezone(ZoneInfo(project.timezone)).date().isoformat()
            != data.payload["data_date"]
        ):
            raise HTTPException(422, "Reporting cutoff must match the project-local data date")
        if cutoff > datetime.now(UTC):
            raise HTTPException(422, "Daily updates cannot report a future cut-off")
    for item_id in data.evidence_item_ids:
        item = session.get(EvidenceItem, item_id)
        if item is None or item.project_id != project.id or item.status != "ACTIVE":
            raise HTTPException(422, "Evidence must be active and belong to the project")
        item_date = item.as_of.replace(tzinfo=UTC) if item.as_of.tzinfo is None else item.as_of
        if cutoff and item_date > cutoff:
            raise HTTPException(422, "Daily update evidence cannot postdate the reporting cut-off")
    initial = {
        "CHARTER": "DRAFT",
        "STAKEHOLDER": "ACTIVE",
        "DAILY_UPDATE": "REPORTED",
        "CHANGE_REQUEST": "DRAFT",
    }.get(data.record_type, "OPEN")
    record = ProjectContextRecord(
        id=uuid.uuid4(),
        organization_id=project.organization_id,
        project_id=project.id,
        record_type=data.record_type,
        record_key=data.record_key,
        version_number=latest.version_number + 1 if latest else 1,
        supersedes_record_id=data.supersedes_record_id,
        effective_from=data.effective_from,
        initial_status=initial,
        payload=data.payload,
        evidence_item_ids=[str(value) for value in data.evidence_item_ids],
        idempotency_key=key,
        request_hash=request_hash,
        created_by=actor.actor_id,
    )
    session.add(record)
    record_audit(
        session,
        actor,
        organization_id=project.organization_id,
        project_id=project.id,
        action="PROJECT_CONTEXT_RECORDED",
        object_type="PROJECT_CONTEXT_RECORD",
        object_id=str(record.id),
        object_version=record.version_number,
        details={
            "record_type": record.record_type,
            "initial_status": initial,
            "truth_notice": "Reported context; review is not evidence verification",
        },
    )
    return record


def transition_record(
    session: Session,
    actor: ActorContext,
    project: Project,
    record: ProjectContextRecord,
    data: ProjectContextTransitionCreate,
    key: str,
    expected_version: int,
) -> ProjectContextLifecycleEvent:
    project_lock(session, project)
    request_hash = digest(
        {
            "record_id": str(record.id),
            "expected_version": expected_version,
            "command": data.model_dump(mode="json"),
        }
    )
    prior = session.scalar(
        select(ProjectContextLifecycleEvent).where(
            ProjectContextLifecycleEvent.project_id == project.id,
            ProjectContextLifecycleEvent.idempotency_key == key,
        )
    )
    if prior:
        if prior.request_hash != request_hash:
            raise HTTPException(409, "Idempotency key payload mismatch")
        return prior
    history = events(session, record)
    if len(history) != expected_version:
        raise HTTPException(409, "Stale lifecycle version")
    latest = session.scalar(
        select(ProjectContextRecord)
        .where(
            ProjectContextRecord.project_id == project.id,
            ProjectContextRecord.record_type == record.record_type,
            ProjectContextRecord.record_key == record.record_key,
        )
        .order_by(ProjectContextRecord.version_number.desc())
        .limit(1)
    )
    if latest.id != record.id:
        raise HTTPException(409, "Superseded context versions cannot change lifecycle")
    current = history[-1].to_status if history else record.initial_status
    if data.to_status not in TRANSITIONS[record.record_type].get(current, set()):
        raise HTTPException(409, "Invalid project context lifecycle transition")
    authorized_id = None
    approving = data.to_status == "APPROVED"
    if not approving and (
        data.authority_grant_id
        or data.authorized_context_source_version_id
        or data.approval_reference
    ):
        raise HTTPException(422, "Authorization fields are only valid on approval commands")
    if approving:
        grant = (
            session.get(AuthorityGrant, data.authority_grant_id)
            if data.authority_grant_id
            else None
        )
        today = datetime.now(UTC).date()
        required = "CHARTER_APPROVAL" if record.record_type == "CHARTER" else "CHANGE_APPROVAL"
        if (
            grant is None
            or grant.project_id != project.id
            or grant.actor_id != actor.actor_id
            or not grant.active
            or grant.authority_type != required
            or grant.controlled_object_id is not None
            or grant.max_amount is not None
            or (grant.valid_from and grant.valid_from > today)
            or (grant.valid_until and grant.valid_until < today)
        ):
            raise HTTPException(
                403, "Matching active project-wide human approval authority is required"
            )
        if not data.approval_reference:
            raise HTTPException(422, "Approval reference is required")
        if record.record_type == "CHANGE_REQUEST":
            current_context = session.scalar(
                select(AuthorizedContextVersion).where(
                    AuthorizedContextVersion.project_id == project.id,
                    AuthorizedContextVersion.context_type
                    == record.payload["affected_context_type"],
                    AuthorizedContextVersion.semantic_state == "CURRENT_AUTHORIZED",
                )
            )
            if (str(current_context.id) if current_context else None) != record.payload.get(
                "expected_authorized_context_id"
            ):
                raise HTTPException(
                    409, "Authorized context changed since the change request was recorded"
                )
            source = (
                session.get(AuthorizedContextVersion, data.authorized_context_source_version_id)
                if data.authorized_context_source_version_id
                else None
            )
            if (
                source is None
                or source.project_id != project.id
                or source.context_type != record.payload["affected_context_type"]
                or source.semantic_state != "PROPOSED"
            ):
                raise HTTPException(
                    422, "Approved change requires an exact matching proposed context"
                )
            if session.scalar(
                select(AuthorizedContextVersion.id)
                .where(
                    AuthorizedContextVersion.source_version_id == source.id,
                )
                .limit(1)
            ):
                raise HTTPException(409, "Proposed context has already been authorized")
            authorized = activate_source_version(
                session,
                actor,
                project,
                ContextActivation(
                    source_version_id=source.id,
                    authority_grant_id=grant.id,
                    expected_current_context_id=current_context.id if current_context else None,
                    approval_reference=data.approval_reference,
                    reason=data.reason,
                ),
                idempotency_key="change:" + hashlib.sha256(key.encode()).hexdigest(),
                governed_change_grant=grant,
            )
            authorized_id = authorized.id
        elif data.authorized_context_source_version_id:
            raise HTTPException(422, "Charter approval cannot activate schedule or budget context")
    event = ProjectContextLifecycleEvent(
        id=uuid.uuid4(),
        organization_id=project.organization_id,
        project_id=project.id,
        record_id=record.id,
        event_number=len(history) + 1,
        from_status=current,
        to_status=data.to_status,
        reason=data.reason,
        authority_grant_id=data.authority_grant_id,
        authorized_context_id=authorized_id,
        actor_id=actor.actor_id,
        idempotency_key=key,
        request_hash=request_hash,
    )
    session.add(event)
    record_audit(
        session,
        actor,
        organization_id=project.organization_id,
        project_id=project.id,
        action="PROJECT_CONTEXT_TRANSITIONED",
        object_type="PROJECT_CONTEXT_RECORD",
        object_id=str(record.id),
        object_version=event.event_number,
        details={
            "from_status": current,
            "to_status": data.to_status,
            "authority_grant_id": str(data.authority_grant_id) if data.authority_grant_id else None,
            "authorized_context_id": str(authorized_id) if authorized_id else None,
        },
    )
    return event
