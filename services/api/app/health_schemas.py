from datetime import datetime
from decimal import Decimal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


class HealthPolicy(BaseModel):
    """Explicit project policy; no numerical materiality or thresholds are silently invented."""

    model_config = ConfigDict(extra="forbid")
    version: str = Field(min_length=3, max_length=60)
    owner_actor_id: str = Field(min_length=1, max_length=200)
    rationale: str = Field(min_length=10)
    effective_from: AwareDatetime
    progress_yellow_deficit: Decimal = Field(gt=0, le=1)
    progress_red_deficit: Decimal = Field(gt=0, le=1)
    schedule_yellow_days: Decimal = Field(gt=0)
    schedule_red_days: Decimal = Field(gt=0)
    cost_yellow_overrun: Decimal = Field(gt=0)
    cost_red_overrun: Decimal = Field(gt=0)
    evidence_red_below: Decimal = Field(ge=0, le=1)
    evidence_green_at_least: Decimal = Field(gt=0, le=1)
    material_weight_threshold: Decimal = Field(gt=0, le=1)
    maximum_source_age_days: int = Field(ge=0, le=365)

    @model_validator(mode="after")
    def ordered_thresholds(self):
        for yellow, red in (
            (self.progress_yellow_deficit, self.progress_red_deficit),
            (self.schedule_yellow_days, self.schedule_red_days),
            (self.cost_yellow_overrun, self.cost_red_overrun),
        ):
            if yellow >= red:
                raise ValueError("Yellow thresholds must be strictly below Red thresholds")
        if self.evidence_red_below >= self.evidence_green_at_least:
            raise ValueError("Evidence confidence thresholds must be ordered")
        return self


def utc_datetime(value: datetime) -> datetime:
    from datetime import UTC

    return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)
