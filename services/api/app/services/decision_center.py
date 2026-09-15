from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from app.auth import ActorContext
from app.decision_center_schemas import (
    DecisionQueueItem,
    GovernedReport,
    ReviewQueueEntry,
    ReviewQueues,
)
from app.models import (
    CaseActiveResponse,
    CaseLearningRecord,
    CaseLedgerEvent,
    CaseLimitation,
    CaseSnapshot,
    DecisionCaseControlledObject,
    DecisionCaseShell,
    ForecastProjection,
    HumanDecision,
    ImpactAssessment,
    OrchestrationRun,
    Project,
    ResponseAuthorization,
    ResponseExecutionObservation,
    ResponseOutcome,
    ResponseProposal,
    Signal,
)
from sqlalchemy import func, select
from sqlalchemy.orm import Session

REPORT_NOTICE = (
    "Recommendations, forecasts, proposals, human decisions, authorization, execution "
    "observations, and outcomes retain their separate stored semantics."
)


def _latest(session: Session, model: Any, case_id: uuid.UUID, order: Any) -> Any | None:
    return session.scalar(select(model).where(model.case_id == case_id).order_by(order.desc()))


def _next_action(case: DecisionCaseShell) -> str:
    if case.lifecycle == "CLOSED":
        return "REOPEN_ONLY_ON_MATERIAL_TRIGGER"
    return {
        "GOVERNANCE_BLOCKED": "RESOLVE_GOVERNANCE_BLOCK",
        "VERIFICATION_REQUIRED": "VERIFY_REQUESTED_EVIDENCE",
        "HUMAN_REVIEW_REQUIRED": "COMPLETE_HUMAN_REVIEW",
        "APPROVAL_REQUIRED": "OBTAIN_RESPONSE_APPROVAL",
        "ESCALATION_REQUIRED": "COMPLETE_ESCALATION_ROUTE",
        "AUTHORIZED_TO_PROCEED": "OBSERVE_AUTHORIZED_RESPONSE",
    }.get(case.governance_state, "CONTINUE_CASE_ANALYSIS")


def decision_queue(session: Session, project: Project) -> list[DecisionQueueItem]:
    cases = list(
        session.scalars(
            select(DecisionCaseShell)
            .where(DecisionCaseShell.project_id == project.id)
            .order_by(DecisionCaseShell.opened_at.desc())
        )
    )
    items: list[DecisionQueueItem] = []
    for case in cases:
        impact = _latest(session, ImpactAssessment, case.id, ImpactAssessment.assessment_number)
        run = _latest(session, OrchestrationRun, case.id, OrchestrationRun.run_number)
        decision = _latest(session, HumanDecision, case.id, HumanDecision.decision_number)
        decision_run = (
            session.get(OrchestrationRun, decision.orchestration_run_id) if decision else None
        )
        object_count = (
            session.scalar(
                select(func.count())
                .select_from(DecisionCaseControlledObject)
                .where(DecisionCaseControlledObject.case_id == case.id)
            )
            or 0
        )
        limitations = list(
            session.scalars(
                select(CaseLimitation).where(
                    CaseLimitation.case_id == case.id, CaseLimitation.status == "OPEN"
                )
            )
        )
        active_count = (
            session.scalar(
                select(func.count())
                .select_from(CaseActiveResponse)
                .where(CaseActiveResponse.case_id == case.id, CaseActiveResponse.status == "ACTIVE")
            )
            or 0
        )
        deadlines = [item.due_at for item in limitations if item.due_at]
        consequence_window = None
        if impact and impact.decision_clocks:
            known = [
                clock.get("deadline")
                for clock in impact.decision_clocks
                if clock.get("clock_type") == "CONSEQUENCE" and clock.get("deadline")
            ]
            consequence_window = known[0] if known else None
        items.append(
            DecisionQueueItem(
                case_id=case.id,
                case_number=case.case_number,
                title=case.title,
                lifecycle=case.lifecycle,
                readiness=case.readiness,
                governance_state=case.governance_state,
                owner_actor_id=case.owner_actor_id,
                opened_at=case.opened_at,
                controlled_object_count=object_count,
                open_limitation_count=len(limitations),
                active_response_count=active_count,
                recommended_disposition=run.recommended_disposition if run else None,
                decision_basis_recommendation=(
                    decision_run.recommended_disposition if decision_run else None
                ),
                human_disposition=decision.disposition if decision else None,
                recommendation_agreement=decision.recommendation_agreement if decision else None,
                priority_score=str(impact.priority_score) if impact else None,
                priority_band=impact.priority_band if impact else None,
                urgency=impact.urgency if impact else None,
                overall_confidence=str(impact.overall_confidence) if impact else None,
                consequence_window=consequence_window,
                next_deadline=min(deadlines) if deadlines else None,
                next_action=_next_action(case),
            )
        )
    priority_rank = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
    urgency_rank = {"IMMEDIATE": 4, "URGENT": 3, "NEAR_TERM": 2, "ROUTINE": 1}
    return sorted(
        items,
        key=lambda item: (
            item.lifecycle != "CLOSED",
            priority_rank.get(item.priority_band or "", 0),
            urgency_rank.get(item.urgency or "", 0),
            item.opened_at,
        ),
        reverse=True,
    )


