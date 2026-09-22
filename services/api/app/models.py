from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Organization(Base):
    __tablename__ = "organization"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Project(Base):
    __tablename__ = "project"
    __table_args__ = (UniqueConstraint("organization_id", "code", name="uq_project_org_code"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="RESTRICT"), index=True
    )
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    timezone: Mapped[str] = mapped_column(String(80), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    delivery_model: Mapped[str] = mapped_column(String(80), nullable=False)
    reporting_cadence: Mapped[str] = mapped_column(String(40), nullable=False)
    calendar_config: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="DRAFT")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Membership(Base):
    __tablename__ = "membership"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "project_id", "actor_id", "role", name="uq_membership_scope_role"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("project.id", ondelete="CASCADE"), index=True
    )
    actor_id: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(60), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ControlledObject(Base):
    __tablename__ = "controlled_object"
    __table_args__ = (
        UniqueConstraint("project_id", "code", name="uq_controlled_object_project_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="RESTRICT"), index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="CASCADE"), index=True
    )
    object_type: Mapped[str] = mapped_column(String(40), nullable=False)
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    owner_actor_id: Mapped[str | None] = mapped_column(String(200))
    attributes: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ControlledObjectRelation(Base):
    __tablename__ = "controlled_object_relation"
    __table_args__ = (
        UniqueConstraint(
            "source_id", "target_id", "relation_type", name="uq_controlled_object_relation"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="RESTRICT"), index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="CASCADE"), index=True
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("controlled_object.id", ondelete="CASCADE"), index=True
    )
    target_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("controlled_object.id", ondelete="CASCADE"), index=True
    )
    relation_type: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuthorityGrant(Base):
    __tablename__ = "authority_grant"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="RESTRICT"), index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="CASCADE"), index=True
    )
    actor_id: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    authority_type: Mapped[str] = mapped_column(String(80), nullable=False)
    controlled_object_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("controlled_object.id", ondelete="CASCADE")
    )
    max_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    currency: Mapped[str | None] = mapped_column(String(3))
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_until: Mapped[date | None] = mapped_column(Date)
    escalation_level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    escalates_to_actor_id: Mapped[str | None] = mapped_column(String(200))
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class AuthorizedContextVersion(Base):
    __tablename__ = "authorized_context_version"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "context_type", "version_number", name="uq_context_project_type_version"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="RESTRICT"), index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="RESTRICT"), index=True
    )
    context_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    semantic_state: Mapped[str] = mapped_column(String(30), nullable=False)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    source_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("authorized_context_version.id", ondelete="RESTRICT")
    )
    approval_reference: Mapped[str | None] = mapped_column(Text)
    activation_reason: Mapped[str | None] = mapped_column(Text)
    activated_by: Mapped[str | None] = mapped_column(String(200))
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditEvent(Base):
    __tablename__ = "audit_event"

    event_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organization.id", ondelete="RESTRICT"), index=True
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("project.id", ondelete="RESTRICT"), index=True
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    actor_id: Mapped[str] = mapped_column(Text, nullable=False)
    actor_type: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    object_type: Mapped[str] = mapped_column(Text, nullable=False)
    object_id: Mapped[str] = mapped_column(Text, nullable=False)
    object_version: Mapped[int | None] = mapped_column(Integer)
    correlation_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, default=uuid.uuid4)
    authority_result: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class EvidenceArtifact(Base):
    __tablename__ = "evidence_artifact"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="RESTRICT"), index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="RESTRICT"), index=True
    )
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    media_type: Mapped[str] = mapped_column(String(150), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(80), nullable=False)
    source_id: Mapped[str] = mapped_column(String(200), nullable=False)
    provided_by_actor: Mapped[str] = mapped_column(String(200), nullable=False)
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    classification: Mapped[str] = mapped_column(String(30), nullable=False)
    parser_version: Mapped[str | None] = mapped_column(String(80))
    scan_result: Mapped[str] = mapped_column(String(20), nullable=False)
    scan_engine: Mapped[str] = mapped_column(String(80), nullable=False)
    scan_signature_version: Mapped[str] = mapped_column(String(80), nullable=False)
    scanned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    supersedes_artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("evidence_artifact.id", ondelete="RESTRICT")
    )


