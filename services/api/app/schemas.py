from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

from app.generated.taxonomies import (
    AuthorizedContextType,
    ControlledObjectRelationType,
    ControlledObjectType,
    ProgressBasis,
    ProjectRole,
    ProjectStatus,
    SemanticState,
)


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class OrganizationCreate(ApiModel):
    name: str = Field(min_length=2, max_length=200)
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=80)


class OrganizationRead(OrganizationCreate):
    id: uuid.UUID
    created_at: datetime


class ProjectCalendar(ApiModel):
    working_weekdays: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4])
    hours_per_day: Decimal = Field(default=Decimal("8"), gt=0, le=24)
    holidays: list[date] = Field(default_factory=list)

    @field_validator("working_weekdays")
    @classmethod
    def valid_weekdays(cls, value: list[int]) -> list[int]:
        if not value or any(day < 0 or day > 6 for day in value):
            raise ValueError("working_weekdays must contain values from 0 through 6")
        if len(value) != len(set(value)):
            raise ValueError("working_weekdays must be unique")
        return value


class ProjectCreate(ApiModel):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=2, max_length=200)
    timezone: str
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    delivery_model: str = Field(min_length=2, max_length=80)
    reporting_cadence: str = Field(min_length=2, max_length=40)
    calendar_config: ProjectCalendar = Field(default_factory=ProjectCalendar)

    @field_validator("timezone")
    @classmethod
    def timezone_exists(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("Unknown IANA timezone") from exc
        return value


class ProjectRead(ProjectCreate):
    id: uuid.UUID
    organization_id: uuid.UUID
    status: ProjectStatus
    created_at: datetime


class MembershipCreate(ApiModel):
    actor_id: str = Field(min_length=1, max_length=200)
    role: ProjectRole


class MembershipRead(MembershipCreate):
    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID | None
    active: bool


class ControlledObjectCreate(ApiModel):
    object_type: ControlledObjectType
    code: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=2, max_length=240)
    owner_actor_id: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class ControlledObjectRead(ControlledObjectCreate):
    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID
    active: bool


class RelationCreate(ApiModel):
    source_id: uuid.UUID
    target_id: uuid.UUID
    relation_type: ControlledObjectRelationType


class RelationRead(RelationCreate):
    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID


class AuthorityGrantCreate(ApiModel):
    actor_id: str
    authority_type: str = Field(min_length=2, max_length=80)
    controlled_object_id: uuid.UUID | None = None
    max_amount: Decimal | None = None
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    valid_from: date | None = None
    valid_until: date | None = None
    escalation_level: int = Field(default=0, ge=0)
    escalates_to_actor_id: str | None = Field(default=None, max_length=200)

    @field_validator("valid_until")
    @classmethod
    def valid_range(cls, value: date | None, info: Any) -> date | None:
        start = info.data.get("valid_from")
        if value and start and value < start:
            raise ValueError("valid_until must not precede valid_from")
        return value

    @model_validator(mode="after")
    def valid_authority_chain(self) -> AuthorityGrantCreate:
        if self.max_amount is not None and self.currency is None:
            raise ValueError("currency is required when max_amount is set")
        if self.escalates_to_actor_id == self.actor_id:
            raise ValueError("authority cannot escalate to the same actor")
        return self


class AuthorityGrantRead(AuthorityGrantCreate):
    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID
    active: bool


class PlannedProgressPoint(ApiModel):
    as_of: date
    numerator: Decimal = Field(ge=0)
    denominator: Decimal = Field(gt=0)
    unit: str = Field(min_length=1, max_length=30)
    measurement_basis: ProgressBasis

    @model_validator(mode="after")
    def within_denominator(self) -> PlannedProgressPoint:
        if self.numerator > self.denominator:
            raise ValueError("Planned progress cannot exceed its denominator")
        return self


