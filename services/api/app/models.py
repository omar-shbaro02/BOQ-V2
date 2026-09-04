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