class BoqSourceVersion(Base):
    __tablename__ = "boq_source_version"
    __table_args__ = (
        UniqueConstraint("project_id", "version_number", name="uq_boq_source_project_version"),
        UniqueConstraint("project_id", "artifact_id", name="uq_boq_source_project_artifact"),
        UniqueConstraint("project_id", "idempotency_key", name="uq_boq_source_idempotency"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="RESTRICT"), index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="RESTRICT"), index=True
    )
    artifact_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evidence_artifact.id", ondelete="RESTRICT"), index=True
    )
    prior_source_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("boq_source_version.id", ondelete="RESTRICT"), index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    source_format: Mapped[str] = mapped_column(String(20), nullable=False)
    parser_name: Mapped[str] = mapped_column(String(80), nullable=False)
    parser_version: Mapped[str] = mapped_column(String(40), nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    extraction_status: Mapped[str] = mapped_column(String(40), nullable=False)
    extraction_confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    structure_manifest: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    warnings: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    extracted_row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BoqSourceRow(Base):
    __tablename__ = "boq_source_row"
    __table_args__ = (
        UniqueConstraint("source_version_id", "sequence_number", name="uq_boq_row_sequence"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="RESTRICT"), index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="RESTRICT"), index=True
    )
    source_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("boq_source_version.id", ondelete="RESTRICT"), index=True
    )
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    sheet_name: Mapped[str | None] = mapped_column(String(200))
    page_number: Mapped[int | None] = mapped_column(Integer)
    row_number: Mapped[int | None] = mapped_column(Integer)
    region: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    raw_values: Mapped[list[Any]] = mapped_column(JSON, nullable=False)
    original_text: Mapped[str | None] = mapped_column(Text)
    extraction_confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    warnings: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BoqNormalizationRun(Base):
    __tablename__ = "boq_normalization_run"
    __table_args__ = (
        UniqueConstraint("source_version_id", name="uq_boq_normalization_source"),
        UniqueConstraint("project_id", "idempotency_key", name="uq_boq_normalization_idempotency"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="RESTRICT"), index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="RESTRICT"), index=True
    )
    source_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("boq_source_version.id", ondelete="RESTRICT"), index=True
    )
    normalizer_version: Mapped[str] = mapped_column(String(40), nullable=False)
    header_rows: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    column_mapping: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    warnings: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    total_rows: Mapped[int] = mapped_column(Integer, nullable=False)
    schedule_relevant_rows: Mapped[int] = mapped_column(Integer, nullable=False)
    review_required_rows: Mapped[int] = mapped_column(Integer, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BoqLine(Base):
    __tablename__ = "boq_line"
    __table_args__ = (
        UniqueConstraint("normalization_run_id", "source_row_id", name="uq_boq_line_source_row"),
        UniqueConstraint("source_version_id", "stable_line_id", name="uq_boq_stable_line"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    stable_line_id: Mapped[str] = mapped_column(String(80), nullable=False)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="RESTRICT"), index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="RESTRICT"), index=True
    )
    normalization_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("boq_normalization_run.id", ondelete="RESTRICT"), index=True
    )
    source_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("boq_source_version.id", ondelete="RESTRICT"), index=True
    )
    source_row_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("boq_source_row.id", ondelete="RESTRICT"), index=True
    )
    source_location: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    item_number: Mapped[str | None] = mapped_column(String(160))
    division: Mapped[str | None] = mapped_column(String(240))
    source_wbs_code: Mapped[str | None] = mapped_column(String(160))
    item_name: Mapped[str | None] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text)
    unit: Mapped[str | None] = mapped_column(String(80))
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(24, 6))
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(24, 6))
    total_price: Mapped[Decimal | None] = mapped_column(Numeric(24, 6))
    currency: Mapped[str | None] = mapped_column(String(3))
    location: Mapped[str | None] = mapped_column(String(240))
    trade: Mapped[str | None] = mapped_column(String(160))
    package: Mapped[str | None] = mapped_column(String(240))
    notes: Mapped[str | None] = mapped_column(Text)
    parent_section: Mapped[str | None] = mapped_column(String(300))
    source_row_text: Mapped[str | None] = mapped_column(Text)
    normalized_values: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    unmapped_values: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    classification: Mapped[str] = mapped_column(String(60), nullable=False)
    classification_basis: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    schedule_relevant: Mapped[bool] = mapped_column(Boolean, nullable=False)
    confidence: Mapped[str] = mapped_column(String(20), nullable=False)
    review_state: Mapped[str] = mapped_column(String(30), nullable=False)
    warnings: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BoqPlanningStructureVersion(Base):
    __tablename__ = "boq_planning_structure_version"
    __table_args__ = (
        UniqueConstraint("normalization_run_id", "version_number", name="uq_boq_structure_version"),
        UniqueConstraint("project_id", "idempotency_key", name="uq_boq_structure_idempotency"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="RESTRICT"), index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="RESTRICT"), index=True
    )
    normalization_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("boq_normalization_run.id", ondelete="RESTRICT"), index=True
    )
    supersedes_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("boq_planning_structure_version.id", ondelete="RESTRICT"), index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    wbs_nodes: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    work_packages: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    line_mappings: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    unmapped_lines: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    assumptions: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    warnings: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    change_summary: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ScheduleDraftGeneration(Base):
    __tablename__ = "schedule_draft_generation"
    __table_args__ = (
        UniqueConstraint("planning_structure_id", name="uq_schedule_generation_structure"),
        UniqueConstraint(
            "project_id", "idempotency_key", name="uq_schedule_generation_idempotency"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="RESTRICT"), index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="RESTRICT"), index=True
    )
    planning_structure_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("boq_planning_structure_version.id", ondelete="RESTRICT"), index=True
    )
    generator_version: Mapped[str] = mapped_column(String(40), nullable=False)
    draft_state: Mapped[str] = mapped_column(String(40), nullable=False)
    productivity_inputs: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    duration_inputs: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    warnings: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    activity_count: Mapped[int] = mapped_column(Integer, nullable=False)
    unresolved_duration_count: Mapped[int] = mapped_column(Integer, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProposedScheduleActivity(Base):
    __tablename__ = "proposed_schedule_activity"
    __table_args__ = (
        UniqueConstraint("generation_id", "activity_code", name="uq_proposed_activity_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="RESTRICT"), index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="RESTRICT"), index=True
    )
    generation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schedule_draft_generation.id", ondelete="RESTRICT"), index=True
    )
    activity_code: Mapped[str] = mapped_column(String(80), nullable=False)
    wbs_node_id: Mapped[str] = mapped_column(String(80), nullable=False)
    work_package_id: Mapped[str] = mapped_column(String(80), nullable=False)
    boq_line_refs: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    activity_name: Mapped[str] = mapped_column(String(300), nullable=False)
    activity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    trade: Mapped[str | None] = mapped_column(String(160))
    location: Mapped[str | None] = mapped_column(String(240))
    description: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(24, 6))
    unit: Mapped[str | None] = mapped_column(String(80))
    duration_working_days: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    duration_unrounded: Mapped[Decimal | None] = mapped_column(Numeric(24, 10))
    duration_status: Mapped[str] = mapped_column(String(40), nullable=False)
    duration_basis: Mapped[str] = mapped_column(String(50), nullable=False)
    productivity: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    calendar_id: Mapped[str | None] = mapped_column(String(80))
    responsible_role: Mapped[str | None] = mapped_column(String(160))
    confidence: Mapped[str] = mapped_column(String(20), nullable=False)
    review_state: Mapped[str] = mapped_column(String(30), nullable=False)
    warnings: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PlanningAssumption(Base):
    __tablename__ = "planning_assumption"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="RESTRICT"), index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="RESTRICT"), index=True
    )
    generation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schedule_draft_generation.id", ondelete="RESTRICT"), index=True
    )
    proposition: Mapped[str] = mapped_column(Text, nullable=False)
    reason_needed: Mapped[str] = mapped_column(Text, nullable=False)
    affected_activity_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    source_basis: Mapped[str] = mapped_column(String(200), nullable=False)
    confidence: Mapped[str] = mapped_column(String(20), nullable=False)
    consequence_if_wrong: Mapped[str] = mapped_column(Text, nullable=False)
    validation_owner: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    resolution_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ScheduleLogicProposal(Base):
    __tablename__ = "schedule_logic_proposal"
    __table_args__ = (
        UniqueConstraint("generation_id", name="uq_schedule_logic_generation"),
        UniqueConstraint("project_id", "idempotency_key", name="uq_schedule_logic_idempotency"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="RESTRICT"), index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="RESTRICT"), index=True
    )
    generation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schedule_draft_generation.id", ondelete="RESTRICT"), index=True
    )
    logic_version: Mapped[str] = mapped_column(String(40), nullable=False)
    dependencies: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    milestones: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    constraints: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    calendar: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    sequence_templates: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    assumptions: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    warnings: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    review_state: Mapped[str] = mapped_column(String(30), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BootstrapScheduleCalculation(Base):
    __tablename__ = "bootstrap_schedule_calculation"
    __table_args__ = (
        UniqueConstraint("logic_proposal_id", name="uq_bootstrap_calculation_logic"),
        UniqueConstraint("project_id", "idempotency_key", name="uq_bootstrap_calculation_idem"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="RESTRICT"), index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="RESTRICT"), index=True
    )
    generation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schedule_draft_generation.id", ondelete="RESTRICT"), index=True
    )
    logic_proposal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schedule_logic_proposal.id", ondelete="RESTRICT"), index=True
    )
    calculation_version: Mapped[str] = mapped_column(String(40), nullable=False)
    project_start: Mapped[date] = mapped_column(Date, nullable=False)
    proposed_finish: Mapped[date | None] = mapped_column(Date)
    readiness: Mapped[str] = mapped_column(String(40), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    activity_results: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    milestone_results: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    validation_findings: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    critical_activity_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BootstrapScheduleRelease(Base):
    __tablename__ = "bootstrap_schedule_release"
    __table_args__ = (
        UniqueConstraint("calculation_id", "version_number", name="uq_bootstrap_release_version"),
        UniqueConstraint("project_id", "idempotency_key", name="uq_bootstrap_release_idem"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="RESTRICT"), index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="RESTRICT"), index=True
    )
    calculation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("bootstrap_schedule_calculation.id", ondelete="RESTRICT"), index=True
    )
    supersedes_release_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("bootstrap_schedule_release.id", ondelete="RESTRICT"), index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String(40), nullable=False)
    schedule_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    edit_history: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    review_reason: Mapped[str] = mapped_column(Text, nullable=False)
    authority_grant_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("authority_grant.id", ondelete="RESTRICT")
    )
    authorized_context_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("authorized_context_version.id", ondelete="RESTRICT")
    )
    approval_reference: Mapped[str | None] = mapped_column(Text)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BootstrapRevisionDelta(Base):
    __tablename__ = "bootstrap_revision_delta"
    __table_args__ = (
        UniqueConstraint("new_source_version_id", name="uq_bootstrap_delta_new_source"),
        UniqueConstraint("project_id", "idempotency_key", name="uq_bootstrap_delta_idem"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="RESTRICT"), index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="RESTRICT"), index=True
    )
    prior_source_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("boq_source_version.id", ondelete="RESTRICT"), index=True
    )
    new_source_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("boq_source_version.id", ondelete="RESTRICT"), index=True
    )
    prior_release_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("bootstrap_schedule_release.id", ondelete="RESTRICT")
    )
    comparison_version: Mapped[str] = mapped_column(String(40), nullable=False)
    added_scope: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    removed_scope: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    changed_scope: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    mapping_changes: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    activity_changes: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    schedule_effects: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    current_authorized_context_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("authorized_context_version.id", ondelete="RESTRICT")
    )
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EvidenceItem(Base):
    __tablename__ = "evidence_item"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="RESTRICT"), index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="RESTRICT"), index=True
    )
    artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("evidence_artifact.id", ondelete="RESTRICT"), index=True
    )
    controlled_object_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("controlled_object.id", ondelete="RESTRICT"), index=True
    )
    field_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    value: Mapped[Any] = mapped_column(JSON, nullable=False)
    unit: Mapped[str | None] = mapped_column(String(30))
    currency: Mapped[str | None] = mapped_column(String(3))
    measurement_basis: Mapped[str | None] = mapped_column(String(80))
    semantic_state: Mapped[str] = mapped_column(String(30), nullable=False)
    truth_type: Mapped[str] = mapped_column(String(30), nullable=False)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    source_reliability: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")
    supersedes_item_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("evidence_item.id", ondelete="RESTRICT")
    )
    derived_from_item_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("evidence_item.id", ondelete="RESTRICT")
    )
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    @property
    def is_stale(self) -> bool:
        if self.expires_at is None:
            return False
        expiry = self.expires_at
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=UTC)
        return expiry <= datetime.now(UTC)


