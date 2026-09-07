from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.case_schemas import DecisionCaseRead
from app.generated.taxonomies import (
    CommercialEffectType,
    CostAlignmentStatus,
    CostAssessmentStatus,
    CostConclusion,
    CostForecastStatus,
    CostRecordKind,
    SemanticState,
    TruthType,
)


class CostApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CostPolicyCreate(CostApiModel):
    policy_version: str = Field(min_length=3, max_length=40)
    alignment_tolerance: Decimal = Field(ge=0, le=1)
    minimum_earned_ratio_for_forecast: Decimal = Field(gt=0, le=1)
    include_accruals_in_recognized_cost: bool = True
    rationale: str = Field(min_length=3)
    supersedes_policy_id: uuid.UUID | None = None


class CostPolicyRead(CostApiModel):
    id: uuid.UUID | None
    organization_id: uuid.UUID | None
    project_id: uuid.UUID | None
    policy_version: str
    alignment_tolerance: Decimal
    minimum_earned_ratio_for_forecast: Decimal
    include_accruals_in_recognized_cost: bool
    rationale: str
    supersedes_policy_id: uuid.UUID | None
    created_by: str
    created_at: datetime | None


class CostRecordCreate(CostApiModel):
    evidence_item_id: uuid.UUID
    authorized_context_id: uuid.UUID | None = None
    record_kind: CostRecordKind
    amount: Decimal = Field(ge=0)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    measurement_basis: str = Field(min_length=1, max_length=80)
    reporting_period_start: date
    reporting_period_end: date
    commercial_effect: CommercialEffectType = CommercialEffectType.NONE
    effect_explanation: str | None = Field(default=None, min_length=3)

    @model_validator(mode="after")
    def valid_record(self) -> CostRecordCreate:
        if self.reporting_period_end < self.reporting_period_start:
            raise ValueError("Reporting period end must not precede start")
        authorized_kinds = {
            CostRecordKind.APPROVED_BUDGET,
            CostRecordKind.AUTHORIZED_CHANGE,
            CostRecordKind.BOQ_VALUE,
        }
        if (self.record_kind in authorized_kinds) != (self.authorized_context_id is not None):
            raise ValueError("Budget, change, and BOQ records require authorized context only")
        if self.commercial_effect != CommercialEffectType.NONE and not self.effect_explanation:
            raise ValueError("Commercial effects require an evidence-backed explanation")
        return self


class CostRecordRead(CostApiModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID
    controlled_object_id: uuid.UUID
    evidence_item_id: uuid.UUID
    authorized_context_id: uuid.UUID | None
    record_kind: CostRecordKind
    amount: Decimal
    currency: str
    measurement_basis: str
    reporting_period_start: date
    reporting_period_end: date
    as_of: datetime
    commercial_effect: CommercialEffectType
    effect_explanation: str | None
    semantic_state: SemanticState
    truth_type: TruthType
    confidence: Decimal
    recorded_by: str
    recorded_at: datetime


class CostAssessmentCreate(CostApiModel):
    expected_version: int = Field(ge=1)
    snapshot_id: uuid.UUID
    controlled_object_id: uuid.UUID
    cost_record_ids: list[uuid.UUID] = Field(min_length=1)
    physical_progress_ratio: Decimal | None = Field(default=None, ge=0, le=1)
    progress_measurement_id: uuid.UUID | None = None
    policy_version: str = Field(default="COST-DEFAULT-1.0.0", min_length=3, max_length=40)

    @model_validator(mode="after")
    def one_progress_source(self) -> CostAssessmentCreate:
        if self.physical_progress_ratio is not None and self.progress_measurement_id is not None:
            raise ValueError("Choose a progress measurement or explicit physical ratio, not both")
        return self


class CostAssessmentRead(CostApiModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID
    case_id: uuid.UUID
    snapshot_id: uuid.UUID
    budget_context_id: uuid.UUID
    controlled_object_id: uuid.UUID
    assessment_number: int
    data_date: datetime
    reporting_period_start: date
    reporting_period_end: date
    currency: str
    measurement_basis: str
    approved_budget: Decimal
    authorized_changes: Decimal
    current_authorized_budget: Decimal
    commitments: Decimal
    actuals: Decimal
    accruals: Decimal
    recognized_cost: Decimal
    earned_value: Decimal | None
    physical_progress_ratio: Decimal | None
    cost_consumption_ratio: Decimal | None
    progress_value_ratio: Decimal | None
    alignment_variance_ratio: Decimal | None
    alignment_status: CostAlignmentStatus
    explained_effects: list[dict[str, Any]]
    unexplained_variance_ratio: Decimal | None
    forecast_status: CostForecastStatus
    forecast_to_complete: Decimal | None
    estimate_at_completion: Decimal | None
    assessment_status: CostAssessmentStatus
    maximum_supported_conclusion: CostConclusion
    input_cost_record_ids: list[str]
    input_evidence_ids: list[str]
    truth_type: TruthType
    confidence: Decimal
    limitations: list[dict[str, Any]]
    policy_version: str
    formula_version: str
    idempotency_key: str
    request_hash: str
    assessed_by: str
    assessed_at: datetime


class CostAssessmentResult(CostApiModel):
    case: DecisionCaseRead
    assessment: CostAssessmentRead


class BudgetContextRead(CostApiModel):
    context_id: uuid.UUID
    version_number: int
    effective_from: datetime
    currency: str
    approved_budget: Decimal
    authorized_changes: Decimal
    current_authorized_budget: Decimal
    data_date: date | None
    reporting_period_start: date | None
    reporting_period_end: date | None
    controlled_object_code: str | None
    measurement_basis: str
