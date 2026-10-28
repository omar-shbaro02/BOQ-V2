import hashlib
import uuid
from datetime import UTC, datetime

from app.auth import ActorContext
from app.models import (
    AuthorityGrant,
    PresentationArtifact,
    PresentationLifecycleEvent,
    Project,
    ReportSnapshot,
)
from app.presentation_schemas import PresentationCreate, PresentationTransition
from app.services.audit import record_audit
from app.services.control_metrics import shared_metrics
from app.services.presentation_render import (
    GENERATOR_VERSION,
    build_presentation,
    digest,
    inspect_source,
)
from app.services.project_context import project_lock
from app.services.reports import lifecycle_events
from app.storage import EvidenceStore
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session


def scoped_presentation(
    session: Session, project: Project, presentation_id: uuid.UUID
) -> PresentationArtifact:
    record = session.get(PresentationArtifact, presentation_id)
    if record is None or record.project_id != project.id:
        raise HTTPException(404, "Presentation not found")
    return record


def presentation_events(
    session: Session, record: PresentationArtifact
) -> list[PresentationLifecycleEvent]:
    return list(
        session.scalars(
            select(PresentationLifecycleEvent)
            .where(PresentationLifecycleEvent.presentation_id == record.id)
            .order_by(PresentationLifecycleEvent.event_number)
        )
    )


def presentation_read(session: Session, record: PresentationArtifact) -> dict:
    history = presentation_events(session, record)
    return {
        **{column.name: getattr(record, column.name) for column in record.__table__.columns},
        "lifecycle_status": history[-1].to_status,
        "lifecycle_events": history,
    }


def create_presentation(
    session: Session,
    actor: ActorContext,
    project: Project,
    data: PresentationCreate,
    key: str,
    store: EvidenceStore,
) -> tuple[PresentationArtifact, bool]:
    project_lock(session, project)
    request_hash = digest(data.model_dump(mode="json"))
    existing = session.scalar(
        select(PresentationArtifact).where(
            PresentationArtifact.project_id == project.id,
            PresentationArtifact.idempotency_key == key,
        )
    )
    if existing:
        if existing.request_hash != request_hash:
            raise HTTPException(409, "Idempotency key payload mismatch")
        return existing, False
    report = session.get(ReportSnapshot, data.report_snapshot_id)
    if report is None or report.project_id != project.id:
        raise HTTPException(404, "Source report not found")
    history = lifecycle_events(session, report.id)
    if not history or history[-1].to_status != "APPROVED":
        raise HTTPException(409, "An approved immutable source report is required")
    if digest(report.payload) != report.content_hash:
        raise HTTPException(409, "Source report content hash mismatch")
    control = report.payload.get("project_control")
    if not control:
        raise HTTPException(409, "Source report has no immutable project-control projection")
    registry = {
        item["id"]: item
        for item in control.get("supporting_context", {}).get("project_context", [])
        if item["record_type"] == "STAKEHOLDER"
        and item["status"] == "ACTIVE"
        and item["payload"].get("report_recipient") is True
    }
    selected = [str(value) for value in sorted(data.recipient_record_ids, key=str)]
    if any(identifier not in registry for identifier in selected):
        raise HTTPException(
            422, "Recipients must be exact active recipient versions frozen in the source report"
        )
    recipients = [registry[identifier] for identifier in selected]
    record_id = uuid.uuid4()
    envelope = {
        "presentation_id": str(record_id),
        "generator_version": GENERATOR_VERSION,
        "source_report_approval_event_id": str(history[-1].id),
        "recipients": recipients,
        "report": {
            "id": str(report.id),
            "report_type": report.report_type,
            "report_date": report.report_date.isoformat(),
            "data_date": report.data_date.isoformat(),
            "content_hash": report.content_hash,
            "payload": report.payload,
            "source_refs": report.source_refs,
            "policy_versions": report.policy_versions,
            "semantic_notice": report.semantic_notice,
            "schema_version": report.schema_version,
            "generator_version": report.generator_version,
            "fidelity_manifest": report.fidelity_manifest,
        },
    }
    try:
        content = build_presentation(envelope)
        source = inspect_source(content)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if source["shared_metrics"] != control.get("shared_metrics", shared_metrics(control)):
        raise HTTPException(409, "Source report/shared metric fidelity mismatch")
    content_hash = hashlib.sha256(content).hexdigest()
    storage_key = (
        f"{project.organization_id}/{project.id}/presentations/{record_id}/{content_hash}.html"
    )
    record = PresentationArtifact(
        id=record_id,
        organization_id=project.organization_id,
        project_id=project.id,
        report_snapshot_id=report.id,
        source_report_approval_event_id=history[-1].id,
        source_report_hash=report.content_hash,
        storage_key=storage_key,
        content_hash=content_hash,
        generator_version=GENERATOR_VERSION,
        recipients=recipients,
        fidelity_manifest={
            "format": "SELF_CONTAINED_HTML_SLIDES",
            "source_report_id": str(report.id),
            "source_report_hash": report.content_hash,
            "shared_metrics": source["shared_metrics"],
            "complete_source_embedded": True,
            "unknown_values_preserved": True,
            "recipient_record_ids": selected,
            "semantic_notice": report.semantic_notice,
        },
        idempotency_key=key,
        request_hash=request_hash,
        generated_by=actor.actor_id,
    )
    session.add(record)
    session.flush()
    store.put(storage_key, content)
    session.add(
        PresentationLifecycleEvent(
            id=uuid.uuid4(),
            organization_id=project.organization_id,
            project_id=project.id,
            presentation_id=record.id,
            event_number=1,
            from_status=None,
            to_status="DRAFT",
            reason="Report-derived presentation generated for human review",
            actor_id=actor.actor_id,
            idempotency_key=f"created:{record.id}",
            request_hash=request_hash,
        )
    )
    record_audit(
        session,
        actor,
        organization_id=project.organization_id,
        project_id=project.id,
        action="PRESENTATION_GENERATED",
        object_type="PRESENTATION_ARTIFACT",
        object_id=str(record.id),
        details={
            "source_report_id": str(report.id),
            "source_report_hash": report.content_hash,
            "content_hash": content_hash,
            "recipient_record_ids": selected,
        },
    )
    return record, True


