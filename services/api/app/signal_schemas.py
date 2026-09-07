from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from app.generated.taxonomies import (
    CaseLifecycle,
    CorrelationOutcome,
    CorrelationReviewStatus,
    MaterialityBand,
    ScreeningOutcome,
    ScreeningReasonCode,
    SignalStatus,
    SignalType,
)


class SignalApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class SignalDetectionCreate(SignalApiModel):
    evidence_item_ids: list[uuid.UUID] = Field(default_factory=list)
    contradiction_ids: list[uuid.UUID] = Field(default_factory=list)


class SignalRead(SignalApiModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID
    controlled_object_id: uuid.UUID | None
    signal_type: SignalType
    status: SignalStatus
    title: str
    summary: str
    source_field: str
    source_evidence_ids: list[str]
    source_contradiction_id: uuid.UUID | None
    observed_value: Any
    detector_details: dict[str, Any]
    materiality_candidate: MaterialityBand
    fingerprint: str
    occurrence_count: int
    detector_name: str
    detector_version: str
    first_observed_at: datetime
    last_observed_at: datetime
    expires_at: datetime
    deferred_until: datetime | None
    workflow_version: int
    created_by: str
    created_at: datetime
    updated_at: datetime
    is_expired: bool


class DetectionRunRead(SignalApiModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID
    idempotency_key: str
    request_hash: str
    detector_version: str
    signal_ids: list[str]
    created_by: str
    created_at: datetime


class SignalDetectionResult(SignalApiModel):
    run: DetectionRunRead
    signals: list[SignalRead]


class SignalScreenCreate(SignalApiModel):
    expected_version: int = Field(ge=1)
    outcome: ScreeningOutcome
    reason_code: ScreeningReasonCode
    rationale: str = Field(min_length=3)
    materiality_candidate: MaterialityBand
    defer_until: AwareDatetime | None = None

    @model_validator(mode="after")
    def enforce_outcome_fields(self) -> SignalScreenCreate:
        if self.outcome == ScreeningOutcome.DEFER and self.defer_until is None:
            raise ValueError("DEFER outcome requires defer_until")
        if self.outcome != ScreeningOutcome.DEFER and self.defer_until is not None:
            raise ValueError("Only DEFER outcome accepts defer_until")
        return self


class ScreeningDecisionRead(SignalApiModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID
    signal_id: uuid.UUID
    signal_version: int
    outcome: ScreeningOutcome
    reason_code: ScreeningReasonCode
    rationale: str
    materiality_candidate: MaterialityBand
    defer_until: datetime | None
    decided_by: str
    decided_at: datetime


class SignalScreenResult(SignalApiModel):
    signal: SignalRead
    decision: ScreeningDecisionRead


class ExpireSignalsRead(SignalApiModel):
    expired_signal_ids: list[uuid.UUID]


class CorrelationSuggestionRead(SignalApiModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID
    signal_id: uuid.UUID
    signal_version: int
    suggested_outcome: CorrelationOutcome
    target_case_id: uuid.UUID | None
    child_case_ids: list[str]
    confidence: Decimal
    rationale: str
    status: CorrelationReviewStatus
    created_by: str
    created_at: datetime


class CorrelationReviewCreate(SignalApiModel):
    expected_signal_version: int = Field(ge=1)
    status: CorrelationReviewStatus
    selected_outcome: CorrelationOutcome | None = None
    target_case_id: uuid.UUID | None = None
    child_case_ids: list[uuid.UUID] = Field(default_factory=list)
    defer_until: AwareDatetime | None = None
    case_title: str | None = Field(default=None, min_length=3, max_length=240)
    case_owner_actor_id: str | None = Field(default=None, min_length=1, max_length=200)
    rationale: str = Field(min_length=3)

    @model_validator(mode="after")
    def enforce_review_fields(self) -> CorrelationReviewCreate:
        if self.status == CorrelationReviewStatus.REJECTED:
            if self.selected_outcome is not None:
                raise ValueError("Rejected suggestions cannot select an outcome")
            return self
        if self.selected_outcome is None:
            raise ValueError("Accepted review requires selected_outcome")
        if self.selected_outcome == CorrelationOutcome.LINK_EXISTING and not self.target_case_id:
            raise ValueError("LINK_EXISTING requires target_case_id")
        if self.selected_outcome == CorrelationOutcome.DEFER and not self.defer_until:
            raise ValueError("DEFER correlation requires defer_until")
        if self.selected_outcome in {
            CorrelationOutcome.OPEN_NEW,
            CorrelationOutcome.CROSS_CUTTING_PARENT_CHILD,
        } and (not self.case_title or not self.case_owner_actor_id):
            raise ValueError("Opening a case requires title and owner")
        if (
            self.selected_outcome == CorrelationOutcome.CROSS_CUTTING_PARENT_CHILD
            and len(self.child_case_ids) < 2
        ):
            raise ValueError("Cross-cutting correlation requires at least two child cases")
        return self


class CorrelationReviewRead(SignalApiModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID
    suggestion_id: uuid.UUID
    selected_outcome: CorrelationOutcome | None
    target_case_id: uuid.UUID | None
    created_case_id: uuid.UUID | None
    child_case_ids: list[str]
    rationale: str
    status: CorrelationReviewStatus
    reviewed_by: str
    reviewed_at: datetime


class DecisionCaseShellRead(SignalApiModel):
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
    created_by: str
    opened_at: datetime


class CorrelationReviewResult(SignalApiModel):
    signal: SignalRead
    review: CorrelationReviewRead
    case: DecisionCaseShellRead | None


class OutboxEventRead(SignalApiModel):
    event_id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID
    event_type: str
    schema_version: str
    aggregate_type: str
    aggregate_id: uuid.UUID
    aggregate_version: int
    actor_id: str
    correlation_id: uuid.UUID
    causation_id: uuid.UUID | None
    data_classification: str
    payload: dict[str, Any]
    occurred_at: datetime
    published_at: datetime | None
