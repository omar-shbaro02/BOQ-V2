"""Read-only, deterministic answers from a single immutable snapshot; no model or action tools."""

import hashlib
import json
import re

from app.assistant_schemas import SnapshotQuestion
from app.health_schemas import utc_datetime
from app.models import ProjectControlSnapshot
from app.services.control_metrics import shared_metrics

GENERATOR_VERSION = "SNAPSHOT-ASSISTANT-1.0.0"
NOTICE = (
    "Read-only snapshot analysis. Reported claims, derived metrics, forecasts, and authorization "
    "remain separate. Management considerations require human review "
    "and grant no execution authority."
)


def source_allowlist(snapshot: ProjectControlSnapshot) -> set[str]:
    allowed = {
        str(snapshot.id),
        str(snapshot.schedule_context_id),
        str(snapshot.progress_weighting_context_id),
        *snapshot.input_evidence_ids,
    }
    for package in snapshot.package_results:
        allowed.update(
            [
                package["controlled_object_id"],
                package["planned_measurement_id"],
                package["actual_measurement_id"],
            ]
        )
    for item in snapshot.cost_assessment_refs + snapshot.forecast_projection_refs:
        allowed.update(
            str(item[key])
            for key in ("id", "case_id", "controlled_object_id", "budget_context_id")
            if item.get(key)
        )
    support = snapshot.supporting_context or {}
    for item in support.get("project_context", []):
        allowed.add(item["id"])
        allowed.update(item["evidence_item_ids"])
        allowed.update(item["lifecycle_event_ids"])
    for item in support.get("schedule_assessments", []):
        allowed.update([item["id"], item["case_id"], *item["input_evidence_ids"]])
    for item in support.get("governance", []):
        allowed.update(
            value
            for value in (item["case_id"], item["case_snapshot_id"], item["audit_event_id"])
            if value
        )
        allowed.update(item.get("contradiction_ids", []))
    return allowed


