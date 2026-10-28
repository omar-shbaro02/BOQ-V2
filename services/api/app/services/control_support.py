"""Freeze supporting records at the selected cut-off; never reconstruct from current case state."""

import uuid
from datetime import datetime

from app.health_schemas import HealthPolicy, utc_datetime
from app.models import (
    AuditEvent,
    CaseSnapshot,
    Project,
    ProjectContextLifecycleEvent,
    ProjectContextRecord,
    ScheduleAssessment,
)
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session


def freeze_support(
    session: Session,
    project: Project,
    data_date: datetime,
    schedule_id: uuid.UUID,
    assessment_ids: list[uuid.UUID],
    policy: HealthPolicy | None,
) -> dict:
    cutoff = utc_datetime(data_date)
    schedules = []
    object_ids = set()
    for assessment_id in sorted(assessment_ids, key=str):
        assessment = session.get(ScheduleAssessment, assessment_id)
        if assessment is None or assessment.project_id != project.id:
            raise HTTPException(404, "Schedule assessment not found")
        if (
            assessment.schedule_context_id != schedule_id
            or utc_datetime(assessment.data_date) > cutoff
        ):
            raise HTTPException(
                422, "Schedule assessment must use the selected context and source cut-off"
            )
        if assessment.controlled_object_id in object_ids:
            raise HTTPException(422, "Select only one exact schedule assessment per package")
        object_ids.add(assessment.controlled_object_id)
        schedules.append(
            {
                "id": str(assessment.id),
                "case_id": str(assessment.case_id),
                "controlled_object_id": str(assessment.controlled_object_id),
                "schedule_context_id": str(assessment.schedule_context_id),
                "data_date": utc_datetime(assessment.data_date).isoformat(),
                "assessed_at": utc_datetime(assessment.assessed_at).isoformat(),
                "assessment_status": assessment.assessment_status,
                "schedule_quality": assessment.schedule_quality,
                "project_completion_exposure_days": str(assessment.project_completion_exposure_days)
                if assessment.project_completion_exposure_days is not None
                else None,
                "maximum_supported_conclusion": assessment.maximum_supported_conclusion,
                "confidence": str(assessment.confidence),
                "truth_type": assessment.truth_type,
                "input_evidence_ids": assessment.input_evidence_ids,
                "limitations": assessment.limitations,
                "stale": policy is not None
                and (cutoff - utc_datetime(assessment.data_date)).days
                > policy.maximum_source_age_days,
                "policy_version": assessment.policy_version,
                "formula_version": assessment.formula_version,
            }
        )
    case_snapshots = session.scalars(
        select(CaseSnapshot)
        .where(
            CaseSnapshot.project_id == project.id,
            CaseSnapshot.data_date <= cutoff,
            CaseSnapshot.created_at <= cutoff,
        )
        .order_by(CaseSnapshot.case_id, CaseSnapshot.snapshot_number.desc())
    )
    governance = []
    seen_cases = set()
    for snapshot in case_snapshots:
        if snapshot.case_id in seen_cases:
            continue
        seen_cases.add(snapshot.case_id)
        event = session.scalar(
            select(AuditEvent)
            .where(
                AuditEvent.project_id == project.id,
                AuditEvent.object_type == "DECISION_CASE",
                AuditEvent.object_id == str(snapshot.case_id),
                AuditEvent.occurred_at <= cutoff,
            )
            .order_by(
                AuditEvent.object_version.desc(),
                AuditEvent.occurred_at.desc(),
                AuditEvent.event_id.desc(),
            )
            .limit(1)
        )
        governance.append(
            {
                "case_id": str(snapshot.case_id),
                "case_snapshot_id": str(snapshot.id),
                "controlled_object_ids": snapshot.controlled_object_ids,
                "audit_event_id": str(event.event_id) if event else None,
                "case_version": event.object_version if event else None,
                "governance_state": event.details.get("governance_state", "UNKNOWN")
                if event
                else "UNKNOWN",
                "observed_at": utc_datetime(event.occurred_at).isoformat() if event else None,
                "contradiction_ids": snapshot.contradiction_ids,
            }
        )
    records = session.scalars(
        select(ProjectContextRecord)
        .where(
            ProjectContextRecord.project_id == project.id,
            ProjectContextRecord.created_at <= cutoff,
            ProjectContextRecord.effective_from <= cutoff,
        )
        .order_by(ProjectContextRecord.version_number.desc(), ProjectContextRecord.id)
    )
    context_refs = []
    streams = set()
    for record in records:
        stream = (record.record_type, record.record_key)
        if stream in streams and record.record_type != "CHARTER":
            continue
        streams.add(stream)
        history = list(
            session.scalars(
                select(ProjectContextLifecycleEvent)
                .where(
                    ProjectContextLifecycleEvent.record_id == record.id,
                    ProjectContextLifecycleEvent.occurred_at <= cutoff,
                )
                .order_by(ProjectContextLifecycleEvent.event_number)
            )
        )
        context_refs.append(
            {
                "id": str(record.id),
                "record_type": record.record_type,
                "record_key": record.record_key,
                "version_number": record.version_number,
                "effective_from": utc_datetime(record.effective_from).isoformat(),
                "recorded_at": utc_datetime(record.created_at).isoformat(),
                "status": history[-1].to_status if history else record.initial_status,
                "payload": record.payload,
                "evidence_item_ids": record.evidence_item_ids,
                "lifecycle_event_ids": [str(item.id) for item in history],
                "semantic_notice": (
                    "Reported context; review and approval do not verify operational assertions."
                ),
            }
        )
    return {
        "data_date": cutoff.isoformat(),
        "schedule_assessments": schedules,
        "governance": governance,
        "project_context": context_refs,
    }
