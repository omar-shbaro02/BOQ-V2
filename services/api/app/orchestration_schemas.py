from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.case_schemas import DecisionCaseRead
from app.generated.taxonomies import (
    DecisionReadiness,
    Disposition,
    OrchestrationStatus,
    SpecialistContradictionType,
    SpecialistKind,
    SpecialistRunStatus,
)


class OrchestrationApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class OrchestrationCreate(OrchestrationApiModel):
    expected_version: int = Field(ge=1)
    snapshot_id: uuid.UUID
    retry_of_run_id: uuid.UUID | None = None
    contradiction_resolution_ids: list[uuid.UUID] = Field(default_factory=list)
    progress_evaluation_id: uuid.UUID | None = None
    schedule_assessment_id: uuid.UUID | None = None
    cost_assessment_id: uuid.UUID | None = None
    forecast_projection_ids: list[uuid.UUID] = Field(default_factory=list)
    impact_assessment_id: uuid.UUID | None = None
    requested_questions: list[str] = Field(default_factory=list, max_length=20)


class SpecialistRunRead(OrchestrationApiModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID
    orchestration_run_id: uuid.UUID
    case_id: uuid.UUID
    snapshot_id: uuid.UUID
    specialist_kind: SpecialistKind
    status: SpecialistRunStatus
    attempt: int
    input_references: dict[str, Any]
    output_references: dict[str, Any]
    findings: list[dict[str, Any]]
    calculations: list[dict[str, Any]]
    evidence_references: list[str]
    truth_labels: list[str]
    assumptions: list[str]
    contradictions: list[dict[str, Any]]
    confidence: Decimal
    limitations: list[dict[str, Any]]
    requested_evidence: list[dict[str, Any]]
    contract_version: str
    error_class: str | None
    started_at: datetime
    completed_at: datetime | None


class OrchestrationRunRead(OrchestrationApiModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID
    case_id: uuid.UUID
    snapshot_id: uuid.UUID
    retry_of_run_id: uuid.UUID | None
    run_number: int
    status: OrchestrationStatus
    readiness: DecisionReadiness
    recommended_disposition: Disposition | None
    alternative_dispositions: list[dict[str, Any]]
    blockers: list[dict[str, Any]]
    limitations: list[dict[str, Any]]
    contradiction_findings: list[dict[str, Any]]
    case_brief: dict[str, Any]
    policy_versions: dict[str, str]
    formula_version: str
    idempotency_key: str
    request_hash: str
    created_by: str
    started_at: datetime
    completed_at: datetime | None
    specialist_runs: list[SpecialistRunRead] = Field(default_factory=list)


class OrchestrationResult(OrchestrationApiModel):
    case: DecisionCaseRead
    run: OrchestrationRunRead


class ContradictionResolutionCreate(OrchestrationApiModel):
    expected_version: int = Field(ge=1)
    contradiction_index: int = Field(ge=0)
    selected_result_id: str = Field(min_length=1, max_length=80)
    rejected_result_ids: list[str] = Field(default_factory=list)
    resolution_basis: str = Field(min_length=20)


class ContradictionResolutionRead(OrchestrationApiModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID
    case_id: uuid.UUID
    snapshot_id: uuid.UUID
    orchestration_run_id: uuid.UUID
    contradiction_index: int
    contradiction_type: SpecialistContradictionType
    source_result_ids: list[str]
    selected_result_id: str
    rejected_result_ids: list[str]
    resolution_basis: str
    downstream_invalidations: list[str]
    resolved_by: str
    resolved_at: datetime


class ContradictionResolutionResult(OrchestrationApiModel):
    case: DecisionCaseRead
    resolution: ContradictionResolutionRead


class NarrativeValidationCreate(OrchestrationApiModel):
    narrative: str = Field(min_length=1, max_length=20000)


class NarrativeValidationRead(OrchestrationApiModel):
    valid: bool
    violations: list[dict[str, str]]
    run_id: uuid.UUID
    formula_version: str
