from __future__ import annotations

from dataclasses import dataclass

from app.generated.taxonomies import AutonomyClass, SemanticState, TruthType


class SemanticViolation(ValueError):
    """Raised when an operation would strengthen or corrupt governed meaning."""


@dataclass(frozen=True, slots=True)
class AssertionSemantics:
    state: SemanticState
    truth_type: TruthType


ANALYTICAL_WRITE_STATES = frozenset(
    {SemanticState.FORECAST, SemanticState.SCENARIO, SemanticState.PROPOSED}
)


def assert_analytical_write_allowed(state: SemanticState, autonomy: AutonomyClass) -> None:
    if autonomy not in {
        AutonomyClass.A1_ANALYTICAL_AUTONOMY,
        AutonomyClass.A2_ADVISORY_AUTONOMY,
    }:
        raise SemanticViolation("Analytical writes require A1 or A2 autonomy")
    if state not in ANALYTICAL_WRITE_STATES:
        raise SemanticViolation(f"Analytical runtime cannot write {state}")


def derive_truth_type(*inputs: TruthType) -> TruthType:
    """A calculation remains derived and never upgrades its inputs to fact."""
    if not inputs:
        raise SemanticViolation("A derived metric requires at least one input")
    if TruthType.CONTRADICTED in inputs:
        return TruthType.CONTRADICTED
    if TruthType.UNKNOWN in inputs:
        return TruthType.UNKNOWN
    return TruthType.DERIVED_METRIC


def assert_human_decision_actor(*, is_human: bool, autonomy: AutonomyClass) -> None:
    if not is_human or autonomy != AutonomyClass.A4_HUMAN_RESERVED:
        raise SemanticViolation("Only an explicitly authorized human may record a human decision")