class EvidenceRelation(Base):
    __tablename__ = "evidence_relation"
    __table_args__ = (
        UniqueConstraint(
            "from_item_id", "to_item_id", "relation_type", name="uq_evidence_relation"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="RESTRICT"), index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="RESTRICT"), index=True
    )
    from_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evidence_item.id", ondelete="CASCADE"), index=True
    )
    to_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evidence_item.id", ondelete="CASCADE"), index=True
    )
    relation_type: Mapped[str] = mapped_column(String(30), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class VerificationEvent(Base):
    __tablename__ = "verification_event"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="RESTRICT"), index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="RESTRICT"), index=True
    )
    evidence_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evidence_item.id", ondelete="RESTRICT"), index=True
    )
    result_item_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("evidence_item.id", ondelete="RESTRICT")
    )
    method: Mapped[str] = mapped_column(String(160), nullable=False)
    outcome: Mapped[str] = mapped_column(String(30), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    reviewer_actor_id: Mapped[str] = mapped_column(String(200), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class SourceReliabilityAssessment(Base):
    __tablename__ = "source_reliability_assessment"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="RESTRICT"), index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="RESTRICT"), index=True
    )
    source_type: Mapped[str] = mapped_column(String(80), nullable=False)
    source_id: Mapped[str] = mapped_column(String(200), nullable=False)
    evidence_class: Mapped[str] = mapped_column(String(80), nullable=False)
    score: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    assessed_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Contradiction(Base):
    __tablename__ = "contradiction"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="RESTRICT"), index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="RESTRICT"), index=True
    )
    controlled_object_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("controlled_object.id", ondelete="RESTRICT"), index=True
    )
    left_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evidence_item.id", ondelete="RESTRICT")
    )
    right_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evidence_item.id", ondelete="RESTRICT")
    )
    field_name: Mapped[str] = mapped_column(String(120), nullable=False)
    material: Mapped[bool] = mapped_column(Boolean, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="OPEN")
    resolution_policy: Mapped[str | None] = mapped_column(String(120))
    chosen_item_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("evidence_item.id", ondelete="RESTRICT")
    )
    resolution_reason: Mapped[str | None] = mapped_column(Text)
    resolved_by: Mapped[str | None] = mapped_column(String(200))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EvidenceRequest(Base):
    __tablename__ = "evidence_request"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="RESTRICT"), index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="RESTRICT"), index=True
    )
    controlled_object_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("controlled_object.id", ondelete="RESTRICT"), index=True
    )
    requested_fields: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    urgency: Mapped[str] = mapped_column(String(20), nullable=False)
    owner_actor_id: Mapped[str] = mapped_column(String(200), nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="OPEN")
    satisfied_by_item_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("evidence_item.id", ondelete="RESTRICT")
    )
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ImportBatch(Base):
    __tablename__ = "import_batch"
    __table_args__ = (
        UniqueConstraint("project_id", "idempotency_key", name="uq_import_batch_idempotency"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="RESTRICT"), index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="RESTRICT"), index=True
    )
    artifact_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evidence_artifact.id", ondelete="RESTRICT"), index=True
    )
    import_format: Mapped[str] = mapped_column(String(10), nullable=False)
    mapping: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False)
    normalized_rows: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    validation_errors: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    total_rows: Mapped[int] = mapped_column(Integer, nullable=False)
    valid_rows: Mapped[int] = mapped_column(Integer, nullable=False)
    rejected_rows: Mapped[int] = mapped_column(Integer, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    committed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ImportBatchItem(Base):
    __tablename__ = "import_batch_item"

    batch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("import_batch.id", ondelete="CASCADE"), primary_key=True
    )
    evidence_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evidence_item.id", ondelete="RESTRICT"), primary_key=True
    )


class Signal(Base):
    __tablename__ = "signal"
    __table_args__ = (
        UniqueConstraint("project_id", "fingerprint", name="uq_signal_project_fingerprint"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="RESTRICT"), index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="RESTRICT"), index=True
    )
    controlled_object_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("controlled_object.id", ondelete="RESTRICT"), index=True
    )
    signal_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    source_field: Mapped[str] = mapped_column(String(120), nullable=False)
    source_evidence_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    source_contradiction_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("contradiction.id", ondelete="RESTRICT")
    )
    observed_value: Mapped[Any] = mapped_column(JSON, nullable=False)
    detector_details: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    materiality_candidate: Mapped[str] = mapped_column(String(20), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    occurrence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    detector_name: Mapped[str] = mapped_column(String(100), nullable=False)
    detector_version: Mapped[str] = mapped_column(String(40), nullable=False)
    first_observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deferred_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    workflow_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    @property
    def is_expired(self) -> bool:
        expiry = self.expires_at
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=UTC)
        return expiry <= datetime.now(UTC)


