"""Deterministic package-first RAG; colors summarize rules, never authority or factual truth."""

from decimal import Decimal

from app.health_schemas import HealthPolicy

FORMULA_VERSION = "PROJECT-RAG-1.0.0"
DIMENSIONS = ("progress", "schedule", "cost", "evidence", "governance")
NOTICE = (
    "RAG is derived management attention, not a human decision, "
    "execution approval, or verification."
)


def severity(statuses: list[str]) -> str:
    if "RED" in statuses:
        return "RED"
    if "YELLOW" in statuses:
        return "YELLOW"
    if "UNKNOWN" in statuses or not statuses:
        return "UNKNOWN"
    return "GREEN"


def threshold(value: Decimal, yellow: Decimal, red: Decimal) -> str:
    return "RED" if value >= red else "YELLOW" if value >= yellow else "GREEN"


def compute_health(
    packages: list[dict],
    costs: list[dict],
    support: dict,
    policy: HealthPolicy | None,
    data_date: str,
) -> dict:
    def finding(
        status="UNKNOWN",
        rule="INPUT_UNAVAILABLE",
        value=None,
        thresholds=None,
        sources=None,
        confidence=None,
        limitations=None,
        route=None,
    ):
        return {
            "status": status,
            "rule": rule,
            "value": str(value) if value is not None else None,
            "thresholds": thresholds or {},
            "input_refs": sources or [],
            "data_date": data_date,
            "confidence": str(confidence) if confidence is not None else None,
            "limitations": limitations or [],
            "review_route": route if status in {"RED", "YELLOW"} else None,
        }

    if policy is None or not packages:
        return {
            "formula_version": FORMULA_VERSION,
            "policy": None,
            "status": "UNKNOWN",
            "data_date": data_date,
            "semantic_notice": NOTICE,
            "limitations": ["PROJECT_RAG_POLICY_OR_PACKAGE_INPUTS_UNAVAILABLE"],
            "packages": [],
            "dimensions": {},
        }
    results = []
    for package in packages:
        object_id = package["controlled_object_id"]
        route = {
            "type": "SIGNAL_REVIEW",
            "url": "/signals",
            "controlled_object_id": object_id,
            "controlled_object_code": package["controlled_object_code"],
        }
        confidence = Decimal(package["actual_confidence"])
        deficit = Decimal(package["planned_ratio"]) - Decimal(package["actual_ratio"])
        inputs = [package["planned_measurement_id"], package["actual_measurement_id"]]
        progress = finding(
            threshold(deficit, policy.progress_yellow_deficit, policy.progress_red_deficit),
            "AUTHORIZED_PLAN_MINUS_VERIFIED_COMPLETION",
            deficit,
            {
                "yellow_at_least": str(policy.progress_yellow_deficit),
                "red_at_least": str(policy.progress_red_deficit),
            },
            inputs,
            confidence,
            route=route,
        )
        evidence_status = (
            "RED"
            if confidence < policy.evidence_red_below
            else "GREEN"
            if confidence >= policy.evidence_green_at_least
            else "YELLOW"
        )
        evidence = finding(
            evidence_status,
            "VERIFIED_INPUT_CONFIDENCE",
            confidence,
            {
                "red_below": str(policy.evidence_red_below),
                "green_at_least": str(policy.evidence_green_at_least),
            },
            inputs,
            confidence,
            route=route,
        )
        schedules = [
            item
            for item in support.get("schedule_assessments", [])
            if item["controlled_object_id"] == object_id
        ]
        schedule = finding(limitations=["EXACT_SCHEDULE_ASSESSMENT_UNAVAILABLE"])
        if len(schedules) == 1:
            item = schedules[0]
            exposure = item["project_completion_exposure_days"]
            if (
                item["assessment_status"] == "ASSESSED"
                and item["schedule_quality"] == "VALID"
                and not item["stale"]
                and exposure is not None
            ):
                schedule = finding(
                    threshold(
                        Decimal(exposure), policy.schedule_yellow_days, policy.schedule_red_days
                    ),
                    "SUPPORTED_NETWORK_COMPLETION_EXPOSURE",
                    exposure,
                    {
                        "yellow_at_least_days": str(policy.schedule_yellow_days),
                        "red_at_least_days": str(policy.schedule_red_days),
                    },
                    [item["id"], *item["input_evidence_ids"]],
                    item["confidence"],
                    item["limitations"],
                    {"type": "DECISION_CASE", "url": "/cases", "case_id": item["case_id"]},
                )
            else:
                schedule = finding(
                    rule="SCHEDULE_CONCLUSION_RESTRICTED",
                    sources=[item["id"]],
                    confidence=item["confidence"],
                    limitations=item["limitations"]
                    or ["Insufficient, stale, or unsupported completion exposure"],
                )
        elif len(schedules) > 1:
            schedule = finding(
                rule="AMBIGUOUS_SCHEDULE_BASIS", sources=[item["id"] for item in schedules]
            )
        package_costs = [item for item in costs if item["controlled_object_id"] == object_id]
        cost = finding(limitations=["EXACT_COST_ASSESSMENT_UNAVAILABLE"])
        if len(package_costs) == 1:
            item = package_costs[0]
            budget = Decimal(item["current_authorized_budget"])
            eac = item["estimate_at_completion"]
            if (
                item["assessment_status"] == "ASSESSED"
                and eac is not None
                and budget > 0
                and not item.get("stale", False)
            ):
                overrun = (Decimal(eac) - budget) / budget
                cost = finding(
                    threshold(overrun, policy.cost_yellow_overrun, policy.cost_red_overrun),
                    "EAC_OVER_AUTHORIZED_BUDGET",
                    overrun,
                    {
                        "yellow_at_least": str(policy.cost_yellow_overrun),
                        "red_at_least": str(policy.cost_red_overrun),
                    },
                    [item["id"]],
                    item["confidence"],
                    item["limitations"],
                    {"type": "DECISION_CASE", "url": "/cases", "case_id": item["case_id"]},
                )
            else:
                cost = finding(
                    rule="COST_CONCLUSION_RESTRICTED",
                    sources=[item["id"]],
                    limitations=item["limitations"]
                    or ["EAC, compatible budget, or current evidence unavailable"],
                )
        elif len(package_costs) > 1:
            cost = finding(
                rule="AMBIGUOUS_COST_BASIS", sources=[item["id"] for item in package_costs]
            )
        cases = [
            item
            for item in support.get("governance", [])
            if object_id in item["controlled_object_ids"]
        ]
        contradictions = sorted(
            {identifier for item in cases for identifier in item.get("contradiction_ids", [])}
        )
        if contradictions:
            evidence = finding(
                "RED",
                "SNAPSHOT_CONTRADICTION_REQUIRES_REVIEW",
                sources=contradictions,
                confidence=confidence,
                limitations=["Unresolved snapshot contradictions restrict conclusions."],
                route=route,
            )
            progress = finding(
                rule="CONTRADICTED_PROGRESS_REQUIRES_REVIEW",
                value=deficit,
                sources=inputs + contradictions,
                confidence=confidence,
                limitations=[
                    "Comparison is retained, but a supported progress conclusion is withheld."
                ],
            )
        governance = finding(limitations=["HISTORICAL_GOVERNANCE_STATE_UNAVAILABLE"])
        if cases:
            states = []
            for item in cases:
                state = item["governance_state"]
                states.append(
                    "RED"
                    if state == "GOVERNANCE_BLOCKED"
                    else "GREEN"
                    if state in {"ANALYSIS_AUTHORIZED", "AUTHORIZED_TO_PROCEED"}
                    else "YELLOW"
                    if state
                    in {
                        "VERIFICATION_REQUIRED",
                        "HUMAN_REVIEW_REQUIRED",
                        "APPROVAL_REQUIRED",
                        "ESCALATION_REQUIRED",
                    }
                    else "UNKNOWN"
                )
            governance = finding(
                severity(states),
                "FROZEN_CASE_GOVERNANCE_ROUTE",
                thresholds={
                    "red_states": ["GOVERNANCE_BLOCKED"],
                    "green_states": ["ANALYSIS_AUTHORIZED", "AUTHORIZED_TO_PROCEED"],
                    "yellow_states": [
                        "VERIFICATION_REQUIRED",
                        "HUMAN_REVIEW_REQUIRED",
                        "APPROVAL_REQUIRED",
                        "ESCALATION_REQUIRED",
                    ],
                },
                sources=[item["audit_event_id"] for item in cases if item["audit_event_id"]],
                limitations=["A clear analysis route does not authorize execution."],
                route={
                    "type": "DECISION_CASE",
                    "url": "/cases",
                    "case_ids": [item["case_id"] for item in cases],
                },
            )
        dimensions = {
            "progress": progress,
            "schedule": schedule,
            "cost": cost,
            "evidence": evidence,
            "governance": governance,
        }
        results.append(
            {
                "controlled_object_id": object_id,
                "controlled_object_code": package["controlled_object_code"],
                "weight": package["weight"],
                "status": severity([item["status"] for item in dimensions.values()]),
                "dimensions": dimensions,
                "review_route": route
                if severity([item["status"] for item in dimensions.values()]) in {"RED", "YELLOW"}
                else None,
            }
        )
    project_dimensions = {}
    for dimension in DIMENSIONS:
        red_weight = sum(
            (
                Decimal(item["weight"])
                for item in results
                if item["dimensions"][dimension]["status"] == "RED"
            ),
            Decimal(0),
        )
        unknown_weight = sum(
            (
                Decimal(item["weight"])
                for item in results
                if item["dimensions"][dimension]["status"] == "UNKNOWN"
            ),
            Decimal(0),
        )
        statuses = [item["dimensions"][dimension]["status"] for item in results]
        status = (
            "RED"
            if red_weight >= policy.material_weight_threshold
            else "YELLOW"
            if any(value in {"RED", "YELLOW"} for value in statuses)
            else "UNKNOWN"
            if unknown_weight
            else "GREEN"
        )
        project_dimensions[dimension] = finding(
            status,
            "WEIGHTED_PACKAGE_MATERIALITY",
            red_weight,
            {"red_weight_at_least": str(policy.material_weight_threshold)},
            [item["controlled_object_id"] for item in results],
            limitations=[f"Unknown package weight: {unknown_weight}"],
            route={
                "type": "PACKAGE_REVIEW",
                "url": "/signals",
                "controlled_object_ids": [
                    item["controlled_object_id"]
                    for item in results
                    if item["dimensions"][dimension]["status"] in {"RED", "YELLOW"}
                ],
            },
        )
        project_dimensions[dimension]["unknown_weight"] = str(unknown_weight)
        confidences = [item["dimensions"][dimension]["confidence"] for item in results]
        if confidences and all(value is not None for value in confidences):
            project_dimensions[dimension]["confidence"] = str(
                min(Decimal(value) for value in confidences)
            )
    return {
        "formula_version": FORMULA_VERSION,
        "policy": policy.model_dump(mode="json"),
        "policy_status": "EXPLICIT_PROJECT_POLICY",
        "data_date": data_date,
        "status": severity([item["status"] for item in project_dimensions.values()]),
        "semantic_notice": NOTICE,
        "limitations": ["Unknown dimensions are never Green."],
        "packages": results,
        "dimensions": project_dimensions,
        "review_route": {"type": "PACKAGE_REVIEW", "url": "/signals"}
        if severity([item["status"] for item in project_dimensions.values()]) in {"RED", "YELLOW"}
        else None,
    }
