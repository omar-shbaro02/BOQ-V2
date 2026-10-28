from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, computed_field, model_validator

from app.case_schemas import DecisionCaseRead
from app.generated.taxonomies import (
    DeviationDirection,
    ProgressBasis,
    ProgressMeasurementKind,
    ProgressReconciliationStatus,
    ProgressWeightingBasis,
    SemanticState,
    TrendDirection,
    TrendPersistence,
    TruthType,
)
from app.health_schemas import HealthPolicy
from app.services.control_metrics import shared_metrics


class ProgressApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ProgressPolicyCreate(ProgressApiModel):
    policy_version: str = Field(min_length=3, max_length=40)
    deviation_threshold: Decimal = Field(gt=0, le=1)
    on_plan_tolerance: Decimal = Field(ge=0, lt=1)
    persistence_min_observations: int = Field(ge=2, le=20)
    persistence_min_duration_days: int = Field(ge=1, le=365)
    rationale: str = Field(min_length=3)
    supersedes_policy_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def tolerance_below_threshold(self) -> ProgressPolicyCreate:
        if self.on_plan_tolerance >= self.deviation_threshold:
            raise ValueError("on_plan_tolerance must be below deviation_threshold")
        return self


class ProgressPolicyRead(ProgressApiModel):
    id: uuid.UUID | None
    organization_id: uuid.UUID | None
    project_id: uuid.UUID | None
    policy_version: str
    deviation_threshold: Decimal
    on_plan_tolerance: Decimal
    persistence_min_observations: int
    persistence_min_duration_days: int
    rationale: str
    supersedes_policy_id: uuid.UUID | None
    created_by: str
    created_at: datetime | None


class ProgressMeasurementCreate(ProgressApiModel):
    evidence_item_id: uuid.UUID
    authorized_context_id: uuid.UUID | None = None
    measurement_kind: ProgressMeasurementKind
    numerator: Decimal = Field(ge=0)
    denominator: Decimal = Field(gt=0)
    unit: str = Field(min_length=1, max_length=30)

    @model_validator(mode="after")
    def planned_requires_context(self) -> ProgressMeasurementCreate:
        if (
            self.measurement_kind == ProgressMeasurementKind.PLANNED_AUTHORIZED
            and self.authorized_context_id is None
        ):
            raise ValueError("Planned progress requires authorized_context_id")
        return self


