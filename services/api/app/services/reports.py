from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from app.auth import ActorContext
from app.decision_center_schemas import ReportLifecycleCreate, ReportSnapshotCreate
from app.models import (
    AuthorityGrant,
    Project,
    ProjectControlSnapshot,
    ReportLifecycleEvent,
    ReportSnapshot,
)
from app.services.audit import record_audit
from app.services.cases import scoped_case
from app.services.control_metrics import shared_metrics
from app.services.decision_center import (
    REPORT_NOTICE,
    case_dossier,
    conformity_report,
    decision_queue,
    exception_report,
    pilot_kpi_report,
    weekly_brief,
)
from app.services.project_context import project_lock
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

GENERATOR_VERSION = "GOVERNED-REPORT-1.1.0"


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _serialize_control(snapshot: ProjectControlSnapshot) -> dict[str, Any]:
    return {
        "id": str(snapshot.id),
        "snapshot_number": snapshot.snapshot_number,
        "data_date": snapshot.data_date.isoformat(),
        "planned_ratio": str(snapshot.planned_ratio),
        "actual_ratio": str(snapshot.actual_ratio),
        "variance_ratio": str(snapshot.variance_ratio),
        "progress_status": snapshot.progress_status,
        "confidence": str(snapshot.confidence),
        "limitations": snapshot.limitations,
        "package_results": snapshot.package_results,
        "cost_assessment_refs": snapshot.cost_assessment_refs,
        "forecast_projection_refs": snapshot.forecast_projection_refs,
        "supporting_context": snapshot.supporting_context,
        "health": snapshot.health,
        "shared_metrics": shared_metrics(snapshot),
    }


def _projection(
    session: Session,
    actor: ActorContext,
    project: Project,
    data: ReportSnapshotCreate,
    report_date: datetime,
) -> dict[str, Any]:
    if data.report_type == "CASE_DOSSIER":
        return case_dossier(
            session, actor, project, scoped_case(session, project, data.case_id), report_date
        ).payload
    builders = {
        "WEEKLY_DECISION_BRIEF": weekly_brief,
        "PROJECT_CONTROL_EXCEPTION_REPORT": exception_report,
        "PILOT_KPI_REPORT": pilot_kpi_report,
        "GOVERNANCE_CONFORMITY_REPORT": conformity_report,
    }
    if data.report_type in builders:
        return builders[data.report_type](session, actor, project, report_date).payload
    queue = [item.model_dump(mode="json") for item in decision_queue(session, project)]
    return {
        "reporting_scope": "MONTHLY_EXECUTIVE"
        if data.report_type == "MONTHLY_EXECUTIVE_REPORT"
        else "ON_DEMAND_STATUS",
        "decision_queue": queue,
    }