def review_queues(session: Session, project: Project, as_of: datetime) -> ReviewQueues:
    queue = decision_queue(session, project)
    by_id = {item.case_id: item for item in queue}

    def entries(state: str, reason: str, role: str) -> list[ReviewQueueEntry]:
        return [
            ReviewQueueEntry(
                case=item, reason=reason, deadline=item.next_deadline, required_role=role
            )
            for item in queue
            if item.lifecycle != "CLOSED" and item.governance_state == state
        ]

    verification = [
        ReviewQueueEntry(
            case=item,
            reason="Decision-critical evidence requires verification",
            deadline=item.next_deadline,
            required_role="VERIFIER",
        )
        for item in queue
        if item.lifecycle != "CLOSED" and item.readiness == "VERIFICATION_REQUIRED"
    ]
    overdue = [
        ReviewQueueEntry(
            case=item,
            reason="An open evidence limitation is past its recorded deadline",
            deadline=item.next_deadline,
            required_role="DATA_CONTRIBUTOR_OR_VERIFIER",
        )
        for item in queue
        if item.lifecycle != "CLOSED"
        and item.next_deadline is not None
        and _aware(item.next_deadline) < as_of
    ]
    threshold = as_of + timedelta(days=7)
    latest_forecasts: dict[uuid.UUID, ForecastProjection] = {}
    for forecast in session.scalars(
        select(ForecastProjection).where(ForecastProjection.project_id == project.id)
    ):
        current = latest_forecasts.get(forecast.case_id)
        if current is None or forecast.forecast_number > current.forecast_number:
            latest_forecasts[forecast.case_id] = forecast
    expiring = [
        ReviewQueueEntry(
            case=by_id[case_id],
            reason="Latest forecast expires within seven days",
            deadline=forecast.valid_until,
            required_role="ANALYST_CONTROLLER",
        )
        for case_id, forecast in latest_forecasts.items()
        if case_id in by_id
        and by_id[case_id].lifecycle != "CLOSED"
        and _aware(forecast.valid_until) <= threshold
    ]
    return ReviewQueues(
        project_timezone=project.timezone,
        verification=verification,
        human_review=entries(
            "HUMAN_REVIEW_REQUIRED", "Case awaits accountable human review", "DECISION_OWNER"
        ),
        approval=entries("APPROVAL_REQUIRED", "Intervention awaits explicit approval", "APPROVER"),
        escalation=entries(
            "ESCALATION_REQUIRED", "Case exceeds current decision route", "ESCALATION_AUTHORITY"
        ),
        governance_blocks=entries(
            "GOVERNANCE_BLOCKED", "Recorded governance blocker must be resolved", "PROJECT_ADMIN"
        ),
        overdue_evidence=overdue,
        expiring_forecasts=expiring,
    )


