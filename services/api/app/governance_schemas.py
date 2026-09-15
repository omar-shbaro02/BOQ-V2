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
