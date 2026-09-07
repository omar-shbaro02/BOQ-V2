from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.case_schemas import DecisionCaseRead
from app.generated.taxonomies import (
    FloatSource,
    ScheduleAssessmentStatus,
    ScheduleConclusion,
    ScheduleExposureLevel,
    ScheduleQualityStatus,
    ScheduleTimingDirection,
    TruthType,
)


class ScheduleApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class SchedulePolicyCreate(ScheduleApiModel):
    policy_version: str = Field(min_length=3, max_length=40)
    on_time_tolerance_days: Decimal = Field(ge=0, le=30)
    maximum_schedule_age_days: int = Field(ge=1, le=365)
    require_dependency_for_consequence: bool = True
    allow_calculated_float: bool = True
    rationale: str = Field(min_length=3)
    supersedes_policy_id: uuid.UUID | None = None


class SchedulePolicyRead(ScheduleApiModel):
    id: uuid.UUID | None
    organization_id: uuid.UUID | None
    project_id: uuid.UUID | None
    policy_version: str
    on_time_tolerance_days: Decimal
    maximum_schedule_age_days: int
    require_dependency_for_consequence: bool
    allow_calculated_float: bool
    rationale: str
    supersedes_policy_id: uuid.UUID | None
    created_by: str
    created_at: datetime | None


class ScheduleAssessmentCreate(ScheduleApiModel):
    expected_version: int = Field(ge=1)
    snapshot_id: uuid.UUID
    controlled_object_id: uuid.UUID
    activity_code: str = Field(min_length=1, max_length=80)
    delay_evidence_item_id: uuid.UUID
    policy_version: str = Field(default="SCHEDULE-DEFAULT-1.0.0", min_length=3, max_length=40)


class ScheduleAssessmentRead(ScheduleApiModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID
    case_id: uuid.UUID
    snapshot_id: uuid.UUID
    schedule_context_id: uuid.UUID
    controlled_object_id: uuid.UUID
    delay_evidence_item_id: uuid.UUID
    assessment_number: int
    activity_code: str
    data_date: datetime
    planned_start: date
    planned_finish: date
    delay_days: Decimal
    timing_direction: ScheduleTimingDirection
    effective_float_days: Decimal | None
    float_source: FloatSource
    schedule_quality: ScheduleQualityStatus
    assessment_status: ScheduleAssessmentStatus
    exposure_level: ScheduleExposureLevel
    downstream_paths: list[dict[str, Any]]
    affected_activity_codes: list[str]
    milestone_exposures: list[dict[str, Any]]
    project_completion_exposure_days: Decimal | None
    maximum_supported_conclusion: ScheduleConclusion
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


class ScheduleAssessmentResult(ScheduleApiModel):
    case: DecisionCaseRead
    assessment: ScheduleAssessmentRead


class ScheduleNetworkRead(ScheduleApiModel):
    context_id: uuid.UUID
    version_number: int
    effective_from: datetime
    data_date: date
    activity_count: int
    dependency_count: int
    milestone_count: int
    calendar_count: int
    activities: list[dict[str, Any]]
    dependencies: list[dict[str, Any]]
    milestones: list[dict[str, Any]]
    constraints: list[dict[str, Any]]
