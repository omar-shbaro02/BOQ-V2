from copy import deepcopy
from decimal import Decimal

import pytest
from app.health_schemas import HealthPolicy
from app.services.project_health import compute_health
from pydantic import ValidationError

POLICY = {
    "version": "PILOT-RAG-1",
    "owner_actor_id": "pm@test",
    "rationale": "Explicit synthetic test materiality; no production default implied.",
    "effective_from": "2026-01-01T00:00:00Z",
    "progress_yellow_deficit": "0.02",
    "progress_red_deficit": "0.05",
    "schedule_yellow_days": "2",
    "schedule_red_days": "5",
    "cost_yellow_overrun": "0.03",
    "cost_red_overrun": "0.10",
    "evidence_red_below": "0.5",
    "evidence_green_at_least": "0.8",
    "material_weight_threshold": "0.2",
    "maximum_source_age_days": 14,
}


def package(code="WP-1", weight="1", planned="0.5", actual="0.5", confidence="0.9"):
    return {
        "controlled_object_id": code,
        "controlled_object_code": code,
        "weight": weight,
        "planned_ratio": planned,
        "actual_ratio": actual,
        "actual_confidence": confidence,
        "planned_measurement_id": f"plan-{code}",
        "actual_measurement_id": f"actual-{code}",
    }


def source_context(code="WP-1", exposure="0", governance="ANALYSIS_AUTHORIZED"):
    return {
        "schedule_assessments": [
            {
                "id": "schedule-1",
                "case_id": "case-1",
                "controlled_object_id": code,
                "assessment_status": "ASSESSED",
                "schedule_quality": "VALID",
                "stale": False,
                "project_completion_exposure_days": exposure,
                "input_evidence_ids": ["delay-1"],
                "confidence": "0.9",
                "limitations": [],
            }
        ],
        "governance": [
            {
                "case_id": "case-1",
                "controlled_object_ids": [code],
                "governance_state": governance,
                "audit_event_id": "audit-1",
                "contradiction_ids": [],
            }
        ],
    }


def cost(code="WP-1", eac="100"):
    return {
        "id": "cost-1",
        "case_id": "case-1",
        "controlled_object_id": code,
        "current_authorized_budget": "100",
        "estimate_at_completion": eac,
        "assessment_status": "ASSESSED",
        "confidence": "0.9",
        "limitations": [],
    }


def assess(packages=None, costs=None, support=None, policy=POLICY):
    return compute_health(
        packages or [package()],
        costs if costs is not None else [cost()],
        support if support is not None else source_context(),
        HealthPolicy.model_validate(policy) if policy else None,
        "2026-10-01T00:00:00Z",
    )


def test_complete_supported_basis_is_green_with_full_rule_lineage():
    result = assess()
    assert result["status"] == "GREEN"
    assert result["policy"] == HealthPolicy.model_validate(POLICY).model_dump(mode="json")
    for dimension in result["packages"][0]["dimensions"].values():
        assert dimension["status"] == "GREEN"
        assert dimension["rule"] and dimension["input_refs"] and dimension["data_date"]
    assert "not a human decision" in result["semantic_notice"]


@pytest.mark.parametrize(
    "actual,status", [("0.49", "GREEN"), ("0.48", "YELLOW"), ("0.45", "RED"), ("0", "RED")]
)
def test_progress_boundary_arithmetic_and_zero(actual, status):
    result = assess(packages=[package(actual=actual)])
    dimension = result["packages"][0]["dimensions"]["progress"]
    assert dimension["status"] == status
    assert Decimal(dimension["value"]) == Decimal("0.5") - Decimal(actual)
    if status != "GREEN":
        assert dimension["review_route"]["url"] == "/signals"


@pytest.mark.parametrize("exposure,status", [("0", "GREEN"), ("2", "YELLOW"), ("5", "RED")])
def test_schedule_uses_supported_network_exposure(exposure, status):
    dimension = assess(support=source_context(exposure=exposure))["packages"][0]["dimensions"][
        "schedule"
    ]
    assert dimension["status"] == status
    assert "schedule-1" in dimension["input_refs"]
    if status != "GREEN":
        assert dimension["review_route"]["case_id"] == "case-1"


@pytest.mark.parametrize(
    "eac,status", [("100", "GREEN"), ("103", "YELLOW"), ("110", "RED"), (None, "UNKNOWN")]
)
def test_cost_uses_eac_and_keeps_unknown_distinct(eac, status):
    assert assess(costs=[cost(eac=eac)])["packages"][0]["dimensions"]["cost"]["status"] == status


def test_unknown_inputs_and_missing_policy_never_green():
    result = assess(costs=[], support={})
    assert result["status"] == "UNKNOWN"
    assert result["dimensions"]["cost"]["unknown_weight"] == "1"
    assert assess(policy=None)["status"] == "UNKNOWN"


def test_weighted_red_materiality_does_not_disappear_in_averages():
    small = package("SMALL", "0.1", actual="0.1")
    large = package("LARGE", "0.9")
    result = assess(packages=[small, large], costs=[], support={})
    assert result["packages"][0]["dimensions"]["progress"]["status"] == "RED"
    assert result["dimensions"]["progress"]["status"] == "YELLOW"
    assert result["dimensions"]["progress"]["review_route"]["controlled_object_ids"] == ["SMALL"]
    small["weight"], large["weight"] = "0.2", "0.8"
    assert assess(packages=[small, large])["dimensions"]["progress"]["status"] == "RED"


def test_contradictions_restrict_progress_without_deleting_comparison():
    source = source_context()
    source["governance"][0]["contradiction_ids"] = ["contradiction-1"]
    result = assess(support=source)
    dimensions = result["packages"][0]["dimensions"]
    assert dimensions["evidence"]["status"] == "RED"
    assert dimensions["progress"]["status"] == "UNKNOWN"
    assert dimensions["progress"]["value"] == "0.0"
    assert "contradiction-1" in dimensions["progress"]["input_refs"]


def test_stale_and_restricted_schedule_never_strengthened():
    source = source_context()
    source["schedule_assessments"][0]["stale"] = True
    assert assess(support=source)["packages"][0]["dimensions"]["schedule"]["status"] == "UNKNOWN"
    source["schedule_assessments"][0]["stale"] = False
    source["schedule_assessments"][0]["assessment_status"] = "VERIFICATION_REQUIRED"
    assert assess(support=source)["packages"][0]["dimensions"]["schedule"]["status"] == "UNKNOWN"


def test_governance_gate_and_frozen_inputs_remain_independent():
    source = source_context(governance="GOVERNANCE_BLOCKED")
    frozen = deepcopy(source)
    result = assess(support=source)
    assert result["packages"][0]["dimensions"]["governance"]["status"] == "RED"
    assert source == frozen
    source["governance"][0]["governance_state"] = "APPROVAL_REQUIRED"
    assert assess(support=source)["packages"][0]["dimensions"]["governance"]["status"] == "YELLOW"


def test_policy_rejects_unordered_thresholds():
    with pytest.raises(ValidationError, match="Yellow thresholds"):
        HealthPolicy.model_validate({**POLICY, "progress_yellow_deficit": "0.1"})
