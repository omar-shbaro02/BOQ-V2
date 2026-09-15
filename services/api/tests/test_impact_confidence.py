from decimal import Decimal
from unittest import TestCase

from app.confidence import impact_confidence


class ImpactConfidenceTests(TestCase):
    def test_forecast_retains_truth_while_horizon_caps_overall(self):
        result = impact_confidence([Decimal("0.9")], [Decimal("0.7")], [])
        self.assertEqual(result.truth, Decimal("0.9"))
        self.assertEqual(result.forecast, Decimal("0.7"))
        self.assertEqual(result.upstream_ceiling, Decimal("0.7"))
        self.assertEqual(result.overall, Decimal("0.63"))

    def test_weakest_source_limits_every_component(self):
        result = impact_confidence([Decimal("0.9")], [Decimal("0.7")], [Decimal("0.4")])
        self.assertEqual(result.truth, Decimal("0.4"))
        self.assertEqual(result.forecast, Decimal("0.4"))
        self.assertEqual(result.consequence, Decimal("0.36"))
        self.assertEqual(result.overall, Decimal("0.36"))

    def test_repeated_inputs_cannot_inflate_confidence(self):
        result = impact_confidence([Decimal("0.9")], [Decimal("0.7")], [])
        repeated = impact_confidence([Decimal("0.9")] * 3, [Decimal("0.7")] * 2, [])
        self.assertEqual(result, repeated)

    def test_missing_truth_or_zero_reliability_fails_closed(self):
        for truth, reliability in (([], []), ([Decimal("0.9")], [Decimal("0")])):
            result = impact_confidence(truth, [Decimal("0.7")], reliability)
            self.assertEqual(result.overall, Decimal("0"))
            self.assertEqual(result.truth, Decimal("0"))

    def test_longer_horizon_cannot_increase_confidence(self):
        near = impact_confidence([Decimal("0.9")], [Decimal("0.8")], [])
        far = impact_confidence([Decimal("0.9")], [Decimal("0.5")], [])
        self.assertEqual(near.truth, far.truth)
        self.assertLess(far.overall, near.overall)

    def test_invalid_confidence_is_rejected(self):
        for value in ("NaN", "Infinity", "-0.1", "1.1"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                impact_confidence([Decimal(value)], [], [])
