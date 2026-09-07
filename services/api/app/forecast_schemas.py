from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.case_schemas import DecisionCaseRead
from app.generated.taxonomies import (
    ForecastMethod,
    ForecastScenarioType,
    ForecastStatus,
    ForecastTarget,
    ForecastValidity,
    SemanticState,
    TruthType,
)


class ForecastApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ForecastPolicyCreate(ForecastApiModel):
    policy_version: str = Field(min_length=3, max_length=40)
    lower_rate_factor: Decimal = Field(gt=0, lt=1)
    upper_rate_factor: Decimal = Field(gt=1, le=3)
    lower_cost_factor: Decimal = Field(gt=0, lt=1)
    upper_cost_factor: Decimal = Field(gt=1, le=3)
    confidence_decay_per_30_days: Decimal = Field(ge=0, lt=1)
    confidence_floor: Decimal = Field(ge=0, le=1)
    maximum_horizon_days: int = Field(ge=1, le=3650)
    validity_days: int = Field(ge=1, le=365)
    rationale: str = Field(min_length=3)
    supersedes_policy_id: uuid.UUID | None = None


class ForecastPolicyRead(ForecastApiModel):
    id: uuid.UUID | None
    organization_id: uuid.UUID | None
    project_id: uuid.UUID | None
    policy_version: str
    lower_rate_factor: Decimal
    upper_rate_factor: Decimal
    lower_cost_factor: Decimal
    upper_cost_factor: Decimal
    confidence_decay_per_30_days: Decimal
    confidence_floor: Decimal
    maximum_horizon_days: int
    validity_days: int
    rationale: str
    supersedes_policy_id: uuid.UUID | None
    created_by: str
    created_at: datetime | None


class ForecastCreate(ForecastApiModel):
    expected_version: int = Field(ge=1)
    snapshot_id: uuid.UUID
    controlled_object_id: uuid.UUID
    target: ForecastTarget
    scenario_type: ForecastScenarioType
    horizon_end: date
    progress_evaluation_id: uuid.UUID | None = None
    schedule_assessment_id: uuid.UUID | None = None
    cost_assessment_id: uuid.UUID | None = None
    active_response_id: uuid.UUID | None = None
    assumptions: list[str] = Field(default_factory=list, max_length=20)
    scenario_parameters: dict[str, Decimal] = Field(default_factory=dict)
    policy_version: str = Field(default="FORECAST-DEFAULT-1.0.0", min_length=3, max_length=40)

    @model_validator(mode="after")
    def valid_branch_and_input(self) -> ForecastCreate:
        inputs = {
            ForecastTarget.PRODUCTION_COMPLETION_DATE: self.progress_evaluation_id,
            ForecastTarget.SCHEDULE_COMPLETION_DATE: self.schedule_assessment_id,
            ForecastTarget.ESTIMATE_AT_COMPLETION: self.cost_assessment_id,
        }
        if inputs[self.target] is None or sum(value is not None for value in inputs.values()) != 1:
            raise ValueError("Forecast target requires exactly its matching specialist input")
        if self.scenario_type == ForecastScenarioType.ACTIVE_RESPONSE:
            if self.active_response_id is None:
                raise ValueError("Active-response forecast requires active_response_id")
            if self.scenario_parameters:
                raise ValueError("Active-response parameters come from the authorized response")
        elif self.active_response_id is not None:
            raise ValueError("Only active-response forecasts may reference an active response")
        if (
            self.scenario_type == ForecastScenarioType.CONTINUED_PERFORMANCE
            and self.scenario_parameters
        ):
            raise ValueError("Continued-performance forecast cannot contain scenario changes")
        if self.scenario_type == ForecastScenarioType.HYPOTHETICAL and not self.assumptions:
            raise ValueError("Hypothetical scenario requires explicit assumptions")
        allowed = {"productivity_multiplier", "schedule_day_adjustment", "cost_multiplier"}
        if set(self.scenario_parameters) - allowed:
            raise ValueError("Unsupported scenario parameter")
        return self


class ForecastRead(ForecastApiModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID
    case_id: uuid.UUID
    snapshot_id: uuid.UUID
    controlled_object_id: uuid.UUID
    progress_evaluation_id: uuid.UUID | None
    schedule_assessment_id: uuid.UUID | None
    cost_assessment_id: uuid.UUID | None
    active_response_id: uuid.UUID | None
    forecast_number: int
    target: ForecastTarget
    scenario_type: ForecastScenarioType
    method: ForecastMethod
    status: ForecastStatus
    semantic_state: SemanticState
    truth_type: TruthType
    data_date: datetime
    horizon_end: date
    horizon_days: int
    result_unit: str
    result_point: str
    result_lower: str
    result_upper: str
    input_values: dict[str, Any]
    input_evidence_ids: list[str]
    assumptions: list[str]
    scenario_parameters: dict[str, Any]
    limitations: list[dict[str, Any]]
    upstream_confidence: Decimal
    horizon_confidence: Decimal
    valid_until: datetime
    recalculation_triggers: list[str]
    validity: ForecastValidity
    policy_version: str
    formula_version: str
    idempotency_key: str
    request_hash: str
    created_by: str
    created_at: datetime


class ForecastResult(ForecastApiModel):
    case: DecisionCaseRead
    forecast: ForecastRead