class SignalEvidence(Base):
    __tablename__ = "signal_evidence"

    signal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("signal.id", ondelete="CASCADE"), primary_key=True
    )
    evidence_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evidence_item.id", ondelete="RESTRICT"), primary_key=True
    )


class SignalDetectionRun(Base):
    __tablename__ = "signal_detection_run"
    __table_args__ = (
        UniqueConstraint("project_id", "idempotency_key", name="uq_detection_run_idempotency"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="RESTRICT"), index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="RESTRICT"), index=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    detector_version: Mapped[str] = mapped_column(String(40), nullable=False)
    signal_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SignalScreeningDecision(Base):
    __tablename__ = "signal_screening_decision"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="RESTRICT"), index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="RESTRICT"), index=True
    )
    signal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("signal.id", ondelete="RESTRICT"), index=True
    )
    signal_version: Mapped[int] = mapped_column(Integer, nullable=False)
    outcome: Mapped[str] = mapped_column(String(20), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(50), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    materiality_candidate: Mapped[str] = mapped_column(String(20), nullable=False)
    defer_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_by: Mapped[str] = mapped_column(String(200), nullable=False)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DecisionCaseShell(Base):
    __tablename__ = "decision_case"
    __table_args__ = (
        UniqueConstraint("project_id", "case_number", name="uq_decision_case_number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="RESTRICT"), index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="RESTRICT"), index=True
    )
    case_number: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    case_type: Mapped[str] = mapped_column(String(60), nullable=False)
    lifecycle: Mapped[str] = mapped_column(String(30), nullable=False)
    owner_actor_id: Mapped[str] = mapped_column(String(200), nullable=False)
    parent_case_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("decision_case.id", ondelete="RESTRICT"), index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    readiness: Mapped[str | None] = mapped_column(String(50))
    governance_state: Mapped[str] = mapped_column(
        String(40), nullable=False, default="HUMAN_REVIEW_REQUIRED"
    )
    autonomy_class: Mapped[str] = mapped_column(
        String(40), nullable=False, default="A1_ANALYTICAL_AUTONOMY"
    )
    blocked_from_lifecycle: Mapped[str | None] = mapped_column(String(30))
    blocker_code: Mapped[str | None] = mapped_column(String(80))
    blocker_description: Mapped[str | None] = mapped_column(Text)
    last_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(
            "case_snapshot.id",
            name="fk_decision_case_last_snapshot",
            ondelete="RESTRICT",
            use_alter=True,
        )
    )
    last_progress_evaluation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(
            "progress_evaluation.id",
            name="fk_decision_case_last_progress_evaluation",
            ondelete="RESTRICT",
            use_alter=True,
        )
    )
    last_schedule_assessment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(
            "schedule_assessment.id",
            name="fk_decision_case_last_schedule_assessment",
            ondelete="RESTRICT",
            use_alter=True,
        )
    )
    last_cost_assessment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(
            "cost_assessment.id",
            name="fk_decision_case_last_cost_assessment",
            ondelete="RESTRICT",
            use_alter=True,
        )
    )
    last_forecast_projection_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(
            "forecast_projection.id",
            name="fk_decision_case_last_forecast_projection",
            ondelete="RESTRICT",
            use_alter=True,
        )
    )
    last_impact_assessment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(
            "impact_assessment.id",
            name="fk_decision_case_last_impact_assessment",
            ondelete="RESTRICT",
            use_alter=True,
        )
    )
    last_orchestration_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(
            "orchestration_run.id",
            name="fk_decision_case_last_orchestration_run",
            ondelete="RESTRICT",
            use_alter=True,
        )
    )
    last_human_decision_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(
            "human_decision.id",
            name="fk_decision_case_last_human_decision",
            ondelete="RESTRICT",
            use_alter=True,
        )
    )
    outcome_reference: Mapped[str | None] = mapped_column(String(200))
    close_reason: Mapped[str | None] = mapped_column(Text)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reopen_trigger: Mapped[str | None] = mapped_column(String(50))
    reopen_reason: Mapped[str | None] = mapped_column(Text)
    reopened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DecisionCaseControlledObject(Base):
    __tablename__ = "decision_case_controlled_object"

    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("decision_case.id", ondelete="CASCADE"), primary_key=True
    )
    controlled_object_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("controlled_object.id", ondelete="RESTRICT"), primary_key=True
    )


