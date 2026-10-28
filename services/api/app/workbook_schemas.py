import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator


class WorkbookMapping(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task_id: int = Field(ge=1)
    activity_code: str = Field(min_length=1, max_length=80)
    controlled_object_id: uuid.UUID


class ProgressWorkbookCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    artifact_id: uuid.UUID
    schedule_context_id: uuid.UUID
    data_date: AwareDatetime
    reported_confidence: Decimal = Field(ge=0, le=1)
    mappings: list[WorkbookMapping] = Field(min_length=1, max_length=10000)

    @model_validator(mode="after")
    def unique_mappings(self):
        if len({item.task_id for item in self.mappings}) != len(self.mappings):
            raise ValueError("Workbook task mappings must be unique")
        if len({item.activity_code for item in self.mappings}) != len(self.mappings):
            raise ValueError("Schedule activities must not be double counted")
        return self


class ProgressWorkbookRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID
    artifact_id: uuid.UUID
    schedule_context_id: uuid.UUID
    data_date: datetime
    rows: list[dict[str, Any]]
    network_basis: dict[str, Any]
    limitations: list[dict[str, Any]]
    formula_version: str
    idempotency_key: str
    request_hash: str
    recorded_by: str
    recorded_at: datetime

    @field_validator("data_date", "recorded_at")
    @classmethod
    def utc_dates(cls, value: datetime) -> datetime:
        return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)
