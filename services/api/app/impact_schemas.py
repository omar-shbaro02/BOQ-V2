from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.case_schemas import DecisionCaseRead
from app.generated.taxonomies import (
    ConsequenceSeverity,
    ImpactAssessmentStatus,
    PriorityBand,
    UrgencyLevel,
)


class ImpactApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ImpactPolicyCreate(ImpactApiModel):
    policy_version: str = Field(min_length=3, max_length=40)
    medium_cost_exposure_ratio: Decimal = Field(gt=0, le=1)
    high_cost_exposure_ratio: Decimal = Field(gt=0, le=1)
    critical_cost_exposure_ratio: Decimal = Field(gt=0, le=2)
    elevated_margin_days: int = Field(ge=1, le=365)
    urgent_margin_days: int = Field(ge=0, le=365)
    active_response_score_reduction: Decimal = Field(ge=0, le=50)
    cross_cutting_bonus_per_object: Decimal = Field(ge=0, le=20)
    medium_priority_score: Decimal = Field(gt=0, le=100)
    high_priority_score: Decimal = Field(gt=0, le=100)
    critical_priority_score: Decimal = Field(gt=0, le=100)
    rationale: str = Field(min_length=3)
    supersedes_policy_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def ordered_thresholds(self) -> ImpactPolicyCreate:
        if not (
            self.medium_cost_exposure_ratio
            < self.high_cost_exposure_ratio
            < self.critical_cost_exposure_ratio
        ):
            raise ValueError("Cost exposure thresholds must increase")
        if self.urgent_margin_days >= self.elevated_margin_days:
            raise ValueError("Urgent margin must be below elevated margin")
        if not (
            self.medium_priority_score < self.high_priority_score < self.critical_priority_score
        ):
            raise ValueError("Priority score thresholds must increase")
        return self


class ImpactPolicyRead(ImpactApiModel):
    id: uuid.UUID | None
    organization_id: uuid.UUID | None
    project_id: uuid.UUID | None
    policy_version: str
    medium_cost_exposure_ratio: Decimal
    high_cost_exposure_ratio: Decimal
    critical_cost_exposure_ratio: Decimal
    elevated_margin_days: int
    urgent_margin_days: int
    active_response_score_reduction: Decimal
    cross_cutting_bonus_per_object: Decimal
    medium_priority_score: Decimal
    high_priority_score: Decimal
    critical_priority_score: Decimal
    rationale: str
    supersedes_policy_id: uuid.UUID | None
    created_by: str
    created_at: datetime | None


class ConfidenceOverrideCreate(ImpactApiModel):
    expected_version: int = Field(ge=1)
    snapshot_id: uuid.UUID
    upstream_ceiling: Decimal = Field(ge=0, le=1)
    approved_confidence: Decimal = Field(ge=0, le=1)
    justification: str = Field(min_length=20)


class ConfidenceOverrideRead(ImpactApiModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID
    case_id: uuid.UUID
    snapshot_id: uuid.UUID
    upstream_ceiling: Decimal
    approved_confidence: Decimal
    justification: str
    approved_by: str
    approved_at: datetime


class ConfidenceOverrideResult(ImpactApiModel):
    case: DecisionCaseRead
    override: ConfidenceOverrideRead


class ImpactAssessmentCreate(ImpactApiModel):
    expected_version: int = Field(ge=1)
    snapshot_id: uuid.UUID
    controlled_object_id: uuid.UUID
    progress_evaluation_id: uuid.UUID | None = None
    schedule_assessment_id: uuid.UUID | None = None
    cost_assessment_id: uuid.UUID | None = None
    forecast_projection_ids: list[uuid.UUID] = Field(default_factory=list)
    confidence_override_id: uuid.UUID | None = None
    consequence_date: date | None = None
    verification_duration_days: int = Field(default=0, ge=0, le=365)
    approval_duration_days: int = Field(default=0, ge=0, le=365)
    mobilization_duration_days: int = Field(default=0, ge=0, le=365)
    recovery_window_end: date | None = None
    policy_version: str = Field(default="IMPACT-DEFAULT-1.0.0", min_length=3, max_length=40)

    @model_validator(mode="after")
    def requires_input(self) -> ImpactAssessmentCreate:
        if not any(
            (
                self.progress_evaluation_id,
                self.schedule_assessment_id,
                self.cost_assessment_id,
                self.forecast_projection_ids,
            )
        ):
            raise ValueError("Impact assessment requires at least one specialist result")
        return self


class ImpactAssessmentRead(ImpactApiModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID
    case_id: uuid.UUID
    snapshot_id: uuid.UUID
    controlled_object_id: uuid.UUID
    progress_evaluation_id: uuid.UUID | None
    schedule_assessment_id: uuid.UUID | None
    cost_assessment_id: uuid.UUID | None
    forecast_projection_ids: list[str]
    confidence_override_id: uuid.UUID | None
    assessment_number: int
    consequence_paths: list[dict[str, Any]]
    consequence_severity: ConsequenceSeverity
    decision_clocks: list[dict[str, Any]]
    response_lead_days: int
    urgency_margin_days: int | None
    urgency: UrgencyLevel
    truth_confidence: Decimal
    forecast_confidence: Decimal
    consequence_confidence: Decimal
    upstream_confidence_ceiling: Decimal
    overall_confidence: Decimal
    cross_cutting_reach: int
    active_response_count: int
    priority_score: Decimal
    priority_band: PriorityBand
    priority_reason_codes: list[str]
    assessment_status: ImpactAssessmentStatus
    limitations: list[dict[str, Any]]
    policy_version: str
    formula_version: str
    idempotency_key: str
    request_hash: str
    assessed_by: str
    assessed_at: datetime


class ImpactAssessmentResult(ImpactApiModel):
    case: DecisionCaseRead
    assessment: ImpactAssessmentRead