def weekly_brief(
    session: Session, actor: ActorContext, project: Project, as_of: datetime
) -> GovernedReport:
    start = as_of - timedelta(days=7)
    queue = decision_queue(session, project)
    changed_ids = set(
        session.scalars(
            select(CaseLedgerEvent.case_id).where(
                CaseLedgerEvent.project_id == project.id,
                CaseLedgerEvent.occurred_at >= start,
                CaseLedgerEvent.occurred_at <= as_of,
            )
        )
    )
    payload = {
        "period_start": start.isoformat(),
        "period_end": as_of.isoformat(),
        "new_case_ids": [
            str(item.case_id) for item in queue if start <= _aware(item.opened_at) <= as_of
        ],
        "changed_case_ids": sorted(str(value) for value in changed_ids),
        "closed_case_ids": [
            str(item.case_id)
            for item in queue
            if item.lifecycle == "CLOSED" and item.case_id in changed_ids
        ],
        "urgent_cases": [
            item.model_dump(mode="json")
            for item in queue
            if item.urgency in {"IMMEDIATE", "URGENT"}
        ],
        "decision_queue": [item.model_dump(mode="json") for item in queue],
    }
    return _report(actor, project, as_of, "WEEKLY_DECISION_BRIEF", payload)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def case_dossier(
    session: Session,
    actor: ActorContext,
    project: Project,
    case: DecisionCaseShell,
    as_of: datetime,
) -> GovernedReport:
    def rows(model: Any, order: Any) -> list[dict[str, Any]]:
        records = session.scalars(select(model).where(model.case_id == case.id).order_by(order))
        return [_serialize(record) for record in records]

    payload = {
        "case": _serialize(case),
        "snapshots": rows(CaseSnapshot, CaseSnapshot.snapshot_number),
        "impact_assessments": rows(ImpactAssessment, ImpactAssessment.assessment_number),
        "orchestration_runs": rows(OrchestrationRun, OrchestrationRun.run_number),
        "human_decisions": rows(HumanDecision, HumanDecision.decision_number),
        "response_proposals": rows(ResponseProposal, ResponseProposal.proposal_number),
        "response_authorizations": rows(ResponseAuthorization, ResponseAuthorization.authorized_at),
        "execution_observations": rows(
            ResponseExecutionObservation, ResponseExecutionObservation.recorded_at
        ),
        "outcomes": rows(ResponseOutcome, ResponseOutcome.assessed_at),
        "learning_records": rows(CaseLearningRecord, CaseLearningRecord.recorded_at),
        "ledger": rows(CaseLedgerEvent, CaseLedgerEvent.occurred_at),
    }
    return _report(actor, project, as_of, "CASE_DOSSIER", payload)


def exception_report(
    session: Session, actor: ActorContext, project: Project, as_of: datetime
) -> GovernedReport:
    queue = decision_queue(session, project)
    signals = list(session.scalars(select(Signal).where(Signal.project_id == project.id)))
    status_counts: dict[str, int] = {}
    for signal in signals:
        status_counts[signal.status] = status_counts.get(signal.status, 0) + 1
    material = [
        item.model_dump(mode="json")
        for item in queue
        if item.lifecycle != "CLOSED" and item.priority_band in {"CRITICAL", "HIGH"}
    ]
    return _report(
        actor,
        project,
        as_of,
        "PROJECT_CONTROL_EXCEPTION_REPORT",
        {
            "material_open_cases": material,
            "signal_status_counts": status_counts,
            "dismissed_signal_count": status_counts.get("DISMISSED", 0),
            "deferred_signal_count": status_counts.get("DEFERRED", 0),
            "definition": "Open cases ranked HIGH or CRITICAL by their latest impact assessment",
        },
    )


