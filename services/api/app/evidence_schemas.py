from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

from app.generated.taxonomies import (
    ContradictionStatus,
    DataClassification,
    EvidenceItemStatus,
    EvidenceRelationType,
    EvidenceRequestStatus,
    ImportBatchStatus,
    SemanticState,
    TruthType,
    UrgencyLevel,
    VerificationOutcome,
)


class EvidenceApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ArtifactRead(EvidenceApiModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID
    storage_key: str
    original_filename: str
    media_type: str
    size_bytes: int
    sha256: str
    source_type: str
    source_id: str
    provided_by_actor: str
    captured_at: datetime | None
    observed_at: datetime | None
    received_at: datetime
    classification: DataClassification
    parser_version: str | None
    scan_result: str
    scan_engine: str
    scan_signature_version: str
    scanned_at: datetime
    supersedes_artifact_id: uuid.UUID | None


class EvidenceItemBase(EvidenceApiModel):
    artifact_id: uuid.UUID | None = None
    controlled_object_id: uuid.UUID | None = None
    field_name: str = Field(min_length=1, max_length=120)
    value: Any
    unit: str | None = Field(default=None, max_length=30)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    measurement_basis: str | None = Field(default=None, max_length=80)
    semantic_state: SemanticState
    truth_type: TruthType
    as_of: datetime
    expires_at: datetime | None = None
    confidence: Decimal = Field(ge=0, le=1)
    source_reliability: Decimal | None = Field(default=None, ge=0, le=1)


class EvidenceItemCreate(EvidenceItemBase):
    as_of: AwareDatetime
    expires_at: AwareDatetime | None = None
    supersedes_item_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def enforce_semantics(self) -> EvidenceItemCreate:
        if (self.value is None) != (self.truth_type == TruthType.UNKNOWN):
            raise ValueError("Only UNKNOWN assertions may have a null value")
        if self.semantic_state == SemanticState.REPORTED and self.truth_type in {
            TruthType.VERIFIED_FACT,
            TruthType.CORROBORATED_FACT,
        }:
            raise ValueError("REPORTED evidence cannot enter as verified/corroborated fact")
        if self.semantic_state == SemanticState.VERIFIED and self.truth_type not in {
            TruthType.VERIFIED_FACT,
            TruthType.CORROBORATED_FACT,
        }:
            raise ValueError("VERIFIED state requires verified or corroborated fact")
        if "progress" in self.field_name.lower() and not self.measurement_basis:
            raise ValueError("Progress evidence requires a measurement basis")
        if self.expires_at and self.expires_at <= self.as_of:
            raise ValueError("expires_at must be after as_of")
        return self


class EvidenceItemRead(EvidenceItemBase):
    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID
    status: EvidenceItemStatus
    supersedes_item_id: uuid.UUID | None
    derived_from_item_id: uuid.UUID | None
    created_by: str
    created_at: datetime
    is_stale: bool


class EvidenceRelationCreate(EvidenceApiModel):
    from_item_id: uuid.UUID
    to_item_id: uuid.UUID
    relation_type: EvidenceRelationType
    rationale: str = Field(min_length=3)

    @model_validator(mode="after")
    def cannot_self_link(self) -> EvidenceRelationCreate:
        if self.from_item_id == self.to_item_id:
            raise ValueError("Evidence item cannot link to itself")
        return self


class EvidenceRelationRead(EvidenceRelationCreate):
    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID
    created_by: str
    created_at: datetime


class VerificationCreate(EvidenceApiModel):
    method: str = Field(min_length=3, max_length=160)
    outcome: VerificationOutcome
    rationale: str = Field(min_length=3)
    verified_confidence: Decimal | None = Field(default=None, ge=0, le=1)

    @model_validator(mode="after")
    def verified_needs_confidence(self) -> VerificationCreate:
        if self.outcome == VerificationOutcome.VERIFIED and self.verified_confidence is None:
            raise ValueError("VERIFIED outcome requires verified_confidence")
        if self.outcome != VerificationOutcome.VERIFIED and self.verified_confidence is not None:
            raise ValueError("Only VERIFIED outcome accepts verified_confidence")
        return self


class VerificationRead(EvidenceApiModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID
    evidence_item_id: uuid.UUID
    result_item_id: uuid.UUID | None
    method: str
    outcome: VerificationOutcome
    rationale: str
    reviewer_actor_id: str
    occurred_at: datetime


class ReliabilityCreate(EvidenceApiModel):
    source_type: str = Field(min_length=1, max_length=80)
    source_id: str = Field(min_length=1, max_length=200)
    evidence_class: str = Field(min_length=1, max_length=80)
    score: Decimal = Field(ge=0, le=1)
    rationale: str = Field(min_length=3)
    valid_from: AwareDatetime


class ReliabilityRead(ReliabilityCreate):
    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID
    assessed_by: str
    created_at: datetime
    valid_from: datetime


class ContradictionCreate(EvidenceApiModel):
    left_item_id: uuid.UUID
    right_item_id: uuid.UUID
    field_name: str = Field(min_length=1, max_length=120)
    material: bool

    @model_validator(mode="after")
    def distinct_items(self) -> ContradictionCreate:
        if self.left_item_id == self.right_item_id:
            raise ValueError("Contradiction requires two different evidence items")
        return self


class ContradictionResolve(EvidenceApiModel):
    chosen_item_id: uuid.UUID | None = None
    resolution_policy: str = Field(min_length=3, max_length=120)
    resolution_reason: str = Field(min_length=3)


class ContradictionRead(ContradictionCreate):
    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID
    controlled_object_id: uuid.UUID | None
    status: ContradictionStatus
    resolution_policy: str | None
    chosen_item_id: uuid.UUID | None
    resolution_reason: str | None
    resolved_by: str | None
    resolved_at: datetime | None
    created_by: str
    created_at: datetime


class EvidenceRequestCreate(EvidenceApiModel):
    controlled_object_id: uuid.UUID | None = None
    requested_fields: list[str] = Field(min_length=1)
    reason: str = Field(min_length=3)
    urgency: UrgencyLevel
    owner_actor_id: str = Field(min_length=1, max_length=200)
    due_at: AwareDatetime

    @field_validator("requested_fields")
    @classmethod
    def unique_fields(cls, value: list[str]) -> list[str]:
        cleaned = [field.strip() for field in value if field.strip()]
        if not cleaned or len(cleaned) != len(set(cleaned)):
            raise ValueError("requested_fields must be non-empty and unique")
        return cleaned


class EvidenceRequestSatisfy(EvidenceApiModel):
    evidence_item_id: uuid.UUID


class EvidenceRequestRead(EvidenceRequestCreate):
    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID
    status: EvidenceRequestStatus
    satisfied_by_item_id: uuid.UUID | None
    created_by: str
    created_at: datetime
    due_at: datetime


class ImportPreviewCreate(EvidenceApiModel):
    artifact_id: uuid.UUID
    mapping: dict[str, str] = Field(default_factory=dict)


class ImportBatchRead(EvidenceApiModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID
    artifact_id: uuid.UUID
    import_format: str
    mapping: dict[str, str]
    normalized_rows: list[dict[str, Any]]
    validation_errors: list[dict[str, Any]]
    status: ImportBatchStatus
    total_rows: int
    valid_rows: int
    rejected_rows: int
    idempotency_key: str
    created_by: str
    created_at: datetime
    committed_at: datetime | None


class ImportCommitRead(EvidenceApiModel):
    batch: ImportBatchRead
    evidence_item_ids: list[uuid.UUID]
