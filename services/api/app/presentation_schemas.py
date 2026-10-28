import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PresentationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    report_snapshot_id: uuid.UUID
    recipient_record_ids: list[uuid.UUID] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def unique_recipients(self):
        if len(set(self.recipient_record_ids)) != len(self.recipient_record_ids):
            raise ValueError("Recipient records must be unique")
        return self


class PresentationTransition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    to_status: Literal["REVIEWED", "APPROVED"]
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=3)
    authority_grant_id: uuid.UUID | None = None


class PresentationEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    presentation_id: uuid.UUID
    event_number: int
    from_status: str | None
    to_status: str
    reason: str
    authority_grant_id: uuid.UUID | None
    actor_id: str
    occurred_at: datetime


class PresentationRead(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    report_snapshot_id: uuid.UUID
    source_report_approval_event_id: uuid.UUID
    source_report_hash: str
    content_hash: str
    generator_version: str
    recipients: list[dict[str, Any]]
    fidelity_manifest: dict[str, Any]
    generated_by: str
    generated_at: datetime
    lifecycle_status: str
    lifecycle_events: list[PresentationEventRead]
