from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


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
