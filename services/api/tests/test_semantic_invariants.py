import pytest
from app.domain import (
    SemanticViolation,
    assert_analytical_write_allowed,
    assert_human_decision_actor,
    derive_truth_type,
)
from app.generated.taxonomies import AutonomyClass, SemanticState, TruthType


@pytest.mark.parametrize(
    "state",
    [
        SemanticState.BASELINE,
        SemanticState.CURRENT_AUTHORIZED,
        SemanticState.ACTUAL,
        SemanticState.REPORTED,
        SemanticState.VERIFIED,
        SemanticState.SUPERSEDED,
    ],
)
def test_analytical_runtime_cannot_write_governed_or_observed_state(state: SemanticState) -> None:
    with pytest.raises(SemanticViolation):
        assert_analytical_write_allowed(state, AutonomyClass.A2_ADVISORY_AUTONOMY)


@pytest.mark.parametrize(
    "state",
    [SemanticState.FORECAST, SemanticState.SCENARIO, SemanticState.PROPOSED],
)
def test_analytical_runtime_can_write_only_analytical_states(state: SemanticState) -> None:
    assert_analytical_write_allowed(state, AutonomyClass.A1_ANALYTICAL_AUTONOMY)


def test_reported_claim_derivation_does_not_become_fact() -> None:
    assert derive_truth_type(TruthType.REPORTED_CLAIM) == TruthType.DERIVED_METRIC


def test_unknown_and_contradiction_propagate() -> None:
    assert derive_truth_type(TruthType.UNKNOWN) == TruthType.UNKNOWN
    result = derive_truth_type(TruthType.VERIFIED_FACT, TruthType.CONTRADICTED)
    assert result == TruthType.CONTRADICTED


def test_service_cannot_record_human_decision() -> None:
    with pytest.raises(SemanticViolation):
        assert_human_decision_actor(is_human=False, autonomy=AutonomyClass.A2_ADVISORY_AUTONOMY)


def test_authorized_human_can_record_human_decision() -> None:
    assert_human_decision_actor(is_human=True, autonomy=AutonomyClass.A4_HUMAN_RESERVED)