class ScheduleActivity(ApiModel):
    code: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=2, max_length=240)
    planned_start: date
    planned_finish: date
    progress_basis: str = Field(min_length=2, max_length=80)
    responsible_owner: str = Field(min_length=1, max_length=200)
    controlled_object_code: str | None = Field(default=None, min_length=1, max_length=80)
    progress_plan: list[PlannedProgressPoint] = Field(default_factory=list)

    @model_validator(mode="after")
    def valid_dates(self) -> ScheduleActivity:
        if self.planned_finish < self.planned_start:
            raise ValueError("planned_finish must not precede planned_start")
        dates = [point.as_of for point in self.progress_plan]
        if dates != sorted(dates) or len(dates) != len(set(dates)):
            raise ValueError("Planned progress points must have unique ascending dates")
        return self


class ScheduleDependency(ApiModel):
    predecessor_code: str
    successor_code: str
    relation_type: str = Field(default="FINISH_TO_START", pattern=r"^[A-Z_]+$")
    lag_days: Decimal = Decimal("0")


class ScheduleMilestone(ApiModel):
    code: str
    name: str
    planned_date: date


class SchedulePayload(ApiModel):
    data_date: date
    activities: list[ScheduleActivity] = Field(min_length=1)
    dependencies: list[ScheduleDependency] = Field(default_factory=list)
    milestones: list[ScheduleMilestone] = Field(default_factory=list)

    @model_validator(mode="after")
    def valid_references(self) -> SchedulePayload:
        codes = [activity.code for activity in self.activities]
        if len(codes) != len(set(codes)):
            raise ValueError("Schedule activity codes must be unique")
        known = set(codes)
        for dependency in self.dependencies:
            if dependency.predecessor_code not in known or dependency.successor_code not in known:
                raise ValueError("Schedule dependency must reference known activity codes")
            if dependency.predecessor_code == dependency.successor_code:
                raise ValueError("Schedule activity cannot depend on itself")
        return self


class BudgetPayload(ApiModel):
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    approved_budget: Decimal = Field(ge=0)
    authorized_changes: Decimal = Decimal("0")


class BoqItem(ApiModel):
    code: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=500)
    quantity: Decimal = Field(ge=0)
    unit: str = Field(min_length=1, max_length=30)
    rate: Decimal = Field(ge=0)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    controlled_object_code: str | None = None


class BoqPayload(ApiModel):
    items: list[BoqItem] = Field(min_length=1)


class ContextVersionBase(ApiModel):
    context_type: AuthorizedContextType
    semantic_state: SemanticState
    effective_from: datetime
    payload: dict[str, Any]


class ContextVersionCreate(ContextVersionBase):
    effective_from: AwareDatetime

    @field_validator("semantic_state")
    @classmethod
    def source_state_only(cls, value: SemanticState) -> SemanticState:
        if value not in {SemanticState.BASELINE, SemanticState.PROPOSED}:
            raise ValueError("Context sources must be BASELINE or PROPOSED")
        return value

    @model_validator(mode="after")
    def validate_typed_payload(self) -> ContextVersionCreate:
        payload_models = {
            AuthorizedContextType.SCHEDULE: SchedulePayload,
            AuthorizedContextType.BUDGET: BudgetPayload,
            AuthorizedContextType.BOQ: BoqPayload,
        }
        validated = payload_models[self.context_type].model_validate(self.payload)
        self.payload = validated.model_dump(mode="json")
        return self


class ContextVersionRead(ContextVersionBase):
    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID
    version_number: int
    created_by: str
    source_version_id: uuid.UUID | None
    approval_reference: str | None
    activation_reason: str | None
    activated_by: str | None
    activated_at: datetime | None
    superseded_at: datetime | None


class ContextActivation(ApiModel):
    source_version_id: uuid.UUID
    approval_reference: str = Field(min_length=3)
    reason: str = Field(min_length=3)


class AuditEventRead(ApiModel):
    event_id: uuid.UUID
    organization_id: uuid.UUID | None
    project_id: uuid.UUID | None
    occurred_at: datetime
    actor_id: str
    actor_type: str
    action: str
    object_type: str
    object_id: str
    object_version: int | None
    authority_result: str
    details: dict[str, Any]
