"""Shared factual projection for dashboard, reports, assistant, and derived presentations."""

from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal

VERSION = "CONTROL-METRICS-1.0.0"


def shared_metrics(control) -> dict:
    def value(name, default=None):
        return (
            control.get(name, default)
            if isinstance(control, dict)
            else getattr(control, name, default)
        )

    def ratio_metric(name):
        raw = value(name)
        if raw is None:
            return {"ratio": None, "percent": None, "display": "Unknown"}
        number = Decimal(str(raw))
        percent = number * 100
        return {
            "ratio": format(number, ".8f"),
            "percent": format(percent, ".8f"),
            "display": f"{percent.quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)}%",
        }

    data_date = value("data_date")
    if isinstance(data_date, str):
        data_date = datetime.fromisoformat(data_date)
    if data_date is not None:
        data_date = data_date.astimezone(UTC) if data_date.tzinfo else data_date.replace(tzinfo=UTC)
    costs = []
    for item in value("cost_assessment_refs", []):
        costs.append(
            {
                "assessment_id": item["id"],
                "controlled_object_id": item["controlled_object_id"],
                "currency": item["currency"],
                "data_date": item["data_date"],
                "assessment_status": item["assessment_status"],
                "values": {
                    name: item[name] if item["assessment_status"] == "ASSESSED" else None
                    for name in (
                        "current_authorized_budget",
                        "commitments",
                        "actuals",
                        "accruals",
                        "forecast_to_complete",
                        "estimate_at_completion",
                    )
                },
                "limitations": item["limitations"],
            }
        )
    return {
        "projection_version": VERSION,
        "snapshot_id": str(value("id")),
        "data_date": data_date.isoformat() if data_date else None,
        "planned": ratio_metric("planned_ratio"),
        "actual": ratio_metric("actual_ratio"),
        "variance": ratio_metric("variance_ratio"),
        "progress_status": value("progress_status"),
        "confidence": format(Decimal(str(value("confidence"))), ".4f")
        if value("confidence") is not None
        else None,
        "rag_status": (value("health", {}) or {}).get("status", "UNKNOWN"),
        "cost_assessments": costs,
        "forecast_projections": value("forecast_projection_refs", []),
        "limitations": value("limitations", []),
    }