def fact_catalog(snapshot: ProjectControlSnapshot) -> dict[str, dict]:
    facts = {}
    snapshot_id = str(snapshot.id)
    metrics = shared_metrics(snapshot)

    def add(
        key,
        topic,
        label,
        value,
        unit=None,
        state=None,
        truth="DERIVED_METRIC",
        sources=None,
        limitations=None,
        source_date=None,
    ):
        facts[key] = {
            "key": key,
            "topic": topic,
            "label": label,
            "value": value,
            "unit": unit,
            "semantic_state": state,
            "truth_type": truth if value is not None else "UNKNOWN",
            "source_refs": sorted(set([snapshot_id, *(sources or [])])),
            "limitations": limitations or [],
            "data_date": source_date or utc_datetime(snapshot.data_date).isoformat(),
        }

    add(
        "completion.planned",
        "COMPLETION",
        "Authorized planned completion",
        metrics["planned"]["percent"],
        "percent",
        "CURRENT_AUTHORIZED",
        sources=[str(snapshot.schedule_context_id), str(snapshot.progress_weighting_context_id)],
    )
    add(
        "completion.actual",
        "COMPLETION",
        "Verified/accepted completion on the selected measurement basis",
        metrics["actual"]["percent"],
        "percent",
        "ACTUAL",
        sources=snapshot.input_evidence_ids,
    )
    add(
        "completion.variance",
        "COMPLETION",
        "Actual minus authorized planned completion",
        metrics["variance"]["percent"],
        "percentage points",
        "ACTUAL",
    )
    add(
        "completion.basis",
        "COMPLETION",
        "Progress measurement basis",
        snapshot.measurement_basis,
        sources=[str(snapshot.progress_weighting_context_id)],
    )
    for index, package in enumerate(snapshot.package_results):
        add(
            f"completion.package.{index}",
            "COMPLETION",
            f"Package {package['controlled_object_code']}",
            {
                "planned_ratio": package["planned_ratio"],
                "actual_ratio": package["actual_ratio"],
                "actual_measurement_kind": package["actual_measurement_kind"],
                "weight": package["weight"],
            },
            sources=[package["planned_measurement_id"], package["actual_measurement_id"]],
        )
    schedules = (snapshot.supporting_context or {}).get("schedule_assessments", [])
    if not schedules:
        add(
            "schedule.unknown",
            "SCHEDULE",
            "Supported completion exposure",
            None,
            limitations=["No exact schedule assessment is bound to this snapshot."],
        )
    for index, item in enumerate(schedules):
        add(
            f"schedule.{index}",
            "SCHEDULE",
            f"Schedule assessment for {item['controlled_object_id']}",
            {
                key: item[key]
                for key in (
                    "assessment_status",
                    "schedule_quality",
                    "project_completion_exposure_days",
                    "maximum_supported_conclusion",
                    "data_date",
                    "confidence",
                    "stale",
                )
            },
            "days in the bound assessment; inspect its conclusion limits",
            truth=item["truth_type"],
            sources=[item["id"], *item["input_evidence_ids"]],
            limitations=item["limitations"],
            source_date=item["data_date"],
        )
    if not snapshot.cost_assessment_refs:
        add(
            "cost.unknown",
            "COST",
            "Cost position and EAC",
            None,
            limitations=["No cost assessment is bound; no zero or project total is inferred."],
        )
    for index, item in enumerate(snapshot.cost_assessment_refs):
        add(
            f"cost.{index}.assessment_status",
            "COST",
            "Bound cost assessment readiness",
            item["assessment_status"],
            sources=[item["id"]],
            source_date=item["data_date"],
            limitations=item["limitations"],
        )
        for field, state in (
            ("current_authorized_budget", "CURRENT_AUTHORIZED"),
            ("commitments", "ACTUAL"),
            ("actuals", "ACTUAL"),
            ("accruals", "ACTUAL"),
            ("forecast_to_complete", "FORECAST"),
            ("estimate_at_completion", "FORECAST"),
        ):
            add(
                f"cost.{index}.{field}",
                "COST",
                f"{item['controlled_object_id']}: {field.replace('_', ' ')}",
                item[field] if item["assessment_status"] == "ASSESSED" else None,
                item["currency"],
                state,
                item["truth_type"],
                [item["id"]],
                item["limitations"]
                + (
                    []
                    if item["assessment_status"] == "ASSESSED"
                    else [
                        "Cost conclusion is restricted; stored intermediate totals "
                        "are not a supported position."
                    ]
                ),
                source_date=item["data_date"],
            )
    if not snapshot.forecast_projection_refs:
        add(
            "forecast.unknown",
            "FORECAST",
            "Bound forecast",
            None,
            limitations=["No supported non-hypothetical forecast is selected."],
        )
    for index, item in enumerate(snapshot.forecast_projection_refs):
        add(
            f"forecast.{index}",
            "FORECAST",
            f"Forecast: {item['target']}",
            {
                key: item[key]
                for key in (
                    "target",
                    "scenario_type",
                    "status",
                    "data_date",
                    "horizon_end",
                    "result_point",
                    "result_lower",
                    "result_upper",
                    "horizon_confidence",
                    "valid_until",
                )
            },
            item["result_unit"],
            "FORECAST",
            item["truth_type"],
            [item["id"]],
            item["limitations"],
            source_date=item["data_date"],
        )
    health = snapshot.health or {}
    add(
        "rag.overall",
        "RAG",
        "Derived project RAG",
        health.get("status"),
        limitations=health.get("limitations", ["Health was not frozen on this legacy snapshot."]),
    )
    for name, item in health.get("dimensions", {}).items():
        add(
            f"rag.{name}",
            "RAG",
            f"Derived {name} RAG",
            item["status"],
            sources=item["input_refs"],
            limitations=item["limitations"],
        )
    contexts = (snapshot.supporting_context or {}).get("project_context", [])
    risks = [
        item for item in contexts if item["record_type"] in {"RISK", "ISSUE", "CHANGE_REQUEST"}
    ]
    if not risks:
        add(
            "risks.unknown",
            "RISKS",
            "Stored risk/issue/change context",
            None,
            limitations=[
                "No cut-off-valid context is frozen; absence does not establish no risks."
            ],
        )
    for index, item in enumerate(risks):
        add(
            f"risks.{index}",
            "RISKS",
            f"Reported {item['record_type'].replace('_', ' ').lower()}",
            {
                "record_type": item["record_type"],
                "status": item["status"],
                "reported_payload": item["payload"],
                "effective_from": item["effective_from"],
                "recorded_at": item["recorded_at"],
            },
            state="REPORTED",
            truth="REPORTED_CLAIM",
            sources=[item["id"], *item["evidence_item_ids"]],
            limitations=[item["semantic_notice"]],
        )
    add(
        "evidence.references",
        "EVIDENCE",
        "Bound evidence record IDs",
        snapshot.input_evidence_ids,
        sources=snapshot.input_evidence_ids,
    )
    add(
        "evidence.confidence",
        "EVIDENCE",
        "Minimum verified progress confidence",
        str(snapshot.confidence),
    )
    add("evidence.limitations", "EVIDENCE", "Snapshot limitations", snapshot.limitations)
    due_records = [
        item
        for item in risks
        if item["payload"].get("due_date")
        and item["status"] not in {"CLOSED", "RESOLVED", "REJECTED"}
    ]
    if not due_records:
        add(
            "next_review.unknown",
            "NEXT_REVIEW",
            "Next recorded review deadline",
            None,
            limitations=[
                "No explicit open risk/issue review deadline is frozen; do not invent a date."
            ],
        )
    for index, item in enumerate(
        sorted(due_records, key=lambda value: (value["payload"]["due_date"], value["id"]))
    ):
        add(
            f"next_review.{index}",
            "NEXT_REVIEW",
            "Reported context review deadline",
            {
                "due_date": item["payload"]["due_date"],
                "owner_actor_id": item["payload"].get("owner_actor_id"),
                "title": item["payload"].get("title"),
            },
            state="REPORTED",
            truth="REPORTED_CLAIM",
            sources=[item["id"]],
        )
    return facts