def read_presentation_content(record: PresentationArtifact, store: EvidenceStore) -> bytes:
    try:
        content = store.get(record.storage_key)
    except (FileNotFoundError, OSError) as exc:
        raise HTTPException(503, "Presentation artifact is unavailable") from exc
    if hashlib.sha256(content).hexdigest() != record.content_hash:
        raise HTTPException(409, "Presentation artifact hash mismatch")
    try:
        source = inspect_source(content)
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(409, "Presentation source fidelity validation failed") from exc
    if (
        source["report"]["id"] != str(record.report_snapshot_id)
        or source["report"]["content_hash"] != record.source_report_hash
        or source["presentation_id"] != str(record.id)
        or source["source_report_approval_event_id"] != str(record.source_report_approval_event_id)
        or source["recipients"] != record.recipients
    ):
        raise HTTPException(409, "Presentation source lineage mismatch")
    return content


def transition_presentation(
    session: Session,
    actor: ActorContext,
    project: Project,
    record: PresentationArtifact,
    data: PresentationTransition,
    key: str,
    store: EvidenceStore,
) -> PresentationLifecycleEvent:
    project_lock(session, project)
    request_hash = digest(
        {"presentation_id": str(record.id), "command": data.model_dump(mode="json")}
    )
    replay = session.scalar(
        select(PresentationLifecycleEvent).where(
            PresentationLifecycleEvent.project_id == project.id,
            PresentationLifecycleEvent.idempotency_key == key,
        )
    )
    if replay:
        if replay.request_hash != request_hash:
            raise HTTPException(409, "Idempotency key payload mismatch")
        return replay
    history = presentation_events(session, record)
    if len(history) != data.expected_version:
        raise HTTPException(409, "Stale presentation lifecycle version")
    if {"DRAFT": "REVIEWED", "REVIEWED": "APPROVED"}.get(history[-1].to_status) != data.to_status:
        raise HTTPException(409, "Invalid presentation lifecycle transition")
    if data.to_status == "APPROVED":
        grant = (
            session.get(AuthorityGrant, data.authority_grant_id)
            if data.authority_grant_id
            else None
        )
        today = datetime.now(UTC).date()
        if (
            grant is None
            or grant.project_id != project.id
            or grant.actor_id != actor.actor_id
            or not grant.active
            or grant.authority_type != "REPORT_APPROVAL"
            or grant.controlled_object_id is not None
            or grant.max_amount is not None
            or (grant.valid_from and today < grant.valid_from)
            or (grant.valid_until and today > grant.valid_until)
        ):
            raise HTTPException(
                403, "Matching active project-wide REPORT_APPROVAL authority is required"
            )
        read_presentation_content(record, store)
    elif data.authority_grant_id is not None:
        raise HTTPException(422, "Authority linkage belongs on the explicit approval command")
    event = PresentationLifecycleEvent(
        id=uuid.uuid4(),
        organization_id=project.organization_id,
        project_id=project.id,
        presentation_id=record.id,
        event_number=len(history) + 1,
        from_status=history[-1].to_status,
        to_status=data.to_status,
        reason=data.reason,
        authority_grant_id=data.authority_grant_id,
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
        action=f"PRESENTATION_{data.to_status}",
        object_type="PRESENTATION_ARTIFACT",
        object_id=str(record.id),
        object_version=event.event_number,
        details={
            "authority_grant_id": str(data.authority_grant_id) if data.authority_grant_id else None
        },
    )
    return event
