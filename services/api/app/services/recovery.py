"""Qualify projected recovery benefits without presuming execution or success."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any


def utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def comparable_forecast(forecast: Any) -> bool:
    # The explicit linear-method caveat qualifies the result; it is not a stop gate.
    return forecast.status == "CALCULATED" and all(
        item.get("code") == "LINEAR_RATE_ASSUMPTION" for item in forecast.limitations
    )


def qualify_recovery(
    response: Any,
    forecasts: list[Any],
    validities: dict[str, str],
    data_date: datetime,
    assessed_at: datetime,
) -> dict[str, Any]:
    reasons: list[str] = []
    if response.status != "ACTIVE":
        reasons.append("RESPONSE_NOT_ACTIVE")
    if any(
        point < utc(response.effective_from)
        or (response.effective_until is not None and point > utc(response.effective_until))
        for point in (utc(data_date), utc(assessed_at))
    ):
        reasons.append("RESPONSE_OUTSIDE_EFFECTIVE_WINDOW")
    candidates = [item for item in forecasts if item.active_response_id == response.id]
    comparisons = []
    if not candidates:
        reasons.append("RECOVERY_FORECAST_MISSING")
    dimensions = (
        "target",
        "method",
        "policy_version",
        "horizon_end",
        "data_date",
        "result_unit",
        "progress_evaluation_id",
        "schedule_assessment_id",
        "cost_assessment_id",
    )
    for candidate in candidates:
        if validities[str(candidate.id)] != "CURRENT":
            reasons.append("RECOVERY_FORECAST_NOT_CURRENT")
            continue
        if (
            not comparable_forecast(candidate)
            or candidate.scenario_type != "ACTIVE_RESPONSE"
            or candidate.semantic_state != "FORECAST"
        ):
            reasons.append("RECOVERY_FORECAST_LIMITED")
            continue
        baselines = [
            item
            for item in forecasts
            if item.scenario_type == "CONTINUED_PERFORMANCE"
            and item.semantic_state == "FORECAST"
            and validities[str(item.id)] == "CURRENT"
            and comparable_forecast(item)
            and all(getattr(item, key) == getattr(candidate, key) for key in dimensions)
        ]
        if not baselines:
            reasons.append("RECOVERY_COMPARISON_MISSING")
        for baseline in baselines:
            # All supported targets improve downward: earlier completion or lower EAC.
            improved = (
                candidate.result_point < baseline.result_point
                if candidate.result_unit == "DATE"
                else Decimal(candidate.result_point) < Decimal(baseline.result_point)
            )
            comparisons.append(
                {
                    "response_forecast_id": str(candidate.id),
                    "continued_forecast_id": str(baseline.id),
                    "target": candidate.target,
                    "continued_point": baseline.result_point,
                    "response_point": candidate.result_point,
                    "result_unit": candidate.result_unit,
                    "projected_improvement": improved,
                    "assumptions": list(candidate.assumptions),
                    "limitations": list(candidate.limitations),
                }
            )
            if not improved:
                reasons.append("NO_PROJECTED_IMPROVEMENT")
    qualified = not reasons and bool(comparisons)
    return {
        "qualified": qualified,
        "reason_codes": sorted(set(reasons)) or ["PROJECTED_RECOVERY_BENEFIT"],
        "comparisons": comparisons,
        "assessed_at": assessed_at.isoformat(),
        "conclusion_boundary": (
            "Projected benefit under assumptions; execution and success are unproven"
        ),
    }