def consideration_catalog(snapshot: ProjectControlSnapshot) -> list[dict]:
    considerations = []
    for package in (snapshot.health or {}).get("packages", []):
        for dimension, result in package["dimensions"].items():
            if result["status"] in {"RED", "YELLOW"}:
                considerations.append(
                    {
                        "text": (
                            f"Consider reviewing {package['controlled_object_code']} {dimension} "
                            "evidence and its recorded human-review route."
                        ),
                        "status": "MANAGEMENT_CONSIDERATION",
                        "review_route": result["review_route"],
                        "source_refs": sorted(set([str(snapshot.id), *result["input_refs"]])),
                    }
                )
    return considerations


def validate_grounding(answer: dict, snapshot: ProjectControlSnapshot) -> None:
    catalog = fact_catalog(snapshot)
    allowed = source_allowlist(snapshot)
    if (
        answer["snapshot_id"] != str(snapshot.id)
        or answer["generator_version"] != GENERATOR_VERSION
        or answer["semantic_notice"] != NOTICE
    ):
        raise ValueError("Assistant source or semantic boundary mismatch")
    for fact in answer["facts"]:
        if fact["key"] not in catalog or fact != catalog[fact["key"]]:
            raise ValueError("Assistant fact differs from the selected immutable source")
        if set(fact["source_refs"]) - allowed:
            raise ValueError("Assistant cited a record outside the selected snapshot")
    for consideration in answer["considerations"]:
        if consideration not in consideration_catalog(snapshot):
            raise ValueError("Unsupported advisory or authority claim")
        if set(consideration["source_refs"]) - allowed:
            raise ValueError("Advisory reference is outside the selected snapshot")


def answer_question(snapshot: ProjectControlSnapshot, question: SnapshotQuestion) -> dict:
    text = question.question.lower()
    blocked = bool(
        re.search(
            r"\b(ignore|override)\b|\b(system|developer)\s*:|"
            r"\b(approve|authorize|execute|delete|overwrite|grant|send)\b",
            text,
        )
    )
    topic = question.topic
    if topic is None:
        rules = [
            ("NEXT_REVIEW", r"next|review|deadline"),
            ("RISKS", r"risk|issue|blocker|change request"),
            ("COST", r"cost|budget|eac|actuals|accrual|commitment"),
            ("FORECAST", r"forecast|predict"),
            ("RAG", r"rag|health|status|red|yellow|green"),
            ("EVIDENCE", r"evidence|confidence|uncertainty"),
            ("SCHEDULE", r"schedule|delay|finish|float"),
            ("COMPLETION", r"completion|complete|progress|percent"),
            ("OVERVIEW", r"overview|where.*stand|summary"),
        ]
        topic = next((name for name, pattern in rules if re.search(pattern, text)), None)
    catalog = fact_catalog(snapshot)
    facts = (
        []
        if blocked or topic is None
        else [item for item in catalog.values() if topic == "OVERVIEW" or item["topic"] == topic]
    )
    considerations = consideration_catalog(snapshot) if not blocked and topic else []
    answer = {
        "snapshot_id": str(snapshot.id),
        "data_date": utc_datetime(snapshot.data_date).isoformat(),
        "topic": topic or "UNSUPPORTED",
        "status": "ACTION_NOT_PERMITTED"
        if blocked
        else "SUPPORTED"
        if topic
        else "UNSUPPORTED_QUESTION",
        "generator_version": GENERATOR_VERSION,
        "semantic_notice": NOTICE,
        "facts": facts,
        "considerations": considerations,
        "limitations": [
            "Only this selected immutable snapshot is used; no current project state is queried.",
            "This assistant cannot change records, approve, authorize, execute, "
            "or send communications.",
        ],
    }
    validate_grounding(answer, snapshot)
    answer["answer_hash"] = hashlib.sha256(
        json.dumps(answer, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()
    return answer