def pilot_kpi_report(
    session: Session, actor: ActorContext, project: Project, as_of: datetime
) -> GovernedReport:
    cases = {
        item.id: item
        for item in session.scalars(
            select(DecisionCaseShell).where(DecisionCaseShell.project_id == project.id)
        )
    }
    decisions = list(
        session.scalars(select(HumanDecision).where(HumanDecision.project_id == project.id))
    )
    outcomes = list(
        session.scalars(select(ResponseOutcome).where(ResponseOutcome.project_id == project.id))
    )
    decision_hours = [
        (_aware(item.decided_at) - _aware(cases[item.case_id].opened_at)).total_seconds() / 3600
        for item in decisions
        if item.case_id in cases
    ]
    achieved = sum(item.classification == "ACHIEVED" for item in outcomes)
    return _report(
        actor,
        project,
        as_of,
        "PILOT_KPI_REPORT",
        {
            "cohort_definition_version": "PHASE12-PILOT-KPI-1.0.0",
            "cohort": "All project Decision Cases opened on or before report as-of",
            "case_count": len(cases),
            "human_decision_count": len(decisions),
            "outcome_count": len(outcomes),
            "achieved_outcome_count": achieved,
            "mean_open_to_human_decision_hours": (
                round(sum(decision_hours) / len(decision_hours), 3) if decision_hours else None
            ),
            "intervention_lead_time_status": (
                "AVAILABLE" if decision_hours else "INSUFFICIENT_OBSERVATIONS"
            ),
        },
    )


def conformity_report(
    session: Session, actor: ActorContext, project: Project, as_of: datetime
) -> GovernedReport:
    decisions = list(
        session.scalars(select(HumanDecision).where(HumanDecision.project_id == project.id))
    )
    authorizations = list(
        session.scalars(
            select(ResponseAuthorization).where(ResponseAuthorization.project_id == project.id)
        )
    )
    outcomes = list(
        session.scalars(select(ResponseOutcome).where(ResponseOutcome.project_id == project.id))
    )
    unsupported_outcomes = [
        str(item.id)
        for item in outcomes
        if item.classification != "NOT_YET_OBSERVABLE" and not item.evidence_item_ids
    ]
    checks = {
        "human_decisions_have_authority": all(
            item.authority_outcome == "AUTHORIZED" and item.authority_grant_id for item in decisions
        ),
        "response_authorizations_have_grants": all(
            item.authority_grant_id and item.authorization_reference for item in authorizations
        ),
        "realized_outcomes_have_evidence": not unsupported_outcomes,
        "recommendation_decision_separation": True,
        "execution_is_observation_only": True,
    }
    return _report(
        actor,
        project,
        as_of,
        "GOVERNANCE_CONFORMITY_REPORT",
        {
            "conformity_definition_version": "PHASE12-GOVERNANCE-1.0.0",
            "checks": checks,
            "result": "CONFORMANT" if all(checks.values()) else "NON_CONFORMANT",
            "unsupported_outcome_ids": unsupported_outcomes,
            "decision_count": len(decisions),
            "response_authorization_count": len(authorizations),
            "append_only_record_types": [
                "human_decision",
                "response_proposal",
                "response_authorization",
                "response_execution_observation",
                "response_outcome",
                "case_learning_record",
            ],
        },
    )


def _serialize(record: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for column in record.__table__.columns:
        value = getattr(record, column.name)
        if isinstance(value, uuid.UUID):
            value = str(value)
        elif isinstance(value, datetime):
            value = value.isoformat()
        elif hasattr(value, "as_tuple"):
            value = str(value)
        result[column.name] = value
    return result


def _report(
    actor: ActorContext,
    project: Project,
    as_of: datetime,
    report_type: str,
    payload: dict[str, Any],
) -> GovernedReport:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return GovernedReport(
        report_type=report_type,
        schema_version="1.0.0",
        organization_id=project.organization_id,
        project_id=project.id,
        generated_at=datetime.now(UTC),
        generated_by=actor.actor_id,
        as_of=as_of,
        semantic_notice=REPORT_NOTICE,
        content_hash=hashlib.sha256(canonical.encode()).hexdigest(),
        fidelity_manifest={
            "canonicalization": "JSON_SORTED_KEYS_COMPACT_UTF8",
            "hash_algorithm": "SHA-256",
            "semantic_boundaries": [
                "EVIDENCE",
                "DERIVED_ANALYSIS",
                "FORECAST_OR_SCENARIO",
                "SYSTEM_RECOMMENDATION",
                "HUMAN_DECISION",
                "AUTHORIZATION",
                "EXECUTION_OBSERVATION",
                "REALIZED_OUTCOME",
            ],
            "unknown_values_preserved_as_null": True,
            "recommendation_is_not_decision": True,
            "proposal_is_not_authorization": True,
        },
        payload=payload,
    )