def create_report(
    session: Session,
    actor: ActorContext,
    project: Project,
    data: ReportSnapshotCreate,
    idempotency_key: str,
) -> ReportSnapshot:
    project_lock(session, project)
    request_hash = _digest(data.model_dump(mode="json"))
    existing = session.scalar(
        select(ReportSnapshot).where(
            ReportSnapshot.project_id == project.id,
            ReportSnapshot.idempotency_key == idempotency_key,
        )
    )
    if existing:
        if existing.request_hash != request_hash:
            raise HTTPException(status_code=409, detail="Idempotency key payload mismatch")
        return existing
    control = session.get(ProjectControlSnapshot, data.project_control_snapshot_id)
    if control is None or control.project_id != project.id:
        raise HTTPException(status_code=404, detail="Project control snapshot not found")
    report_date = datetime.now(UTC)
    payload = _projection(session, actor, project, data, report_date)
    payload["project_control"] = _serialize_control(control)
    payload["project_control_snapshot_id"] = str(control.id)
    payload["project_identity"] = {
        "id": str(project.id),
        "code": project.code,
        "name": project.name,
        "timezone": project.timezone,
        "currency": project.currency,
    }
    source_refs = {
        "project_control_snapshot_id": str(control.id),
        "schedule_context_id": str(control.schedule_context_id),
        "progress_weighting_context_id": str(control.progress_weighting_context_id),
        "evidence_item_ids": control.input_evidence_ids,
        "case_id": str(data.case_id) if data.case_id else None,
    }
    fidelity = {
        "canonicalization": "JSON_SORTED_KEYS_COMPACT_UTF8",
        "hash_algorithm": "SHA-256",
        "immutable_source_snapshot": True,
        "report_date": report_date.isoformat(),
        "data_date": control.data_date.isoformat(),
        "unknown_values_preserved_as_null": True,
        "recommendation_is_not_decision": True,
        "proposal_is_not_authorization": True,
    }
    number = (
        session.scalar(
            select(func.max(ReportSnapshot.report_number)).where(
                ReportSnapshot.project_id == project.id
            )
        )
        or 0
    ) + 1
    report = ReportSnapshot(
        id=uuid.uuid4(),
        organization_id=project.organization_id,
        project_id=project.id,
        project_control_snapshot_id=control.id,
        case_id=data.case_id,
        report_number=number,
        report_type=data.report_type,
        schema_version="1.0.0",
        report_date=report_date,
        data_date=control.data_date,
        payload=payload,
        source_refs=source_refs,
        policy_versions=control.policy_versions,
        generator_version=GENERATOR_VERSION,
        semantic_notice=REPORT_NOTICE,
        content_hash=_digest(payload),
        fidelity_manifest=fidelity,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
        generated_by=actor.actor_id,
    )
    session.add(report)
    # Persist the immutable parent before appending its lifecycle event (also under real FKs).
    session.flush()
    session.add(
        ReportLifecycleEvent(
            id=uuid.uuid4(),
            organization_id=project.organization_id,
            project_id=project.id,
            report_snapshot_id=report.id,
            event_number=1,
            from_status=None,
            to_status="DRAFT",
            reason="Report generated",
            actor_id=actor.actor_id,
        )
    )
    record_audit(
        session,
        actor,
        organization_id=project.organization_id,
        project_id=project.id,
        action="REPORT_SNAPSHOT_CREATED",
        object_type="REPORT_SNAPSHOT",
        object_id=str(report.id),
        object_version=number,
        details={"report_type": data.report_type, "content_hash": report.content_hash},
    )
    return report


def lifecycle_events(session: Session, report_id: uuid.UUID) -> list[ReportLifecycleEvent]:
    return list(
        session.scalars(
            select(ReportLifecycleEvent)
            .where(ReportLifecycleEvent.report_snapshot_id == report_id)
            .order_by(ReportLifecycleEvent.event_number)
        )
    )


def transition_report(
    session: Session,
    actor: ActorContext,
    project: Project,
    report: ReportSnapshot,
    data: ReportLifecycleCreate,
) -> ReportLifecycleEvent:
    project_lock(session, project)
    events = lifecycle_events(session, report.id)
    current = events[-1].to_status
    expected = {"DRAFT": "REVIEWED", "REVIEWED": "APPROVED"}.get(current)
    if data.to_status != expected:
        raise HTTPException(status_code=409, detail="Invalid report lifecycle transition")
    grant_id = None
    if data.to_status == "APPROVED":
        if data.authority_grant_id is None:
            raise HTTPException(
                status_code=403, detail="Active REPORT_APPROVAL authority grant denied"
            )
        grant = session.get(AuthorityGrant, data.authority_grant_id)
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
                status_code=403, detail="Active REPORT_APPROVAL authority grant denied"
            )
        grant_id = grant.id
    event = ReportLifecycleEvent(
        id=uuid.uuid4(),
        organization_id=project.organization_id,
        project_id=project.id,
        report_snapshot_id=report.id,
        event_number=len(events) + 1,
        from_status=current,
        to_status=data.to_status,
        reason=data.reason,
        authority_grant_id=grant_id,
        actor_id=actor.actor_id,
    )
    session.add(event)
    record_audit(
        session,
        actor,
        organization_id=project.organization_id,
        project_id=project.id,
        action=f"REPORT_{data.to_status}",
        object_type="REPORT_SNAPSHOT",
        object_id=str(report.id),
        object_version=event.event_number,
        details={"authority_grant_id": str(grant_id) if grant_id else None},
    )
    return event
