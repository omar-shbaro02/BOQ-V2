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
    ScheduleConstraintType,
    ScheduleDependencyType,
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


class ScheduleCalendar(ApiModel):
    calendar_id: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=160)
    working_weekdays: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4])
    holidays: list[date] = Field(default_factory=list)

    @model_validator(mode="after")
    def valid_calendar(self) -> ScheduleCalendar:
        if not self.working_weekdays or any(
            value < 0 or value > 6 for value in self.working_weekdays
        ):
            raise ValueError("Schedule calendar weekdays must be unique values from 0 to 6")
        if len(self.working_weekdays) != len(set(self.working_weekdays)):
            raise ValueError("Schedule calendar weekdays must be unique values from 0 to 6")
        if len(self.holidays) != len(set(self.holidays)):
            raise ValueError("Schedule calendar holidays must be unique")
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
    calendar_id: str = Field(default="PROJECT", min_length=1, max_length=80)
    total_float_days: Decimal | None = Field(default=None, ge=0)

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
    relation_type: ScheduleDependencyType = ScheduleDependencyType.FINISH_TO_START
    lag_days: Decimal = Decimal("0")


class ScheduleConstraint(ApiModel):
    activity_code: str = Field(min_length=1, max_length=80)
    constraint_type: ScheduleConstraintType
    constraint_date: date


class ScheduleMilestone(ApiModel):
    code: str
    name: str
    planned_date: date
    activity_code: str | None = None
    controlled_object_code: str | None = None
    material: bool = True


class SchedulePayload(ApiModel):
    data_date: date
    network_complete: bool = False
    activities: list[ScheduleActivity] = Field(min_length=1)
    calendars: list[ScheduleCalendar] = Field(default_factory=list)
    dependencies: list[ScheduleDependency] = Field(default_factory=list)
    constraints: list[ScheduleConstraint] = Field(default_factory=list)
    milestones: list[ScheduleMilestone] = Field(default_factory=list)

    @model_validator(mode="after")
    def valid_references(self) -> SchedulePayload:
        codes = [activity.code for activity in self.activities]
        if len(codes) != len(set(codes)):
            raise ValueError("Schedule activity codes must be unique")
        known = set(codes)
        calendar_ids = [calendar.calendar_id for calendar in self.calendars]
        if len(calendar_ids) != len(set(calendar_ids)):
            raise ValueError("Schedule calendar IDs must be unique")
        known_calendars = {"PROJECT", *calendar_ids}
        if any(activity.calendar_id not in known_calendars for activity in self.activities):
            raise ValueError("Schedule activity references an unknown calendar")
        for dependency in self.dependencies:
            if dependency.predecessor_code not in known or dependency.successor_code not in known:
                raise ValueError("Schedule dependency must reference known activity codes")
            if dependency.predecessor_code == dependency.successor_code:
                raise ValueError("Schedule activity cannot depend on itself")
        adjacency = {code: [] for code in codes}
        for dependency in self.dependencies:
            adjacency[dependency.predecessor_code].append(dependency.successor_code)
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(code: str) -> None:
            if code in visiting:
                raise ValueError("Schedule dependency network must be acyclic")
            if code in visited:
                return
            visiting.add(code)
            for successor in adjacency[code]:
                visit(successor)
            visiting.remove(code)
            visited.add(code)

        for code in codes:
            visit(code)
        if any(constraint.activity_code not in known for constraint in self.constraints):
            raise ValueError("Schedule constraint references an unknown activity")
        by_code = {activity.code: activity for activity in self.activities}
        for constraint in self.constraints:
            activity = by_code[constraint.activity_code]
            invalid = (
                (
                    constraint.constraint_type == ScheduleConstraintType.START_NO_EARLIER_THAN
                    and activity.planned_start < constraint.constraint_date
                )
                or (
                    constraint.constraint_type == ScheduleConstraintType.FINISH_NO_LATER_THAN
                    and activity.planned_finish > constraint.constraint_date
                )
                or (
                    constraint.constraint_type == ScheduleConstraintType.MUST_START_ON
                    and activity.planned_start != constraint.constraint_date
                )
                or (
                    constraint.constraint_type == ScheduleConstraintType.MUST_FINISH_ON
                    and activity.planned_finish != constraint.constraint_date
                )
            )
            if invalid:
                raise ValueError("Schedule activity dates violate a declared constraint")
        milestone_codes = [milestone.code for milestone in self.milestones]
        if len(milestone_codes) != len(set(milestone_codes)):
            raise ValueError("Schedule milestone codes must be unique")
        if any(
            milestone.activity_code is not None and milestone.activity_code not in known
            for milestone in self.milestones
        ):
            raise ValueError("Schedule milestone references an unknown activity")
        return self


class BudgetPayload(ApiModel):
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    approved_budget: Decimal = Field(ge=0)
    authorized_changes: Decimal = Decimal("0")
    data_date: date | None = None
    reporting_period_start: date | None = None
    reporting_period_end: date | None = None
    controlled_object_code: str | None = Field(default=None, min_length=1, max_length=80)
    measurement_basis: str = Field(default="COST_VALUE", min_length=1, max_length=80)

    @model_validator(mode="after")
    def valid_reporting_period(self) -> BudgetPayload:
        if (self.reporting_period_start is None) != (self.reporting_period_end is None):
            raise ValueError("Budget reporting period requires both start and end")
        if (
            self.reporting_period_start is not None
            and self.reporting_period_end < self.reporting_period_start
        ):
            raise ValueError("Budget reporting period end must not precede start")
        return self


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
