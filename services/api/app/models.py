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
