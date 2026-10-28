from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DecisionCenterModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class DecisionQueueItem(DecisionCenterModel):
    case_id: uuid.UUID
    case_number: str
    title: str
    lifecycle: str
    readiness: str | None
    governance_state: str
    owner_actor_id: str
    opened_at: datetime
    controlled_object_count: int
    open_limitation_count: int
    active_response_count: int
    recommended_disposition: str | None
    decision_basis_recommendation: str | None
    human_disposition: str | None
    recommendation_agreement: str | None
    priority_score: str | None
    priority_band: str | None
    urgency: str | None
    overall_confidence: str | None
    consequence_window: str | None
    next_deadline: datetime | None
    next_action: str


class GovernedReport(DecisionCenterModel):
    report_type: str
    schema_version: str
    organization_id: uuid.UUID
    project_id: uuid.UUID
    generated_at: datetime
    generated_by: str
    as_of: datetime
    semantic_notice: str
    content_hash: str
    fidelity_manifest: dict[str, Any]
    payload: dict[str, Any]


class ReportSnapshotCreate(DecisionCenterModel):
    report_type: str = Field(
        pattern=r"^(WEEKLY_DECISION_BRIEF|MONTHLY_EXECUTIVE_REPORT|PROJECT_CONTROL_EXCEPTION_REPORT|ON_DEMAND_STATUS_REPORT|CASE_DOSSIER|PILOT_KPI_REPORT|GOVERNANCE_CONFORMITY_REPORT)$"
    )
    project_control_snapshot_id: uuid.UUID
    case_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def case_scope(self) -> ReportSnapshotCreate:
        if (self.report_type == "CASE_DOSSIER") != (self.case_id is not None):
            raise ValueError("Only CASE_DOSSIER requires case_id")
        return self


class ReportLifecycleCreate(DecisionCenterModel):
    to_status: str = Field(pattern=r"^(REVIEWED|APPROVED)$")
    reason: str = Field(min_length=3)
    authority_grant_id: uuid.UUID | None = None


class ReportLifecycleRead(DecisionCenterModel):
    id: uuid.UUID
    report_snapshot_id: uuid.UUID
    event_number: int
    from_status: str | None
    to_status: str
    reason: str
    authority_grant_id: uuid.UUID | None
    actor_id: str
    occurred_at: datetime


class ReportSnapshotRead(DecisionCenterModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID
    project_control_snapshot_id: uuid.UUID
    case_id: uuid.UUID | None
    report_number: int
    report_type: str
    schema_version: str
    report_date: datetime
    data_date: datetime
    payload: dict[str, Any]
    source_refs: dict[str, Any]
    policy_versions: dict[str, Any]
    generator_version: str
    semantic_notice: str
    content_hash: str
    fidelity_manifest: dict[str, Any]
    idempotency_key: str
    request_hash: str
    generated_by: str
    generated_at: datetime
    lifecycle_status: str
    lifecycle_events: list[ReportLifecycleRead]


class ReviewQueueEntry(DecisionCenterModel):
    case: DecisionQueueItem
    reason: str
    deadline: datetime | None
    required_role: str


class ReviewQueues(DecisionCenterModel):
    project_timezone: str
    verification: list[ReviewQueueEntry]
    human_review: list[ReviewQueueEntry]
    approval: list[ReviewQueueEntry]
    escalation: list[ReviewQueueEntry]
    governance_blocks: list[ReviewQueueEntry]
    overdue_evidence: list[ReviewQueueEntry]
    expiring_forecasts: list[ReviewQueueEntry]
