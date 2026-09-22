from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.generated.taxonomies import (
    BootstrapReadiness,
    BoqExtractionStatus,
    BoqRowClass,
    DependencyBasis,
    DurationBasis,
    DurationStatus,
    MilestoneSourceType,
    PlanningConfidence,
    PlanningReviewState,
    PlanningStructureAction,
    PlanningStructureStatus,
    ProductivitySourceType,
    ScheduleActivityArchetype,
    ScheduleConstraintType,
    ScheduleDependencyType,
    ScheduleDraftState,
)


class BootstrapApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class BoqSourceCreate(BootstrapApiModel):
    artifact_id: uuid.UUID
    prior_source_version_id: uuid.UUID | None = None


class BoqSourceRowRead(BootstrapApiModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID
    source_version_id: uuid.UUID
    sequence_number: int
    sheet_name: str | None
    page_number: int | None
    row_number: int | None
    region: dict[str, Any] | None
    raw_values: list[Any]
    original_text: str | None
    extraction_confidence: Decimal
    warnings: list[dict[str, Any]]
    created_at: datetime


class BoqSourceRead(BootstrapApiModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID
    artifact_id: uuid.UUID
    prior_source_version_id: uuid.UUID | None
    version_number: int
    source_format: str
    parser_name: str
    parser_version: str
    content_sha256: str
    extraction_status: BoqExtractionStatus
    extraction_confidence: Decimal
    structure_manifest: list[dict[str, Any]]
    warnings: list[dict[str, Any]]
    extracted_row_count: int
    created_by: str
    created_at: datetime


class BoqSourceDetail(BoqSourceRead):
    rows: list[BoqSourceRowRead] = Field(default_factory=list)


class BoqNormalizeCreate(BootstrapApiModel):
    header_rows: dict[str, int] = Field(default_factory=dict)
    column_mapping: dict[str, dict[str, int]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def valid_coordinates(self) -> BoqNormalizeCreate:
        if any(row < 1 for row in self.header_rows.values()):
            raise ValueError("Explicit header rows must be positive")
        if any(index < 1 for mapping in self.column_mapping.values() for index in mapping.values()):
            raise ValueError("Explicit column indexes must be positive")
        return self


class BoqLineRead(BootstrapApiModel):
    id: uuid.UUID
    stable_line_id: str
    organization_id: uuid.UUID
    project_id: uuid.UUID
    normalization_run_id: uuid.UUID
    source_version_id: uuid.UUID
    source_row_id: uuid.UUID
    source_location: dict[str, Any]
    item_number: str | None
    division: str | None
    source_wbs_code: str | None
    item_name: str | None
    description: str | None
    unit: str | None
    quantity: Decimal | None
    unit_price: Decimal | None
    total_price: Decimal | None
    currency: str | None
    location: str | None
    trade: str | None
    package: str | None
    notes: str | None
    parent_section: str | None
    source_row_text: str | None
    normalized_values: dict[str, Any]
    unmapped_values: dict[str, Any]
    classification: BoqRowClass
    classification_basis: list[str]
    schedule_relevant: bool
    confidence: PlanningConfidence
    review_state: PlanningReviewState
    warnings: list[dict[str, Any]]
    created_at: datetime


class BoqNormalizationRead(BootstrapApiModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID
    source_version_id: uuid.UUID
    normalizer_version: str
    header_rows: dict[str, int]
    column_mapping: dict[str, dict[str, int]]
    warnings: list[dict[str, Any]]
    total_rows: int
    schedule_relevant_rows: int
    review_required_rows: int
    created_by: str
    created_at: datetime


class BoqNormalizationDetail(BoqNormalizationRead):
    lines: list[BoqLineRead] = Field(default_factory=list)


class PlanningStructureCreate(BootstrapApiModel):
    grouping_dimensions: list[str] = Field(
        default_factory=lambda: [
            "source_wbs_code",
            "division",
            "location",
            "trade",
            "package",
            "parent_section",
        ]
    )


class PlanningStructureRevisionCreate(BootstrapApiModel):
    action: PlanningStructureAction
    package_ids: list[str] = Field(default_factory=list)
    line_ids: list[uuid.UUID] = Field(default_factory=list)
    target_package_id: str | None = None
    new_package_names: list[str] = Field(default_factory=list)
    reason: str = Field(min_length=10, max_length=2000)


class PlanningStructureRead(BootstrapApiModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID
    normalization_run_id: uuid.UUID
    supersedes_version_id: uuid.UUID | None
    version_number: int
    status: PlanningStructureStatus
    action: PlanningStructureAction
    wbs_nodes: list[dict[str, Any]]
    work_packages: list[dict[str, Any]]
    line_mappings: list[dict[str, Any]]
    unmapped_lines: list[dict[str, Any]]
    assumptions: list[dict[str, Any]]
    warnings: list[dict[str, Any]]
    change_summary: dict[str, Any]
    reason: str
    created_by: str
    created_at: datetime


class ProductivityInput(BootstrapApiModel):
    work_package_id: str
    rate_per_working_day: Decimal = Field(gt=0)
    quantity_unit: str = Field(min_length=1, max_length=80)
    source_type: ProductivitySourceType
    source_reference: str = Field(min_length=3, max_length=300)
    source_date: date | None = None
    source_version: str = Field(min_length=1, max_length=80)
    applicable_trade: str | None = Field(default=None, max_length=160)
    applicable_location: str | None = Field(default=None, max_length=240)
    confidence: PlanningConfidence
    review_state: PlanningReviewState


class ExplicitDurationInput(BootstrapApiModel):
    work_package_id: str
    activity_type: ScheduleActivityArchetype
    duration_working_days: Decimal = Field(gt=0)
    basis: DurationBasis
    source_reference: str = Field(min_length=3, max_length=300)
    confidence: PlanningConfidence


class ScheduleDraftGenerateCreate(BootstrapApiModel):
    productivity_inputs: list[ProductivityInput] = Field(default_factory=list)
    duration_inputs: list[ExplicitDurationInput] = Field(default_factory=list)
    validation_owner: str = Field(min_length=3, max_length=200)


class ProposedScheduleActivityRead(BootstrapApiModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID
    generation_id: uuid.UUID
    activity_code: str
    wbs_node_id: str
    work_package_id: str
    boq_line_refs: list[str]
    activity_name: str
    activity_type: ScheduleActivityArchetype
    trade: str | None
    location: str | None
    description: str
    quantity: Decimal | None
    unit: str | None
    duration_working_days: Decimal | None
    duration_unrounded: Decimal | None
    duration_status: DurationStatus
    duration_basis: DurationBasis
    productivity: dict[str, Any] | None
    calendar_id: str | None
    responsible_role: str | None
    confidence: PlanningConfidence
    review_state: PlanningReviewState
    warnings: list[dict[str, Any]]
    created_at: datetime


class PlanningAssumptionRead(BootstrapApiModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID
    generation_id: uuid.UUID
    proposition: str
    reason_needed: str
    affected_activity_ids: list[str]
    source_basis: str
    confidence: PlanningConfidence
    consequence_if_wrong: str
    validation_owner: str
    status: str
    resolution_note: str | None
    created_at: datetime


class ScheduleDraftGenerationRead(BootstrapApiModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID
    planning_structure_id: uuid.UUID
    generator_version: str
    draft_state: ScheduleDraftState
    productivity_inputs: list[dict[str, Any]]
    duration_inputs: list[dict[str, Any]]
    warnings: list[dict[str, Any]]
    activity_count: int
    unresolved_duration_count: int
    created_by: str
    created_at: datetime


class ScheduleDraftGenerationDetail(ScheduleDraftGenerationRead):
    activities: list[ProposedScheduleActivityRead] = Field(default_factory=list)
    assumptions: list[PlanningAssumptionRead] = Field(default_factory=list)


class PlanningCalendarInput(BootstrapApiModel):
    calendar_id: str = Field(default="PROJECT", min_length=1, max_length=80)
    name: str = Field(min_length=2, max_length=160)
    working_weekdays: list[int] = Field(min_length=1)
    working_hours_per_day: Decimal = Field(gt=0, le=24)
    holidays: list[date] = Field(default_factory=list)
    shift_pattern: str | None = Field(default=None, max_length=160)
    review_state: PlanningReviewState

    @model_validator(mode="after")
    def valid_week(self) -> PlanningCalendarInput:
        if any(day < 0 or day > 6 for day in self.working_weekdays):
            raise ValueError("Working weekdays must be between zero and six")
        if len(set(self.working_weekdays)) != len(self.working_weekdays):
            raise ValueError("Working weekdays must be unique")
        return self


class DependencyProposalInput(BootstrapApiModel):
    predecessor_activity_id: uuid.UUID
    successor_activity_id: uuid.UUID
    relation_type: ScheduleDependencyType = ScheduleDependencyType.FINISH_TO_START
    lag_working_days: Decimal = Decimal("0")
    basis: DependencyBasis
    source_reference: str = Field(min_length=3, max_length=300)
    confidence: PlanningConfidence
    review_state: PlanningReviewState


class MilestoneProposalInput(BootstrapApiModel):
    code: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=2, max_length=240)
    target_date: date
    source_type: MilestoneSourceType
    source_reference: str = Field(min_length=3, max_length=300)
    feeds_from_activity_ids: list[uuid.UUID] = Field(default_factory=list)
    material: bool = True


class ConstraintProposalInput(BootstrapApiModel):
    activity_id: uuid.UUID
    constraint_type: ScheduleConstraintType
    constraint_date: date
    source_reference: str = Field(min_length=3, max_length=300)


class ScheduleLogicCreate(BootstrapApiModel):
    calendar: PlanningCalendarInput | None = None
    dependencies: list[DependencyProposalInput] = Field(default_factory=list)
    milestones: list[MilestoneProposalInput] = Field(default_factory=list)
    constraints: list[ConstraintProposalInput] = Field(default_factory=list)
    sequence_templates: list[DependencyProposalInput] = Field(default_factory=list)
    validation_owner: str = Field(min_length=3, max_length=200)


class ScheduleLogicRead(BootstrapApiModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID
    generation_id: uuid.UUID
    logic_version: str
    dependencies: list[dict[str, Any]]
    milestones: list[dict[str, Any]]
    constraints: list[dict[str, Any]]
    calendar: dict[str, Any]
    sequence_templates: list[dict[str, Any]]
    assumptions: list[dict[str, Any]]
    warnings: list[dict[str, Any]]
    review_state: PlanningReviewState
    created_by: str
    created_at: datetime


class ScheduleCalculationCreate(BootstrapApiModel):
    project_start: date


class ScheduleCalculationRead(BootstrapApiModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID
    generation_id: uuid.UUID
    logic_proposal_id: uuid.UUID
    calculation_version: str
    project_start: date
    proposed_finish: date | None
    readiness: BootstrapReadiness
    input_hash: str
    activity_results: list[dict[str, Any]]
    milestone_results: list[dict[str, Any]]
    validation_findings: list[dict[str, Any]]
    critical_activity_ids: list[str]
    created_by: str
    created_at: datetime


class PlannerEdit(BootstrapApiModel):
    field_path: str = Field(min_length=3, max_length=300)
    original_value: Any
    revised_value: Any
    reason: str = Field(min_length=10, max_length=2000)


class ScheduleReviewCreate(BootstrapApiModel):
    edits: list[PlannerEdit] = Field(default_factory=list)
    reason: str = Field(min_length=10, max_length=2000)


class ScheduleApprovalCreate(BootstrapApiModel):
    authority_grant_id: uuid.UUID
    approval_reference: str = Field(min_length=3, max_length=500)
    reason: str = Field(min_length=10, max_length=2000)
    authorize_as_baseline: bool = False


class ScheduleReleaseRead(BootstrapApiModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID
    calculation_id: uuid.UUID
    supersedes_release_id: uuid.UUID | None
    version_number: int
    state: BootstrapReadiness
    schedule_payload: dict[str, Any]
    edit_history: list[dict[str, Any]]
    review_reason: str
    authority_grant_id: uuid.UUID | None
    authorized_context_id: uuid.UUID | None
    approval_reference: str | None
    created_by: str
    created_at: datetime


class RevisionDeltaCreate(BootstrapApiModel):
    prior_release_id: uuid.UUID | None = None


class RevisionDeltaRead(BootstrapApiModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID
    prior_source_version_id: uuid.UUID
    new_source_version_id: uuid.UUID
    prior_release_id: uuid.UUID | None
    comparison_version: str
    added_scope: list[dict[str, Any]]
    removed_scope: list[dict[str, Any]]
    changed_scope: list[dict[str, Any]]
    mapping_changes: list[dict[str, Any]]
    activity_changes: list[dict[str, Any]]
    schedule_effects: dict[str, Any]
    current_authorized_context_id: uuid.UUID | None
    created_by: str
    created_at: datetime