class ProgressMeasurementRead(ProgressApiModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID
    controlled_object_id: uuid.UUID
    evidence_item_id: uuid.UUID
    authorized_context_id: uuid.UUID | None
    measurement_kind: ProgressMeasurementKind
    measurement_basis: ProgressBasis
    numerator: Decimal
    denominator: Decimal
    completion_ratio: Decimal
    unit: str
    as_of: datetime
    semantic_state: SemanticState
    truth_type: TruthType
    confidence: Decimal
    recorded_by: str
    recorded_at: datetime


class ProjectControlPackageInput(ProgressApiModel):
    controlled_object_id: uuid.UUID
    planned_measurement_id: uuid.UUID
    actual_measurement_id: uuid.UUID

    @model_validator(mode="after")
    def distinct_measurements(self) -> ProjectControlPackageInput:
        if self.planned_measurement_id == self.actual_measurement_id:
            raise ValueError("Planned and actual measurements must be distinct")
        return self


class ProjectControlSnapshotCreate(ProgressApiModel):
    data_date: AwareDatetime
    progress_weighting_context_id: uuid.UUID
    schedule_context_id: uuid.UUID
    packages: list[ProjectControlPackageInput] = Field(min_length=1)
    cost_assessment_ids: list[uuid.UUID] = Field(default_factory=list)
    forecast_projection_ids: list[uuid.UUID] = Field(default_factory=list)
    schedule_assessment_ids: list[uuid.UUID] = Field(default_factory=list)
    health_policy: HealthPolicy | None = None
    progress_policy_version: str = Field(
        default="PROGRESS-DEFAULT-1.0.0", min_length=3, max_length=40
    )

    @model_validator(mode="after")
    def unique_package_inputs(self) -> ProjectControlSnapshotCreate:
        if len(self.schedule_assessment_ids) != len(set(self.schedule_assessment_ids)):
            raise ValueError("Schedule assessment IDs must be unique")
        object_ids = [item.controlled_object_id for item in self.packages]
        planned_ids = [item.planned_measurement_id for item in self.packages]
        actual_ids = [item.actual_measurement_id for item in self.packages]
        if len(object_ids) != len(set(object_ids)):
            raise ValueError("Each controlled object may appear only once")
        if len(planned_ids) != len(set(planned_ids)):
            raise ValueError("Each planned measurement may appear only once")
        if len(actual_ids) != len(set(actual_ids)):
            raise ValueError("Each actual measurement may appear only once")
        if len(self.cost_assessment_ids) != len(set(self.cost_assessment_ids)):
            raise ValueError("Cost assessment IDs must be unique")
        if len(self.forecast_projection_ids) != len(set(self.forecast_projection_ids)):
            raise ValueError("Forecast projection IDs must be unique")
        return self


class ProjectControlSnapshotRead(ProgressApiModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID
    snapshot_number: int
    data_date: datetime
    progress_weighting_context_id: uuid.UUID
    schedule_context_id: uuid.UUID
    weighting_basis: ProgressWeightingBasis
    measurement_basis: ProgressBasis
    package_results: list[dict[str, Any]]
    package_exclusions: list[dict[str, Any]]
    cost_assessment_refs: list[dict[str, Any]]
    forecast_projection_refs: list[dict[str, Any]]
    supporting_context: dict[str, Any]
    health: dict[str, Any]
    policy_versions: dict[str, Any]
    planned_ratio: Decimal
    actual_ratio: Decimal
    variance_ratio: Decimal
    progress_status: DeviationDirection
    progress_policy_version: str
    input_evidence_ids: list[str]
    truth_type: TruthType
    confidence: Decimal
    limitations: list[dict[str, Any]]
    formula_version: str
    idempotency_key: str
    request_hash: str
    created_by: str
    created_at: datetime

    @computed_field
    @property
    def shared_metrics(self) -> dict[str, Any]:
        return shared_metrics(self)


class ProgressEvaluationCreate(ProgressApiModel):
    expected_version: int = Field(ge=1)
    snapshot_id: uuid.UUID
    planned_measurement_id: uuid.UUID
    actual_measurement_id: uuid.UUID
    prior_planned_measurement_id: uuid.UUID | None = None
    prior_actual_measurement_id: uuid.UUID | None = None
    policy_version: str = Field(default="PROGRESS-DEFAULT-1.0.0", min_length=3, max_length=40)

    @model_validator(mode="after")
    def paired_prior_measurements(self) -> ProgressEvaluationCreate:
        if (self.prior_planned_measurement_id is None) != (
            self.prior_actual_measurement_id is None
        ):
            raise ValueError("Prior planned and actual measurements must be supplied together")
        if self.planned_measurement_id == self.actual_measurement_id:
            raise ValueError("Planned and actual measurements must be distinct")
        return self


class ProgressEvaluationRead(ProgressApiModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID
    case_id: uuid.UUID
    snapshot_id: uuid.UUID
    controlled_object_id: uuid.UUID
    evaluation_number: int
    data_date: datetime
    planned_measurement_id: uuid.UUID
    actual_measurement_id: uuid.UUID
    prior_planned_measurement_id: uuid.UUID | None
    prior_actual_measurement_id: uuid.UUID | None
    measurement_basis: ProgressBasis
    reconciliation_status: ProgressReconciliationStatus
    reconciled_measurements: dict[str, Any]
    planned_ratio: Decimal
    actual_ratio: Decimal
    variance_ratio: Decimal
    variance_magnitude: Decimal
    direction: DeviationDirection
    duration_days: int
    threshold_crossed: bool
    persistence: TrendPersistence
    trend_direction: TrendDirection
    supporting_observation_count: int
    planned_productivity: Decimal | None
    actual_productivity: Decimal | None
    productivity_variance_ratio: Decimal | None
    input_evidence_ids: list[str]
    input_truth_types: list[str]
    truth_type: TruthType
    confidence: Decimal
    limitations: list[dict[str, Any]]
    policy_version: str
    formula_version: str
    idempotency_key: str
    request_hash: str
    evaluated_by: str
    evaluated_at: datetime


class ProgressEvaluationResult(ProgressApiModel):
    case: DecisionCaseRead
    evaluation: ProgressEvaluationRead


class ProgressHistoryRead(ProgressApiModel):
    measurements: list[ProgressMeasurementRead]
    evaluations: list[ProgressEvaluationRead]