class DecisionCaseSignal(Base):
    __tablename__ = "decision_case_signal"

    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("decision_case.id", ondelete="CASCADE"), primary_key=True
    )
    signal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("signal.id", ondelete="RESTRICT"), primary_key=True
    )
    correlation_rationale: Mapped[str] = mapped_column(Text, nullable=False)
    linked_by: Mapped[str] = mapped_column(String(200), nullable=False)
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SignalCorrelationSuggestion(Base):
    __tablename__ = "signal_correlation_suggestion"
    __table_args__ = (
        UniqueConstraint("signal_id", "signal_version", name="uq_correlation_signal_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="RESTRICT"), index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="RESTRICT"), index=True
    )
    signal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("signal.id", ondelete="RESTRICT"), index=True
    )
    signal_version: Mapped[int] = mapped_column(Integer, nullable=False)
    suggested_outcome: Mapped[str] = mapped_column(String(40), nullable=False)
    target_case_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("decision_case.id", ondelete="RESTRICT")
    )
    child_case_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SignalCorrelationReview(Base):
    __tablename__ = "signal_correlation_review"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="RESTRICT"), index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="RESTRICT"), index=True
    )
    suggestion_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("signal_correlation_suggestion.id", ondelete="RESTRICT"), unique=True
    )
    selected_outcome: Mapped[str | None] = mapped_column(String(40))
    target_case_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("decision_case.id", ondelete="RESTRICT")
    )
    created_case_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("decision_case.id", ondelete="RESTRICT")
    )
    child_case_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    reviewed_by: Mapped[str] = mapped_column(String(200), nullable=False)
    reviewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class OutboxEvent(Base):
    __tablename__ = "outbox_event"

    event_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="RESTRICT"), index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="RESTRICT"), index=True
    )
    event_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    schema_version: Mapped[str] = mapped_column(String(20), nullable=False)
    aggregate_type: Mapped[str] = mapped_column(String(60), nullable=False)
    aggregate_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    aggregate_version: Mapped[int] = mapped_column(Integer, nullable=False)
    actor_id: Mapped[str] = mapped_column(String(200), nullable=False)
    correlation_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    causation_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    data_classification: Mapped[str] = mapped_column(String(30), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CaseEvidenceAttachment(Base):
    __tablename__ = "case_evidence_attachment"

    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("decision_case.id", ondelete="CASCADE"), primary_key=True
    )
    evidence_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evidence_item.id", ondelete="RESTRICT"), primary_key=True
    )
    attachment_reason: Mapped[str] = mapped_column(Text, nullable=False)
    attached_by: Mapped[str] = mapped_column(String(200), nullable=False)
    attached_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class CaseActiveResponse(Base):
    __tablename__ = "case_active_response"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="RESTRICT"), index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="RESTRICT"), index=True
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("decision_case.id", ondelete="CASCADE"), index=True
    )
    response_type: Mapped[str] = mapped_column(String(80), nullable=False)
    authorization_reference: Mapped[str] = mapped_column(String(200), nullable=False)
    owner_actor_id: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    details: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    recorded_by: Mapped[str] = mapped_column(String(200), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class CaseSnapshot(Base):
    __tablename__ = "case_snapshot"
    __table_args__ = (
        UniqueConstraint("case_id", "snapshot_number", name="uq_case_snapshot_number"),
        UniqueConstraint("case_id", "idempotency_key", name="uq_case_snapshot_idempotency"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="RESTRICT"), index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="RESTRICT"), index=True
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("decision_case.id", ondelete="RESTRICT"), index=True
    )
    snapshot_number: Mapped[int] = mapped_column(Integer, nullable=False)
    case_version: Mapped[int] = mapped_column(Integer, nullable=False)
    data_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    controlled_object_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    signal_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    evidence_item_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    contradiction_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    authorized_context_refs: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    active_response_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    baseline_validity: Mapped[str] = mapped_column(String(30), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(40), nullable=False)
    snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CaseBaselineAssessment(Base):
    __tablename__ = "case_baseline_assessment"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="RESTRICT"), index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="RESTRICT"), index=True
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("decision_case.id", ondelete="RESTRICT"), index=True
    )
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("case_snapshot.id", ondelete="RESTRICT"), index=True
    )
    authorized_context_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("authorized_context_version.id", ondelete="RESTRICT")
    )
    validity: Mapped[str] = mapped_column(String(30), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    assessed_by: Mapped[str] = mapped_column(String(200), nullable=False)
    assessed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class CaseSufficiencyAssessment(Base):
    __tablename__ = "case_sufficiency_assessment"
    __table_args__ = (
        UniqueConstraint("snapshot_id", "conclusion_type", name="uq_snapshot_conclusion"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="RESTRICT"), index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="RESTRICT"), index=True
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("decision_case.id", ondelete="RESTRICT"), index=True
    )
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("case_snapshot.id", ondelete="RESTRICT"), index=True
    )
    conclusion_type: Mapped[str] = mapped_column(String(50), nullable=False)
    readiness: Mapped[str] = mapped_column(String(50), nullable=False)
    present_evidence: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    missing_evidence: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    stale_evidence_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    weak_evidence_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    contradictory_evidence: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    limitation_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    evidence_request_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    maximum_supported_conclusion: Mapped[str] = mapped_column(String(80), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(40), nullable=False)
    assessed_by: Mapped[str] = mapped_column(String(200), nullable=False)
    assessed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class CaseLimitation(Base):
    __tablename__ = "case_limitation"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="RESTRICT"), index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="RESTRICT"), index=True
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("decision_case.id", ondelete="RESTRICT"), index=True
    )
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("case_snapshot.id", ondelete="RESTRICT"), index=True
    )
    code: Mapped[str] = mapped_column(String(60), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    material: Mapped[bool] = mapped_column(Boolean, nullable=False)
    owner_actor_id: Mapped[str] = mapped_column(String(200), nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    resolution: Mapped[str | None] = mapped_column(Text)
    resolved_by: Mapped[str | None] = mapped_column(String(200))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CaseLedgerEvent(Base):
    __tablename__ = "case_ledger_event"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="RESTRICT"), index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="RESTRICT"), index=True
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("decision_case.id", ondelete="RESTRICT"), index=True
    )
    case_version: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    from_lifecycle: Mapped[str | None] = mapped_column(String(30))
    to_lifecycle: Mapped[str | None] = mapped_column(String(30))
    actor_id: Mapped[str] = mapped_column(String(200), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ProgressThresholdPolicy(Base):
    __tablename__ = "progress_threshold_policy"
    __table_args__ = (
        UniqueConstraint("project_id", "policy_version", name="uq_progress_policy_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="RESTRICT"), index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="RESTRICT"), index=True
    )
    policy_version: Mapped[str] = mapped_column(String(40), nullable=False)
    deviation_threshold: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    on_plan_tolerance: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    persistence_min_observations: Mapped[int] = mapped_column(Integer, nullable=False)
    persistence_min_duration_days: Mapped[int] = mapped_column(Integer, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    supersedes_policy_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("progress_threshold_policy.id", ondelete="RESTRICT")
    )
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProgressMeasurement(Base):
    __tablename__ = "progress_measurement"
    __table_args__ = (
        UniqueConstraint("evidence_item_id", name="uq_progress_measurement_evidence"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="RESTRICT"), index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="RESTRICT"), index=True
    )
    controlled_object_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("controlled_object.id", ondelete="RESTRICT"), index=True
    )
    evidence_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evidence_item.id", ondelete="RESTRICT"), index=True
    )
    authorized_context_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("authorized_context_version.id", ondelete="RESTRICT")
    )
    measurement_kind: Mapped[str] = mapped_column(String(30), nullable=False)
    measurement_basis: Mapped[str] = mapped_column(String(80), nullable=False)
    numerator: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    denominator: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    completion_ratio: Mapped[Decimal] = mapped_column(Numeric(12, 8), nullable=False)
    unit: Mapped[str] = mapped_column(String(30), nullable=False)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    semantic_state: Mapped[str] = mapped_column(String(30), nullable=False)
    truth_type: Mapped[str] = mapped_column(String(30), nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    recorded_by: Mapped[str] = mapped_column(String(200), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ProgressEvaluation(Base):
    __tablename__ = "progress_evaluation"
    __table_args__ = (
        UniqueConstraint("case_id", "evaluation_number", name="uq_progress_evaluation_number"),
        UniqueConstraint("case_id", "idempotency_key", name="uq_progress_evaluation_idempotency"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="RESTRICT"), index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="RESTRICT"), index=True
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("decision_case.id", ondelete="RESTRICT"), index=True
    )
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("case_snapshot.id", ondelete="RESTRICT"), index=True
    )
    controlled_object_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("controlled_object.id", ondelete="RESTRICT"), index=True
    )
    evaluation_number: Mapped[int] = mapped_column(Integer, nullable=False)
    data_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    planned_measurement_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("progress_measurement.id", ondelete="RESTRICT")
    )
    actual_measurement_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("progress_measurement.id", ondelete="RESTRICT")
    )
    prior_planned_measurement_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("progress_measurement.id", ondelete="RESTRICT")
    )
    prior_actual_measurement_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("progress_measurement.id", ondelete="RESTRICT")
    )
    measurement_basis: Mapped[str] = mapped_column(String(80), nullable=False)
    reconciliation_status: Mapped[str] = mapped_column(String(40), nullable=False)
    reconciled_measurements: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    planned_ratio: Mapped[Decimal] = mapped_column(Numeric(12, 8), nullable=False)
    actual_ratio: Mapped[Decimal] = mapped_column(Numeric(12, 8), nullable=False)
    variance_ratio: Mapped[Decimal] = mapped_column(Numeric(12, 8), nullable=False)
    variance_magnitude: Mapped[Decimal] = mapped_column(Numeric(12, 8), nullable=False)
    direction: Mapped[str] = mapped_column(String(20), nullable=False)
    duration_days: Mapped[int] = mapped_column(Integer, nullable=False)
    threshold_crossed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    persistence: Mapped[str] = mapped_column(String(20), nullable=False)
    trend_direction: Mapped[str] = mapped_column(String(30), nullable=False)
    supporting_observation_count: Mapped[int] = mapped_column(Integer, nullable=False)
    planned_productivity: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    actual_productivity: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    productivity_variance_ratio: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))
    input_evidence_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    input_truth_types: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    truth_type: Mapped[str] = mapped_column(String(30), nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    limitations: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    policy_version: Mapped[str] = mapped_column(String(40), nullable=False)
    formula_version: Mapped[str] = mapped_column(String(40), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    evaluated_by: Mapped[str] = mapped_column(String(200), nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ScheduleAnalysisPolicy(Base):
    __tablename__ = "schedule_analysis_policy"
    __table_args__ = (
        UniqueConstraint("project_id", "policy_version", name="uq_schedule_policy_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="RESTRICT"), index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="RESTRICT"), index=True
    )
    policy_version: Mapped[str] = mapped_column(String(40), nullable=False)
    on_time_tolerance_days: Mapped[Decimal] = mapped_column(Numeric(8, 3), nullable=False)
    maximum_schedule_age_days: Mapped[int] = mapped_column(Integer, nullable=False)
    require_dependency_for_consequence: Mapped[bool] = mapped_column(Boolean, nullable=False)
    allow_calculated_float: Mapped[bool] = mapped_column(Boolean, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    supersedes_policy_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("schedule_analysis_policy.id", ondelete="RESTRICT")
    )
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ScheduleAssessment(Base):
    __tablename__ = "schedule_assessment"
    __table_args__ = (
        UniqueConstraint("case_id", "assessment_number", name="uq_schedule_assessment_number"),
        UniqueConstraint("case_id", "idempotency_key", name="uq_schedule_assessment_idempotency"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="RESTRICT"), index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="RESTRICT"), index=True
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("decision_case.id", ondelete="RESTRICT"), index=True
    )
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("case_snapshot.id", ondelete="RESTRICT"), index=True
    )
    schedule_context_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("authorized_context_version.id", ondelete="RESTRICT"), index=True
    )
    controlled_object_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("controlled_object.id", ondelete="RESTRICT"), index=True
    )
    delay_evidence_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evidence_item.id", ondelete="RESTRICT")
    )
    assessment_number: Mapped[int] = mapped_column(Integer, nullable=False)
    activity_code: Mapped[str] = mapped_column(String(80), nullable=False)
    data_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    planned_start: Mapped[date] = mapped_column(Date, nullable=False)
    planned_finish: Mapped[date] = mapped_column(Date, nullable=False)
    delay_days: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    timing_direction: Mapped[str] = mapped_column(String(20), nullable=False)
    effective_float_days: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    float_source: Mapped[str] = mapped_column(String(20), nullable=False)
    schedule_quality: Mapped[str] = mapped_column(String(40), nullable=False)
    assessment_status: Mapped[str] = mapped_column(String(40), nullable=False)
    exposure_level: Mapped[str] = mapped_column(String(30), nullable=False)
    downstream_paths: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    affected_activity_codes: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    milestone_exposures: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    project_completion_exposure_days: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    maximum_supported_conclusion: Mapped[str] = mapped_column(String(40), nullable=False)
    input_evidence_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    truth_type: Mapped[str] = mapped_column(String(30), nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    limitations: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    policy_version: Mapped[str] = mapped_column(String(40), nullable=False)
    formula_version: Mapped[str] = mapped_column(String(40), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    assessed_by: Mapped[str] = mapped_column(String(200), nullable=False)
    assessed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class CostAnalysisPolicy(Base):
    __tablename__ = "cost_analysis_policy"
    __table_args__ = (
        UniqueConstraint("project_id", "policy_version", name="uq_cost_policy_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="RESTRICT"), index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="RESTRICT"), index=True
    )
    policy_version: Mapped[str] = mapped_column(String(40), nullable=False)
    alignment_tolerance: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    minimum_earned_ratio_for_forecast: Mapped[Decimal] = mapped_column(
        Numeric(8, 6), nullable=False
    )
    include_accruals_in_recognized_cost: Mapped[bool] = mapped_column(Boolean, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    supersedes_policy_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cost_analysis_policy.id", ondelete="RESTRICT")
    )
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CostRecord(Base):
    __tablename__ = "cost_record"
    __table_args__ = (UniqueConstraint("evidence_item_id", name="uq_cost_record_evidence"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="RESTRICT"), index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="RESTRICT"), index=True
    )
    controlled_object_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("controlled_object.id", ondelete="RESTRICT"), index=True
    )
    evidence_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evidence_item.id", ondelete="RESTRICT"), index=True
    )
    authorized_context_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("authorized_context_version.id", ondelete="RESTRICT")
    )
    record_kind: Mapped[str] = mapped_column(String(30), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    measurement_basis: Mapped[str] = mapped_column(String(80), nullable=False)
    reporting_period_start: Mapped[date] = mapped_column(Date, nullable=False)
    reporting_period_end: Mapped[date] = mapped_column(Date, nullable=False)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    commercial_effect: Mapped[str] = mapped_column(String(30), nullable=False)
    effect_explanation: Mapped[str | None] = mapped_column(Text)
    semantic_state: Mapped[str] = mapped_column(String(30), nullable=False)
    truth_type: Mapped[str] = mapped_column(String(30), nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    recorded_by: Mapped[str] = mapped_column(String(200), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class CostAssessment(Base):
    __tablename__ = "cost_assessment"
    __table_args__ = (
        UniqueConstraint("case_id", "assessment_number", name="uq_cost_assessment_number"),
        UniqueConstraint("case_id", "idempotency_key", name="uq_cost_assessment_idempotency"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="RESTRICT"), index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="RESTRICT"), index=True
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("decision_case.id", ondelete="RESTRICT"), index=True
    )
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("case_snapshot.id", ondelete="RESTRICT"), index=True
    )
    budget_context_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("authorized_context_version.id", ondelete="RESTRICT"), index=True
    )
    controlled_object_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("controlled_object.id", ondelete="RESTRICT"), index=True
    )
    assessment_number: Mapped[int] = mapped_column(Integer, nullable=False)
    data_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reporting_period_start: Mapped[date] = mapped_column(Date, nullable=False)
    reporting_period_end: Mapped[date] = mapped_column(Date, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    measurement_basis: Mapped[str] = mapped_column(String(80), nullable=False)
    approved_budget: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    authorized_changes: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    current_authorized_budget: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    commitments: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    actuals: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    accruals: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    recognized_cost: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    earned_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    physical_progress_ratio: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))
    cost_consumption_ratio: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))
    progress_value_ratio: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))
    alignment_variance_ratio: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))
    alignment_status: Mapped[str] = mapped_column(String(30), nullable=False)
    explained_effects: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    unexplained_variance_ratio: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))
    forecast_status: Mapped[str] = mapped_column(String(30), nullable=False)
    forecast_to_complete: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    estimate_at_completion: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    assessment_status: Mapped[str] = mapped_column(String(40), nullable=False)
    maximum_supported_conclusion: Mapped[str] = mapped_column(String(40), nullable=False)
    input_cost_record_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    input_evidence_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    truth_type: Mapped[str] = mapped_column(String(30), nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    limitations: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    policy_version: Mapped[str] = mapped_column(String(40), nullable=False)
    formula_version: Mapped[str] = mapped_column(String(40), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    assessed_by: Mapped[str] = mapped_column(String(200), nullable=False)
    assessed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ForecastPolicy(Base):
    __tablename__ = "forecast_policy"
    __table_args__ = (
        UniqueConstraint("project_id", "policy_version", name="uq_forecast_policy_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="RESTRICT"), index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="RESTRICT"), index=True
    )
    policy_version: Mapped[str] = mapped_column(String(40), nullable=False)
    lower_rate_factor: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    upper_rate_factor: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    lower_cost_factor: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    upper_cost_factor: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    confidence_decay_per_30_days: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    confidence_floor: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    maximum_horizon_days: Mapped[int] = mapped_column(Integer, nullable=False)
    validity_days: Mapped[int] = mapped_column(Integer, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    supersedes_policy_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("forecast_policy.id", ondelete="RESTRICT")
    )
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ForecastProjection(Base):
    __tablename__ = "forecast_projection"
    __table_args__ = (
        UniqueConstraint("case_id", "forecast_number", name="uq_forecast_number"),
        UniqueConstraint("case_id", "idempotency_key", name="uq_forecast_idempotency"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="RESTRICT"), index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="RESTRICT"), index=True
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("decision_case.id", ondelete="RESTRICT"), index=True
    )
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("case_snapshot.id", ondelete="RESTRICT"), index=True
    )
    controlled_object_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("controlled_object.id", ondelete="RESTRICT"), index=True
    )
    progress_evaluation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("progress_evaluation.id", ondelete="RESTRICT")
    )
    schedule_assessment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("schedule_assessment.id", ondelete="RESTRICT")
    )
    cost_assessment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cost_assessment.id", ondelete="RESTRICT")
    )
    active_response_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("case_active_response.id", ondelete="RESTRICT")
    )
    forecast_number: Mapped[int] = mapped_column(Integer, nullable=False)
    target: Mapped[str] = mapped_column(String(40), nullable=False)
    scenario_type: Mapped[str] = mapped_column(String(40), nullable=False)
    method: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    semantic_state: Mapped[str] = mapped_column(String(20), nullable=False)
    truth_type: Mapped[str] = mapped_column(String(30), nullable=False)
    data_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    horizon_end: Mapped[date] = mapped_column(Date, nullable=False)
    horizon_days: Mapped[int] = mapped_column(Integer, nullable=False)
    result_unit: Mapped[str] = mapped_column(String(30), nullable=False)
    result_point: Mapped[str] = mapped_column(String(80), nullable=False)
    result_lower: Mapped[str] = mapped_column(String(80), nullable=False)
    result_upper: Mapped[str] = mapped_column(String(80), nullable=False)
    input_values: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    input_evidence_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    assumptions: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    scenario_parameters: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    limitations: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    upstream_confidence: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    horizon_confidence: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recalculation_triggers: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    policy_version: Mapped[str] = mapped_column(String(40), nullable=False)
    formula_version: Mapped[str] = mapped_column(String(40), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ImpactPriorityPolicy(Base):
    __tablename__ = "impact_priority_policy"
    __table_args__ = (
        UniqueConstraint("project_id", "policy_version", name="uq_impact_policy_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="RESTRICT"), index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="RESTRICT"), index=True
    )
    policy_version: Mapped[str] = mapped_column(String(40), nullable=False)
    medium_cost_exposure_ratio: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    high_cost_exposure_ratio: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    critical_cost_exposure_ratio: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    elevated_margin_days: Mapped[int] = mapped_column(Integer, nullable=False)
    urgent_margin_days: Mapped[int] = mapped_column(Integer, nullable=False)
    active_response_score_reduction: Mapped[Decimal] = mapped_column(Numeric(8, 3), nullable=False)
    cross_cutting_bonus_per_object: Mapped[Decimal] = mapped_column(Numeric(8, 3), nullable=False)
    medium_priority_score: Mapped[Decimal] = mapped_column(Numeric(8, 3), nullable=False)
    high_priority_score: Mapped[Decimal] = mapped_column(Numeric(8, 3), nullable=False)
    critical_priority_score: Mapped[Decimal] = mapped_column(Numeric(8, 3), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    supersedes_policy_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("impact_priority_policy.id", ondelete="RESTRICT")
    )
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ConfidenceOverride(Base):
    __tablename__ = "confidence_override"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="RESTRICT"), index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="RESTRICT"), index=True
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("decision_case.id", ondelete="RESTRICT"), index=True
    )
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("case_snapshot.id", ondelete="RESTRICT"), index=True
    )
    upstream_ceiling: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    approved_confidence: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    justification: Mapped[str] = mapped_column(Text, nullable=False)
    approved_by: Mapped[str] = mapped_column(String(200), nullable=False)
    approved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ImpactAssessment(Base):
    __tablename__ = "impact_assessment"
    __table_args__ = (
        UniqueConstraint("case_id", "assessment_number", name="uq_impact_assessment_number"),
        UniqueConstraint("case_id", "idempotency_key", name="uq_impact_assessment_idempotency"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="RESTRICT"), index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="RESTRICT"), index=True
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("decision_case.id", ondelete="RESTRICT"), index=True
    )
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("case_snapshot.id", ondelete="RESTRICT"), index=True
    )
    controlled_object_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("controlled_object.id", ondelete="RESTRICT"), index=True
    )
    progress_evaluation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("progress_evaluation.id", ondelete="RESTRICT")
    )
    schedule_assessment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("schedule_assessment.id", ondelete="RESTRICT")
    )
    cost_assessment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cost_assessment.id", ondelete="RESTRICT")
    )
    forecast_projection_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    confidence_override_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("confidence_override.id", ondelete="RESTRICT")
    )
    assessment_number: Mapped[int] = mapped_column(Integer, nullable=False)
    consequence_paths: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    consequence_severity: Mapped[str] = mapped_column(String(20), nullable=False)
    decision_clocks: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    response_lead_days: Mapped[int] = mapped_column(Integer, nullable=False)
    urgency_margin_days: Mapped[int | None] = mapped_column(Integer)
    urgency: Mapped[str] = mapped_column(String(20), nullable=False)
    truth_confidence: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    forecast_confidence: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    consequence_confidence: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    upstream_confidence_ceiling: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    overall_confidence: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    cross_cutting_reach: Mapped[int] = mapped_column(Integer, nullable=False)
    active_response_count: Mapped[int] = mapped_column(Integer, nullable=False)
    priority_score: Mapped[Decimal] = mapped_column(Numeric(8, 3), nullable=False)
    priority_band: Mapped[str] = mapped_column(String(20), nullable=False)
    priority_reason_codes: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    assessment_status: Mapped[str] = mapped_column(String(30), nullable=False)
    limitations: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    policy_version: Mapped[str] = mapped_column(String(40), nullable=False)
    formula_version: Mapped[str] = mapped_column(String(40), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    assessed_by: Mapped[str] = mapped_column(String(200), nullable=False)
    assessed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class OrchestrationRun(Base):
    __tablename__ = "orchestration_run"
    __table_args__ = (
        UniqueConstraint("case_id", "run_number", name="uq_orchestration_run_number"),
        UniqueConstraint("case_id", "idempotency_key", name="uq_orchestration_idempotency"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="RESTRICT"), index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="RESTRICT"), index=True
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("decision_case.id", ondelete="RESTRICT"), index=True
    )
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("case_snapshot.id", ondelete="RESTRICT"), index=True
    )
    retry_of_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("orchestration_run.id", ondelete="RESTRICT"), index=True
    )
    run_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    readiness: Mapped[str] = mapped_column(String(50), nullable=False)
    recommended_disposition: Mapped[str | None] = mapped_column(String(20))
    alternative_dispositions: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    blockers: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    limitations: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    contradiction_findings: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    case_brief: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    policy_versions: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False)
    formula_version: Mapped[str] = mapped_column(String(40), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SpecialistRun(Base):
    __tablename__ = "specialist_run"
    __table_args__ = (
        UniqueConstraint(
            "orchestration_run_id", "specialist_kind", name="uq_orchestration_specialist_kind"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="RESTRICT"), index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="RESTRICT"), index=True
    )
    orchestration_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orchestration_run.id", ondelete="RESTRICT"), index=True
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("decision_case.id", ondelete="RESTRICT"), index=True
    )
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("case_snapshot.id", ondelete="RESTRICT"), index=True
    )
    specialist_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False)
    input_references: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    output_references: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    findings: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    calculations: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    evidence_references: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    truth_labels: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    assumptions: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    contradictions: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    limitations: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    requested_evidence: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    contract_version: Mapped[str] = mapped_column(String(40), nullable=False)
    error_class: Mapped[str | None] = mapped_column(String(80))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SpecialistContradictionResolution(Base):
    __tablename__ = "specialist_contradiction_resolution"
    __table_args__ = (
        UniqueConstraint(
            "orchestration_run_id",
            "contradiction_index",
            name="uq_specialist_contradiction_resolution",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="RESTRICT"), index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="RESTRICT"), index=True
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("decision_case.id", ondelete="RESTRICT"), index=True
    )
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("case_snapshot.id", ondelete="RESTRICT"), index=True
    )
    orchestration_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orchestration_run.id", ondelete="RESTRICT"), index=True
    )
    contradiction_index: Mapped[int] = mapped_column(Integer, nullable=False)
    contradiction_type: Mapped[str] = mapped_column(String(40), nullable=False)
    source_result_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    selected_result_id: Mapped[str] = mapped_column(String(80), nullable=False)
    rejected_result_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    resolution_basis: Mapped[str] = mapped_column(Text, nullable=False)
    downstream_invalidations: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    resolved_by: Mapped[str] = mapped_column(String(200), nullable=False)
    resolved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class HumanDecision(Base):
    __tablename__ = "human_decision"
    __table_args__ = (
        UniqueConstraint("case_id", "decision_number", name="uq_human_decision_number"),
        UniqueConstraint("case_id", "idempotency_key", name="uq_human_decision_idempotency"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="RESTRICT"), index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="RESTRICT"), index=True
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("decision_case.id", ondelete="RESTRICT"), index=True
    )
    orchestration_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orchestration_run.id", ondelete="RESTRICT"), index=True
    )
    authority_grant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("authority_grant.id", ondelete="RESTRICT"), index=True
    )
    decision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    disposition: Mapped[str] = mapped_column(String(20), nullable=False)
    recommendation_agreement: Mapped[str] = mapped_column(String(30), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    authority_outcome: Mapped[str] = mapped_column(String(30), nullable=False)
    authority_scope: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    decision_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    currency: Mapped[str | None] = mapped_column(String(3))
    limitations: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    response_authorization_reference: Mapped[str | None] = mapped_column(String(200))
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    decided_by: Mapped[str] = mapped_column(String(200), nullable=False)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ResponseProposal(Base):
    __tablename__ = "response_proposal"
    __table_args__ = (
        UniqueConstraint("case_id", "proposal_number", name="uq_response_proposal_number"),
        UniqueConstraint("case_id", "idempotency_key", name="uq_response_proposal_idempotency"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="RESTRICT"), index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="RESTRICT"), index=True
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("decision_case.id", ondelete="RESTRICT"), index=True
    )
    human_decision_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("human_decision.id", ondelete="RESTRICT"), index=True
    )
    proposal_number: Mapped[int] = mapped_column(Integer, nullable=False)
    response_type: Mapped[str] = mapped_column(String(80), nullable=False)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    actions: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    assumptions: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    simulated_effects: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    requested_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    currency: Mapped[str | None] = mapped_column(String(3))
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    proposed_by: Mapped[str] = mapped_column(String(200), nullable=False)
    proposed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ResponseAuthorization(Base):
    __tablename__ = "response_authorization"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="RESTRICT"), index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="RESTRICT"), index=True
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("decision_case.id", ondelete="RESTRICT"), index=True
    )
    proposal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("response_proposal.id", ondelete="RESTRICT"), unique=True
    )
    human_decision_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("human_decision.id", ondelete="RESTRICT"), index=True
    )
    authority_grant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("authority_grant.id", ondelete="RESTRICT"), index=True
    )
    authorization_reference: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    authority_scope: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    authorized_by: Mapped[str] = mapped_column(String(200), nullable=False)
    authorized_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ResponseExecutionObservation(Base):
    __tablename__ = "response_execution_observation"
    __table_args__ = (
        UniqueConstraint("proposal_id", "sequence_number", name="uq_response_execution_sequence"),
        UniqueConstraint(
            "proposal_id", "idempotency_key", name="uq_response_execution_idempotency"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="RESTRICT"), index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="RESTRICT"), index=True
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("decision_case.id", ondelete="RESTRICT"), index=True
    )
    proposal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("response_proposal.id", ondelete="RESTRICT"), index=True
    )
    authorization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("response_authorization.id", ondelete="RESTRICT"), index=True
    )
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    evidence_item_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    recorded_by: Mapped[str] = mapped_column(String(200), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ResponseOutcome(Base):
    __tablename__ = "response_outcome"
    __table_args__ = (
        UniqueConstraint("proposal_id", "idempotency_key", name="uq_response_outcome_idempotency"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="RESTRICT"), index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="RESTRICT"), index=True
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("decision_case.id", ondelete="RESTRICT"), index=True
    )
    proposal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("response_proposal.id", ondelete="RESTRICT"), index=True
    )
    authorization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("response_authorization.id", ondelete="RESTRICT"), index=True
    )
    classification: Mapped[str] = mapped_column(String(30), nullable=False)
    evidence_item_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    assessed_by: Mapped[str] = mapped_column(String(200), nullable=False)
    assessed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class CaseLearningRecord(Base):
    __tablename__ = "case_learning_record"
    __table_args__ = (
        UniqueConstraint("case_id", "idempotency_key", name="uq_case_learning_idempotency"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="RESTRICT"), index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="RESTRICT"), index=True
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("decision_case.id", ondelete="RESTRICT"), index=True
    )
    response_outcome_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("response_outcome.id", ondelete="RESTRICT"), index=True
    )
    human_decision_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("human_decision.id", ondelete="RESTRICT"), index=True
    )
    orchestration_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orchestration_run.id", ondelete="RESTRICT"), index=True
    )
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    finding: Mapped[str] = mapped_column(Text, nullable=False)
    contributing_factors: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    calibration: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    calibration_notes: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    recorded_by: Mapped[str] = mapped_column(String(200), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
