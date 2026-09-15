from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from app.evidence_schemas import EvidenceItemRead, EvidenceRequestRead
from app.generated.taxonomies import (
    ActiveResponseStatus,
    AutonomyClass,
    BaselineValidity,
    CaseLedgerEventType,
    CaseLifecycle,
    CaseReopenTrigger,
    ConclusionType,
    DecisionReadiness,
    GovernanceState,
    LimitationCode,
    LimitationStatus,
)


class CaseApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class DecisionCaseRead(CaseApiModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID
    case_number: str
    title: str
    case_type: str
    lifecycle: CaseLifecycle
    owner_actor_id: str
    parent_case_id: uuid.UUID | None
    version: int
    readiness: DecisionReadiness | None
    governance_state: GovernanceState
    autonomy_class: AutonomyClass
    blocked_from_lifecycle: CaseLifecycle | None
    blocker_code: str | None
    blocker_description: str | None
    last_snapshot_id: uuid.UUID | None
    last_progress_evaluation_id: uuid.UUID | None
    last_schedule_assessment_id: uuid.UUID | None
    last_cost_assessment_id: uuid.UUID | None
    last_forecast_projection_id: uuid.UUID | None
    last_impact_assessment_id: uuid.UUID | None
    last_orchestration_run_id: uuid.UUID | None
    last_human_decision_id: uuid.UUID | None
    outcome_reference: str | None
    close_reason: str | None
    closed_at: datetime | None
    reopen_trigger: CaseReopenTrigger | None
    reopen_reason: str | None
    reopened_at: datetime | None
    created_by: str
    opened_at: datetime


class AttachEvidenceCreate(CaseApiModel):
    expected_version: int = Field(ge=1)
    evidence_item_ids: list[uuid.UUID] = Field(min_length=1)
    attachment_reason: str = Field(min_length=3)


class AttachEvidenceResult(CaseApiModel):
    case: DecisionCaseRead
    attached_evidence_item_ids: list[uuid.UUID]


class ActiveResponseCreate(CaseApiModel):
    expected_version: int = Field(ge=1)
    response_type: str = Field(min_length=2, max_length=80)
    authorization_reference: str = Field(min_length=2, max_length=200)
    owner_actor_id: str = Field(min_length=1, max_length=200)
    status: ActiveResponseStatus = ActiveResponseStatus.ACTIVE
    effective_from: AwareDatetime
    effective_until: AwareDatetime | None = None
    details: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def valid_window(self) -> ActiveResponseCreate:
        if self.effective_until and self.effective_until <= self.effective_from:
            raise ValueError("effective_until must be after effective_from")
        return self


class ActiveResponseRead(CaseApiModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID
    case_id: uuid.UUID
    response_type: str
    authorization_reference: str
    owner_actor_id: str
    status: ActiveResponseStatus
    effective_from: datetime
    effective_until: datetime | None
    details: dict[str, Any]
    recorded_by: str
    recorded_at: datetime


class ActiveResponseResult(CaseApiModel):
    case: DecisionCaseRead
    response: ActiveResponseRead


class SnapshotCreate(CaseApiModel):
    expected_version: int = Field(ge=1)
    data_date: AwareDatetime
    policy_version: str = Field(default="PHASE4-SUFFICIENCY-1.0.0", min_length=3, max_length=40)


class SnapshotRead(CaseApiModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID
    case_id: uuid.UUID
    snapshot_number: int
    case_version: int
    data_date: datetime
    controlled_object_ids: list[str]
    signal_ids: list[str]
    evidence_item_ids: list[str]
    contradiction_ids: list[str]
    authorized_context_refs: list[dict[str, Any]]
    active_response_ids: list[str]
    baseline_validity: BaselineValidity
    policy_version: str
    snapshot_hash: str
    idempotency_key: str
    request_hash: str
    created_by: str
    created_at: datetime


class SnapshotResult(CaseApiModel):
    case: DecisionCaseRead
    snapshot: SnapshotRead


class BaselineAssessmentCreate(CaseApiModel):
    expected_version: int = Field(ge=1)
    snapshot_id: uuid.UUID
    authorized_context_id: uuid.UUID | None = None
    validity: BaselineValidity
    rationale: str = Field(min_length=3)


class BaselineAssessmentRead(CaseApiModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID
    case_id: uuid.UUID
    snapshot_id: uuid.UUID
    authorized_context_id: uuid.UUID | None
    validity: BaselineValidity
    rationale: str
    assessed_by: str
    assessed_at: datetime


class BaselineAssessmentResult(CaseApiModel):
    case: DecisionCaseRead
    assessment: BaselineAssessmentRead


class SufficiencyAssessCreate(CaseApiModel):
    expected_version: int = Field(ge=1)
    snapshot_id: uuid.UUID
    conclusion_type: ConclusionType
    gap_owner_actor_id: str = Field(min_length=1, max_length=200)
    gap_due_at: AwareDatetime


class SufficiencyAssessmentRead(CaseApiModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID
    case_id: uuid.UUID
    snapshot_id: uuid.UUID
    conclusion_type: ConclusionType
    readiness: DecisionReadiness
    present_evidence: list[dict[str, Any]]
    missing_evidence: list[dict[str, Any]]
    stale_evidence_ids: list[str]
    weak_evidence_ids: list[str]
    contradictory_evidence: list[dict[str, Any]]
    limitation_ids: list[str]
    evidence_request_ids: list[str]
    maximum_supported_conclusion: str
    policy_version: str
    assessed_by: str
    assessed_at: datetime


class LimitationRead(CaseApiModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID
    case_id: uuid.UUID
    snapshot_id: uuid.UUID
    code: LimitationCode
    description: str
    material: bool
    owner_actor_id: str
    due_at: datetime
    status: LimitationStatus
    resolution: str | None
    resolved_by: str | None
    resolved_at: datetime | None
    created_at: datetime


class SufficiencyAssessmentResult(CaseApiModel):
    case: DecisionCaseRead
    assessment: SufficiencyAssessmentRead
    limitations: list[LimitationRead]
    evidence_requests: list[EvidenceRequestRead]


class LimitationResolveCreate(CaseApiModel):
    expected_version: int = Field(ge=1)
    resolution: str = Field(min_length=3)


class LimitationResolveResult(CaseApiModel):
    case: DecisionCaseRead
    limitation: LimitationRead


class LifecycleTransitionCreate(CaseApiModel):
    expected_version: int = Field(ge=1)
    target_lifecycle: CaseLifecycle
    reason: str = Field(min_length=3)


class CaseBlockCreate(CaseApiModel):
    expected_version: int = Field(ge=1)
    blocker_code: str = Field(min_length=2, max_length=80)
    blocker_description: str = Field(min_length=3)


class CaseResumeCreate(CaseApiModel):
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=3)


class CaseCloseCreate(CaseApiModel):
    expected_version: int = Field(ge=1)
    outcome_reference: str | None = Field(default=None, min_length=2, max_length=200)
    administrative_rationale: str | None = Field(default=None, min_length=3)

    @model_validator(mode="after")
    def closure_basis(self) -> CaseCloseCreate:
        if not self.outcome_reference and not self.administrative_rationale:
            raise ValueError("Closure requires outcome_reference or administrative_rationale")
        return self


class CaseReopenCreate(CaseApiModel):
    expected_version: int = Field(ge=1)
    trigger: CaseReopenTrigger
    reason: str = Field(min_length=3)
    new_evidence_item_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def material_evidence_reference(self) -> CaseReopenCreate:
        if (
            self.trigger == CaseReopenTrigger.NEW_MATERIAL_EVIDENCE
            and self.new_evidence_item_id is None
        ):
            raise ValueError("New material evidence reopening requires new_evidence_item_id")
        return self


class CaseLedgerEventRead(CaseApiModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID
    case_id: uuid.UUID
    case_version: int
    event_type: CaseLedgerEventType
    from_lifecycle: CaseLifecycle | None
    to_lifecycle: CaseLifecycle | None
    actor_id: str
    reason: str
    details: dict[str, Any]
    occurred_at: datetime


class EvidenceAssemblyRead(CaseApiModel):
    case: DecisionCaseRead
    evidence: list[EvidenceItemRead]
    requests: list[EvidenceRequestRead]
    active_responses: list[ActiveResponseRead]
    limitations: list[LimitationRead]
    snapshots: list[SnapshotRead]
    assessments: list[SufficiencyAssessmentRead]
    ledger: list[CaseLedgerEventRead]


class SufficiencyPolicyRead(CaseApiModel):
    conclusion_type: ConclusionType
    policy_version: str
    required_field_groups: list[list[str]]
    required_authorized_contexts: list[str]
    requires_strong_truth: bool
