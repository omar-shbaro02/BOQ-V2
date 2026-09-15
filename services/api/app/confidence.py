"""Deterministic confidence ceilings, independent of persistence and API adapters."""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class ImpactConfidence:
    truth: Decimal
    forecast: Decimal
    consequence: Decimal
    upstream_ceiling: Decimal
    overall: Decimal


def impact_confidence(
    truth_inputs: Sequence[Decimal],
    forecast_inputs: Sequence[Decimal],
    reliability_inputs: Sequence[Decimal],
) -> ImpactConfidence:
    """Keep truth and horizon confidence distinct; apply weakest-source ceilings."""
    for value in (*truth_inputs, *forecast_inputs, *reliability_inputs):
        if not value.is_finite() or not Decimal("0") <= value <= Decimal("1"):
            raise ValueError("Confidence inputs must be finite values between zero and one")
    truth = min(truth_inputs, default=Decimal("0"))
    truth = min(truth, *reliability_inputs) if reliability_inputs else truth
    forecast = min(truth, *forecast_inputs) if forecast_inputs else truth
    ceiling = min(truth, forecast)
    consequence = (ceiling * Decimal("0.90")).quantize(Decimal("0.000001"))
    return ImpactConfidence(truth, forecast, consequence, ceiling, min(consequence, ceiling))
