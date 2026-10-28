from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Annotated, Any, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, model_validator

NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ContextModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid", str_strip_whitespace=True)


class CharterPayload(ContextModel):
    objectives: list[NonEmptyText] = Field(min_length=1)
    constraints: list[str] = Field(default_factory=list)
    milestones: list[dict[str, Any]] = Field(default_factory=list)
    success_criteria: list[NonEmptyText] = Field(min_length=1)
    delivery_strategy: str = Field(min_length=3)
    authority_reference: str = Field(min_length=3)


class StakeholderPayload(ContextModel):
    name: str = Field(min_length=2)
    actor_id: str | None = None
    project_role: str = Field(min_length=2)
    communication_rules: list[NonEmptyText] = Field(min_length=1)
    report_recipient: bool = False


class DailyUpdatePayload(ContextModel):
    data_date: date
    reporting_cutoff: AwareDatetime
    weather: dict[str, Any]
    labor: list[dict[str, Any]] = Field(default_factory=list)
    equipment: list[dict[str, Any]] = Field(default_factory=list)
    quantities: list[dict[str, Any]] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    safety_quality_observations: list[str] = Field(default_factory=list)


class RiskIssuePayload(ContextModel):
    title: str = Field(min_length=3)
    description: str = Field(min_length=3)
    owner_actor_id: str = Field(min_length=1)
    due_date: date | None = None
    probability: str | None = None
    impact: str | None = None


class ChangePayload(ContextModel):
    title: str = Field(min_length=3)
    description: str = Field(min_length=3)
    rationale: str = Field(min_length=3)
    affected_context_type: str = Field(pattern=r"^(SCHEDULE|BUDGET|BOQ|PROGRESS_WEIGHTING)$")
    expected_authorized_context_id: uuid.UUID | None = None


PAYLOAD_MODELS = {
    "CHARTER": CharterPayload,
    "STAKEHOLDER": StakeholderPayload,
    "DAILY_UPDATE": DailyUpdatePayload,
    "RISK": RiskIssuePayload,
    "ISSUE": RiskIssuePayload,
    "CHANGE_REQUEST": ChangePayload,
}


class ProjectContextRecordCreate(ContextModel):
    record_type: Literal[
        "CHARTER", "STAKEHOLDER", "DAILY_UPDATE", "RISK", "ISSUE", "CHANGE_REQUEST"
    ]
    record_key: str = Field(min_length=1, max_length=120)
    effective_from: AwareDatetime
    payload: dict[str, Any]
    evidence_item_ids: list[uuid.UUID] = Field(default_factory=list)
    supersedes_record_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def typed_payload(self) -> ProjectContextRecordCreate:
        if self.record_type == "CHARTER" and self.record_key != "PROJECT_CHARTER":
            raise ValueError("Project charter versions must use the singleton key PROJECT_CHARTER")
        self.payload = (
            PAYLOAD_MODELS[self.record_type].model_validate(self.payload).model_dump(mode="json")
        )
        if len(self.evidence_item_ids) != len(set(self.evidence_item_ids)):
            raise ValueError("Evidence item IDs must be unique")
        return self


class ProjectContextTransitionCreate(ContextModel):
    to_status: str = Field(min_length=2, max_length=30)
    reason: str = Field(min_length=3)
    authority_grant_id: uuid.UUID | None = None
    authorized_context_source_version_id: uuid.UUID | None = None
    approval_reference: str | None = Field(default=None, min_length=3)


class ProjectContextLifecycleRead(ContextModel):
    id: uuid.UUID
    record_id: uuid.UUID
    event_number: int
    from_status: str | None
    to_status: str
    reason: str
    authority_grant_id: uuid.UUID | None
    authorized_context_id: uuid.UUID | None
    actor_id: str
    idempotency_key: str
    occurred_at: datetime


class ProjectContextRecordRead(ContextModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID
    record_type: str
    record_key: str
    version_number: int
    supersedes_record_id: uuid.UUID | None
    effective_from: datetime
    initial_status: str
    payload: dict[str, Any]
    evidence_item_ids: list[str]
    idempotency_key: str
    request_hash: str
    created_by: str
    created_at: datetime
    current_status: str
    lifecycle_events: list[ProjectContextLifecycleRead]
    semantic_notice: str = (
        "Context assertions remain reported; review or approval does not verify "
        "operational claims or authorize execution."
    )
