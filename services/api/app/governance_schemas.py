from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.case_schemas import DecisionCaseRead
from app.generated.taxonomies import (
    AuthorityValidationOutcome,
    Disposition,
    HumanDecisionAgreement,
    LearningCategory,
    OutcomeClassification,
    ResponseExecutionStatus,
)


class GovernanceApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class HumanDecisionCreate(GovernanceApiModel):
    expected_version: int = Field(ge=1)
    orchestration_run_id: uuid.UUID
    authority_grant_id: uuid.UUID
    disposition: Disposition
    recommendation_agreement: HumanDecisionAgreement
    rationale: str = Field(min_length=20)
    decision_amount: Decimal | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    limitations: list[dict[str, Any]] = Field(default_factory=list)
    response_authorization_reference: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def consistent_amount(self) -> HumanDecisionCreate:
        if (self.decision_amount is None) != (self.currency is None):
            raise ValueError("decision_amount and currency must be supplied together")
        return self


class HumanDecisionRead(GovernanceApiModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID
    case_id: uuid.UUID
    orchestration_run_id: uuid.UUID
    authority_grant_id: uuid.UUID
    decision_number: int
    disposition: Disposition
    recommendation_agreement: HumanDecisionAgreement
    rationale: str
    authority_outcome: AuthorityValidationOutcome
    authority_scope: dict[str, Any]
    decision_amount: Decimal | None
    currency: str | None
    limitations: list[dict[str, Any]]
    response_authorization_reference: str | None
    idempotency_key: str
    request_hash: str
    decided_by: str
    decided_at: datetime


class HumanDecisionResult(GovernanceApiModel):
    case: DecisionCaseRead
    decision: HumanDecisionRead


class ResponseProposalCreate(GovernanceApiModel):
    expected_version: int = Field(ge=1)
    human_decision_id: uuid.UUID
    response_type: str = Field(min_length=2, max_length=80)
    objective: str = Field(min_length=20)
    actions: list[dict[str, Any]] = Field(min_length=1)
    assumptions: list[str] = Field(default_factory=list)
    simulated_effects: dict[str, Any]
    requested_amount: Decimal | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")

    @model_validator(mode="after")
    def consistent_amount(self) -> ResponseProposalCreate:
        if (self.requested_amount is None) != (self.currency is None):
            raise ValueError("requested_amount and currency must be supplied together")
        return self


class ResponseProposalRead(GovernanceApiModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID
    case_id: uuid.UUID
    human_decision_id: uuid.UUID
    proposal_number: int
    response_type: str
    objective: str
    actions: list[dict[str, Any]]
    assumptions: list[str]
    simulated_effects: dict[str, Any]
    requested_amount: Decimal | None
    currency: str | None
    idempotency_key: str
    request_hash: str
    proposed_by: str
    proposed_at: datetime


class ResponseAuthorizationCreate(GovernanceApiModel):
    expected_version: int = Field(ge=1)
    authority_grant_id: uuid.UUID
    authorization_reference: str = Field(min_length=2, max_length=200)


class ResponseAuthorizationRead(GovernanceApiModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID
    case_id: uuid.UUID
    proposal_id: uuid.UUID
    human_decision_id: uuid.UUID
    authority_grant_id: uuid.UUID
    authorization_reference: str
    authority_scope: dict[str, Any]
    authorized_by: str
    authorized_at: datetime


class ResponseExecutionCreate(GovernanceApiModel):
    expected_version: int = Field(ge=1)
    status: ResponseExecutionStatus
    observed_at: datetime
    details: dict[str, Any] = Field(default_factory=dict)
    evidence_item_ids: list[uuid.UUID] = Field(default_factory=list)


class ResponseExecutionRead(GovernanceApiModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID
    case_id: uuid.UUID
    proposal_id: uuid.UUID
    authorization_id: uuid.UUID
    sequence_number: int
    status: ResponseExecutionStatus
    observed_at: datetime
    details: dict[str, Any]
    evidence_item_ids: list[str]
    idempotency_key: str
    request_hash: str
    recorded_by: str
    recorded_at: datetime


class ResponseOutcomeCreate(GovernanceApiModel):
    expected_version: int = Field(ge=1)
    classification: OutcomeClassification
    evidence_item_ids: list[uuid.UUID] = Field(default_factory=list)
    rationale: str = Field(min_length=20)


class ResponseOutcomeRead(GovernanceApiModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID
    case_id: uuid.UUID
    proposal_id: uuid.UUID
    authorization_id: uuid.UUID
    classification: OutcomeClassification
    evidence_item_ids: list[str]
    rationale: str
    idempotency_key: str
    request_hash: str
    assessed_by: str
    assessed_at: datetime


class LearningRecordCreate(GovernanceApiModel):
    expected_version: int = Field(ge=1)
    response_outcome_id: uuid.UUID
    category: LearningCategory
    finding: str = Field(min_length=20)
    contributing_factors: list[str] = Field(default_factory=list)
    calibration_notes: str = Field(min_length=20)


class LearningRecordRead(GovernanceApiModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID
    case_id: uuid.UUID
    response_outcome_id: uuid.UUID
    human_decision_id: uuid.UUID
    orchestration_run_id: uuid.UUID
    category: LearningCategory
    finding: str
    contributing_factors: list[str]
    calibration: dict[str, Any]
    calibration_notes: str
    idempotency_key: str
    request_hash: str
    recorded_by: str
    recorded_at: datetime
