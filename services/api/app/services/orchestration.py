from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from app.auth import ActorContext
from app.config import get_settings
from app.generated.taxonomies import (
    CaseLedgerEventType,
    CaseLifecycle,
    ConsequenceSeverity,
    DecisionReadiness,
    Disposition,
    GovernanceState,
    ImpactAssessmentStatus,
    OrchestrationStatus,
    SpecialistContradictionType,
    SpecialistKind,
    SpecialistRunStatus,
    TruthType,
    UrgencyLevel,
)
from app.models import (
    CaseSnapshot,
    CostAssessment,
    ForecastProjection,
    ImpactAssessment,
    OrchestrationRun,
    ProgressEvaluation,
    Project,
    ScheduleAssessment,
    SpecialistContradictionResolution,
    SpecialistRun,
)
from app.orchestration_schemas import ContradictionResolutionCreate, OrchestrationCreate
from app.services.agent_automation import run_specialist_agent
from app.services.cases import add_ledger, audit_case, require_version, scoped_case
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

CONTRACT_VERSION = "SPECIALIST-CONTRACT-1.0.0"
FORMULA_VERSION = "ORCHESTRATOR-DETERMINISTIC-1.0.0"
NARRATIVE_VALIDATOR_VERSION = "CASE-BRIEF-FIDELITY-1.0.0"


def request_digest(data: OrchestrationCreate) -> str:
    return hashlib.sha256(
        json.dumps(data.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _input(
    session: Session,
    model: type,
    identifier: uuid.UUID | None,
    case_id: uuid.UUID,
    snapshot_id: uuid.UUID,
    label: str,
) -> Any | None:
    if identifier is None:
        return None
    value = session.get(model, identifier)
    if value is None or value.case_id != case_id or value.snapshot_id != snapshot_id:
        raise HTTPException(status_code=422, detail=f"{label} input is outside this snapshot")
    return value


def _status(value: Any | None, restricted: set[str]) -> SpecialistRunStatus:
    if value is None:
        return SpecialistRunStatus.LIMITED
    upstream = str(getattr(value, "assessment_status", getattr(value, "status", "")))
    return SpecialistRunStatus.LIMITED if upstream in restricted else SpecialistRunStatus.SUCCEEDED


def _specialist(
    run: OrchestrationRun,
    kind: SpecialistKind,
    value: Any | None,
    *,
    output_key: str,
    restricted: set[str] = frozenset(),
    questions: list[str],
    contradictions: list[dict[str, Any]] | None = None,
    attempt: int = 1,
) -> SpecialistRun:
    status = _status(value, restricted)
    evidence = list(getattr(value, "input_evidence_ids", [])) if value else []
    limitations = (
        list(getattr(value, "limitations", []))
        if value
        else [
            {
                "code": "SPECIALIST_INPUT_NOT_SELECTED",
                "description": f"No {kind.value} result selected",
            }
        ]
    )
    confidence = Decimal(str(getattr(value, "confidence", 0))) if value else Decimal("0")
    if kind == SpecialistKind.IMPACT_PRIORITY and value:
        confidence = Decimal(str(value.overall_confidence))
    truth_type = getattr(value, "truth_type", None) if value else None
    input_references = {"snapshot_id": str(run.snapshot_id), "requested_questions": questions}
    output_references = {output_key: str(value.id)} if value else {}
    findings: list[dict[str, Any]] = []
    calculations: list[dict[str, Any]] = []
    requested_evidence: list[dict[str, Any]] = []
    settings = get_settings()
    configured_key = settings.openai_api_key.get_secret_value() if settings.openai_api_key else ""
    if value is not None and settings.openai_agents_enabled and configured_key:
        selected_input = {
            column.name: getattr(value, column.name) for column in value.__table__.columns
        }
        agent = run_specialist_agent(
            kind,
            api_key=configured_key,
            model=settings.openai_agent_model,
            snapshot_id=str(run.snapshot_id),
            selected_input=selected_input,
            requested_questions=questions,
            allowed_evidence_ids={str(item) for item in evidence},
        )
        agent_output = agent.output
        findings = agent_output["findings"]
        calculations = agent_output["calculations"]
        evidence = agent_output["evidence_references"]
        limitations = [*limitations, *agent_output["limitations"]]
        requested_evidence = agent_output["requested_evidence"]
        contradictions = [*list(contradictions or []), *agent_output["contradictions"]]
        confidence = min(confidence, Decimal(str(agent_output["confidence"])))
        input_references.update(
            {
                "execution_mode": "OPENAI_AGENT",
                "agent_model": agent.model,
                "prompt_version": agent.prompt_version,
            }
        )
        output_references["openai_response_id"] = agent.response_id
    else:
        input_references["execution_mode"] = "DETERMINISTIC_FALLBACK"
    return SpecialistRun(
        id=uuid.uuid4(),
        organization_id=run.organization_id,
        project_id=run.project_id,
        orchestration_run_id=run.id,
        case_id=run.case_id,
        snapshot_id=run.snapshot_id,
        specialist_kind=kind,
        status=status,
        attempt=attempt,
        input_references=input_references,
        output_references=output_references,
        findings=findings,
        calculations=calculations,
        evidence_references=evidence,
        truth_labels=[str(truth_type)] if truth_type else [],
        assumptions=list(getattr(value, "assumptions", [])) if value else [],
        contradictions=list(contradictions or []),
        confidence=confidence,
        limitations=limitations,
        requested_evidence=requested_evidence,
        contract_version=CONTRACT_VERSION,
        error_class=None,
        completed_at=datetime.now(UTC),
    )


def _safe_specialist(
    run: OrchestrationRun,
    kind: SpecialistKind,
    value: Any | None,
    **kwargs: Any,
) -> SpecialistRun:
    try:
        return _specialist(run, kind, value, **kwargs)
    except Exception as exc:  # specialist failures must be persisted, not hidden
        return SpecialistRun(
            id=uuid.uuid4(),
            organization_id=run.organization_id,
            project_id=run.project_id,
            orchestration_run_id=run.id,
            case_id=run.case_id,
            snapshot_id=run.snapshot_id,
            specialist_kind=kind,
            status=SpecialistRunStatus.FAILED,
            attempt=int(kwargs.get("attempt", 1)),
            input_references={"snapshot_id": str(run.snapshot_id)},
            output_references={},
            findings=[],
            calculations=[],
            evidence_references=[],
            truth_labels=[],
            assumptions=[],
            contradictions=list(kwargs.get("contradictions") or []),
            confidence=Decimal("0"),
            limitations=[
                {
                    "code": "SPECIALIST_EXECUTION_FAILED",
                    "description": "Specialist produced no validated output",
                }
            ],
            requested_evidence=[],
            contract_version=CONTRACT_VERSION,
            error_class=type(exc).__name__,
            completed_at=datetime.now(UTC),
        )


def _disposition(impact: ImpactAssessment | None) -> tuple[Disposition, DecisionReadiness]:
    if impact is None or impact.assessment_status == ImpactAssessmentStatus.VERIFICATION_REQUIRED:
        return Disposition.VERIFY, DecisionReadiness.VERIFICATION_REQUIRED
    if impact.consequence_severity == ConsequenceSeverity.NONE:
        if impact.urgency == UrgencyLevel.NONE:
            return Disposition.NO_ACTION, DecisionReadiness.DECISION_READY_WITH_LIMITATIONS
        return Disposition.MONITOR, DecisionReadiness.DECISION_READY
    if impact.urgency == UrgencyLevel.IMMEDIATE or impact.priority_band == "CRITICAL":
        return Disposition.ESCALATE, DecisionReadiness.DECISION_READY
    if impact.consequence_severity in {
        ConsequenceSeverity.MEDIUM,
        ConsequenceSeverity.HIGH,
        ConsequenceSeverity.CRITICAL,
    }:
        return Disposition.INTERVENE, DecisionReadiness.DECISION_READY
    return Disposition.MONITOR, DecisionReadiness.DECISION_READY


def _contradictions(
    impact: ImpactAssessment | None,
    progress: ProgressEvaluation | None,
    schedule: ScheduleAssessment | None,
    cost: CostAssessment | None,
    forecasts: list[ForecastProjection],
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    selected = {
        "PROGRESS": progress,
        "SCHEDULE": schedule,
        "COST": cost,
    }
    for label, value in selected.items():
        if value and str(value.truth_type) == TruthType.CONTRADICTED:
            findings.append(
                {
                    "type": SpecialistContradictionType.SOURCE.value,
                    "material": True,
                    "status": "UNRESOLVED",
                    "source_result_ids": [str(value.id)],
                    "description": f"{label} result is derived from contradicted truth",
                    "downstream_invalidations": ["DISPOSITION", "CASE_BRIEF_CONCLUSION"],
                }
            )
        if impact and value and value.controlled_object_id != impact.controlled_object_id:
            findings.append(
                {
                    "type": SpecialistContradictionType.VERSION.value,
                    "material": True,
                    "status": "UNRESOLVED",
                    "source_result_ids": [str(value.id), str(impact.id)],
                    "description": (
                        f"{label} and impact results select different controlled objects"
                    ),
                    "downstream_invalidations": ["DISPOSITION", "CONSEQUENCE_PATH"],
                }
            )
    lineage_fields = {
        "PROGRESS": "progress_evaluation_id",
        "SCHEDULE": "schedule_assessment_id",
        "COST": "cost_assessment_id",
    }
    for forecast in forecasts:
        for label, field in lineage_fields.items():
            direct = selected[label]
            forecast_source_id = getattr(forecast, field)
            if direct and forecast_source_id and direct.id != forecast_source_id:
                findings.append(
                    {
                        "type": SpecialistContradictionType.VERSION.value,
                        "material": True,
                        "status": "UNRESOLVED",
                        "source_result_ids": [
                            str(direct.id),
                            str(forecast_source_id),
                            str(forecast.id),
                        ],
                        "description": f"Selected {label} result differs from forecast lineage",
                        "downstream_invalidations": ["FORECAST", "DISPOSITION"],
                    }
                )
    return findings


def create_contradiction_resolution(
    session: Session,
    actor: ActorContext,
    project: Project,
    case_id: uuid.UUID,
    run_id: uuid.UUID,
    data: ContradictionResolutionCreate,
) -> tuple[Any, SpecialistContradictionResolution]:
    case = scoped_case(session, project, case_id, for_update=True)
    require_version(case, data.expected_version)
    run = session.get(OrchestrationRun, run_id)
    if run is None or run.case_id != case.id:
        raise HTTPException(status_code=404, detail="Orchestration run not found")
    if data.contradiction_index >= len(run.contradiction_findings):
        raise HTTPException(status_code=422, detail="Contradiction index is outside this run")
    finding = run.contradiction_findings[data.contradiction_index]
    source_ids = set(finding["source_result_ids"])
    rejected_ids = set(data.rejected_result_ids)
    if data.selected_result_id not in source_ids:
        raise HTTPException(status_code=422, detail="Selected result is not a contradiction source")
    if not rejected_ids <= source_ids or data.selected_result_id in rejected_ids:
        raise HTTPException(
            status_code=422, detail="Rejected results must be other contradiction sources"
        )
    resolution = SpecialistContradictionResolution(
        id=uuid.uuid4(),
        organization_id=project.organization_id,
        project_id=project.id,
        case_id=case.id,
        snapshot_id=run.snapshot_id,
        orchestration_run_id=run.id,
        contradiction_index=data.contradiction_index,
        contradiction_type=finding["type"],
        source_result_ids=list(finding["source_result_ids"]),
        selected_result_id=data.selected_result_id,
        rejected_result_ids=data.rejected_result_ids,
        resolution_basis=data.resolution_basis,
        downstream_invalidations=list(finding["downstream_invalidations"]),
        resolved_by=actor.actor_id,
    )
    session.add(resolution)
    session.flush()
    case.version += 1
    add_ledger(
        session,
        actor,
        case,
        CaseLedgerEventType.SPECIALIST_CONTRADICTION_RESOLVED,
        "Specialist contradiction received an explicit reviewed resolution",
        details={
            "resolution_id": str(resolution.id),
            "run_id": str(run.id),
            "contradiction_index": data.contradiction_index,
            "selected_result_id": data.selected_result_id,
            "rejected_result_ids": data.rejected_result_ids,
        },
    )
    audit_case(
        session,
        actor,
        case,
        "SPECIALIST_CONTRADICTION_RESOLVED",
        {"resolution_id": str(resolution.id), "run_id": str(run.id)},
    )
    return case, resolution


def validate_narrative(run: OrchestrationRun, narrative: str) -> dict[str, Any]:
    violations: list[dict[str, str]] = []
    normalized = narrative.upper()
    disposition = str(run.recommended_disposition or "WITHHELD")
    mentioned = [value.value for value in Disposition if value.value in normalized]
    if mentioned and disposition not in mentioned:
        violations.append(
            {
                "code": "DISPOSITION_DRIFT",
                "description": "Narrative disposition differs from the structured recommendation",
            }
        )
    authority_claims = (
        "SYSTEM APPROVED",
        "AI APPROVED",
        "AUTOMATICALLY AUTHORIZED",
        "AUTHORIZED TO PROCEED",
        "DECISION HAS BEEN MADE",
    )
    for claim in authority_claims:
        if claim in normalized:
            violations.append(
                {
                    "code": "UNSUPPORTED_AUTHORITY_CLAIM",
                    "description": f"Narrative contains prohibited authority claim: {claim}",
                }
            )
    allowed_numbers = set(
        re.findall(r"(?<![A-Za-z])[-+]?\d+(?:\.\d+)?", json.dumps(run.case_brief))
    )
    narrative_numbers = set(re.findall(r"(?<![A-Za-z])[-+]?\d+(?:\.\d+)?", narrative))
    for number in sorted(narrative_numbers - allowed_numbers):
        violations.append(
            {
                "code": "UNSUPPORTED_NUMBER",
                "description": (
                    f"Narrative number {number} is absent from the structured case brief"
                ),
            }
        )
    return {
        "valid": not violations,
        "violations": violations,
        "run_id": run.id,
        "formula_version": NARRATIVE_VALIDATOR_VERSION,
    }


def create_orchestration_run(
    session: Session,
    actor: ActorContext,
    project: Project,
    case_id: uuid.UUID,
    data: OrchestrationCreate,
    idempotency_key: str,
) -> tuple[Any, OrchestrationRun, list[SpecialistRun]]:
    case = scoped_case(session, project, case_id, for_update=True)
    digest = request_digest(data)
    existing = session.scalar(
        select(OrchestrationRun).where(
            OrchestrationRun.case_id == case.id,
            OrchestrationRun.idempotency_key == idempotency_key,
        )
    )
    if existing:
        if existing.request_hash != digest:
            raise HTTPException(status_code=409, detail="Idempotency key payload mismatch")
        runs = list(
            session.scalars(
                select(SpecialistRun)
                .where(SpecialistRun.orchestration_run_id == existing.id)
                .order_by(SpecialistRun.specialist_kind)
            )
        )
        return case, existing, runs
    require_version(case, data.expected_version)
    if case.lifecycle == CaseLifecycle.CLOSED:
        raise HTTPException(status_code=409, detail="Closed case cannot be orchestrated")
    snapshot = session.get(CaseSnapshot, data.snapshot_id)
    if snapshot is None or snapshot.case_id != case.id:
        raise HTTPException(status_code=404, detail="Case snapshot not found")
    retry_of = None
    attempt = 1
    if data.retry_of_run_id:
        retry_of = session.get(OrchestrationRun, data.retry_of_run_id)
        if retry_of is None or retry_of.case_id != case.id:
            raise HTTPException(status_code=404, detail="Retried orchestration run not found")
        if retry_of.snapshot_id != snapshot.id:
            raise HTTPException(status_code=422, detail="Retry must reuse the original snapshot")
        if retry_of.status == OrchestrationStatus.SUCCEEDED:
            raise HTTPException(
                status_code=409, detail="Successful orchestration run cannot be retried"
            )
        attempt = (
            session.scalar(
                select(func.max(SpecialistRun.attempt)).where(
                    SpecialistRun.orchestration_run_id == retry_of.id
                )
            )
            or 1
        ) + 1

    progress = _input(
        session, ProgressEvaluation, data.progress_evaluation_id, case.id, snapshot.id, "Progress"
    )
    schedule = _input(
        session, ScheduleAssessment, data.schedule_assessment_id, case.id, snapshot.id, "Schedule"
    )
    cost = _input(session, CostAssessment, data.cost_assessment_id, case.id, snapshot.id, "Cost")
    impact = _input(
        session, ImpactAssessment, data.impact_assessment_id, case.id, snapshot.id, "Impact"
    )
    forecasts = [
        _input(session, ForecastProjection, identifier, case.id, snapshot.id, "Forecast")
        for identifier in data.forecast_projection_ids
    ]
    disposition, readiness = _disposition(impact)
    contradiction_findings = _contradictions(impact, progress, schedule, cost, forecasts)
    resolutions = (
        list(
            session.scalars(
                select(SpecialistContradictionResolution).where(
                    SpecialistContradictionResolution.id.in_(data.contradiction_resolution_ids)
                )
            )
        )
        if data.contradiction_resolution_ids
        else []
    )
    if len(resolutions) != len(set(data.contradiction_resolution_ids)):
        raise HTTPException(status_code=422, detail="Contradiction resolution not found")
    for resolution in resolutions:
        if resolution.case_id != case.id or resolution.snapshot_id != snapshot.id:
            raise HTTPException(status_code=422, detail="Resolution is outside this case snapshot")
        matches = [
            finding
            for finding in contradiction_findings
            if finding["type"] == resolution.contradiction_type
            and set(finding["source_result_ids"]) == set(resolution.source_result_ids)
        ]
        if not matches:
            raise HTTPException(
                status_code=422, detail="Resolution does not match a current contradiction"
            )
        for finding in matches:
            finding["status"] = "RESOLVED_REVALIDATION_REQUIRED"
            finding["resolution_id"] = str(resolution.id)
            finding["selected_result_id"] = resolution.selected_result_id
            finding["rejected_result_ids"] = list(resolution.rejected_result_ids)
            finding["resolution_basis"] = resolution.resolution_basis
    blockers = []
    if impact is None:
        blockers.append(
            {
                "code": "IMPACT_ASSESSMENT_REQUIRED",
                "description": "Disposition cannot exceed VERIFY without an impact assessment",
            }
        )
    elif impact.assessment_status == ImpactAssessmentStatus.VERIFICATION_REQUIRED:
        blockers.extend(impact.limitations)
    if case.readiness in {
        DecisionReadiness.INSUFFICIENT,
        DecisionReadiness.VERIFICATION_REQUIRED,
    }:
        blockers.append(
            {
                "code": "CASE_SUFFICIENCY_STOP",
                "readiness": str(case.readiness),
                "description": "Recorded case sufficiency does not support a stronger disposition",
            }
        )
        disposition = Disposition.VERIFY
        readiness = DecisionReadiness(str(case.readiness))
    if case.governance_state == GovernanceState.GOVERNANCE_BLOCKED:
        blockers.append(
            {
                "code": "CASE_GOVERNANCE_BLOCKED",
                "description": "Case governance state blocks recommendation publication",
            }
        )
        disposition = Disposition.VERIFY
        readiness = DecisionReadiness.VERIFICATION_REQUIRED
    if contradiction_findings:
        disposition = Disposition.VERIFY
        readiness = DecisionReadiness.VERIFICATION_REQUIRED
        blockers.extend(
            {
                "code": "UNRESOLVED_SPECIALIST_CONTRADICTION",
                "contradiction_type": finding["type"],
                "source_result_ids": finding["source_result_ids"],
                "description": finding["description"],
            }
            for finding in contradiction_findings
            if finding["material"] and finding["status"] == "UNRESOLVED"
        )
    limitations = list(impact.limitations) if impact else []
    selected_inputs = {
        "EVIDENCE_PROGRESS": progress,
        "SCHEDULE_DEPENDENCY": schedule,
        "COST_COMMERCIAL": cost,
        "FORECAST_SCENARIO": forecasts,
    }
    for specialist_kind, selected in selected_inputs.items():
        if not selected:
            limitations.append(
                {
                    "code": "SPECIALIST_INPUT_NOT_SELECTED",
                    "specialist_kind": specialist_kind,
                    "description": "Specialist did not run beyond its safe no-input boundary",
                }
            )
    if not blockers and limitations and readiness == DecisionReadiness.DECISION_READY:
        readiness = DecisionReadiness.DECISION_READY_WITH_LIMITATIONS
    status = (
        OrchestrationStatus.STOPPED
        if blockers
        else (OrchestrationStatus.LIMITED if limitations else OrchestrationStatus.SUCCEEDED)
    )
    number = (
        session.scalar(
            select(func.max(OrchestrationRun.run_number)).where(OrchestrationRun.case_id == case.id)
        )
        or 0
    ) + 1
    selection_reason = {
        Disposition.NO_ACTION: "No supported material consequence and no timed urgency",
        Disposition.MONITOR: "Condition is credible but does not support intervention",
        Disposition.VERIFY: "A decision-critical input is missing, restricted, or contradictory",
        Disposition.INTERVENE: "Supported material consequence requires management action",
        Disposition.ESCALATE: "Critical priority or immediate clock requires senior authority",
    }
    alternatives = [
        {
            "disposition": value.value,
            "selected": value == disposition,
            "reason_code": (
                "SELECTED_BY_DETERMINISTIC_RULE" if value == disposition else "NOT_SELECTED"
            ),
            "reason": selection_reason[value],
        }
        for value in Disposition
    ]
    authority_route = {
        Disposition.ESCALATE: "ESCALATION_REQUIRED",
        Disposition.INTERVENE: "APPROVAL_REQUIRED",
    }.get(disposition, "HUMAN_REVIEW_REQUIRED")
    brief = {
        "case_id": str(case.id),
        "snapshot_id": str(snapshot.id),
        "condition": impact.consequence_severity if impact else "UNASSESSED",
        "consequences": list(impact.consequence_paths) if impact else [],
        "confidence": str(impact.overall_confidence) if impact else "0",
        "clocks": list(impact.decision_clocks) if impact else [],
        "priority": impact.priority_band if impact else None,
        "recommended_disposition": disposition.value,
        "limitations": limitations,
        "blockers": blockers,
        "contradictions": contradiction_findings,
        "evidence_request": (
            {
                "required": True,
                "reason": "Resolve decision-critical blockers before a stronger disposition",
                "blocker_codes": [value["code"] for value in blockers],
            }
            if blockers
            else {"required": False}
        ),
        "monitoring_trigger": (
            {
                "required": True,
                "condition": "Reassess on new material evidence or changed consequence clock",
            }
            if disposition == Disposition.MONITOR
            else {"required": False}
        ),
        "authority_route": authority_route,
        "prohibited_autonomous_actions": [
            "RECORD_HUMAN_DECISION",
            "AUTHORIZE_RESPONSE",
            "CHANGE_BASELINE_OR_BUDGET",
            "COMMIT_SPEND_OR_CONTRACTUAL_POSITION",
        ],
    }
    run = OrchestrationRun(
        id=uuid.uuid4(),
        organization_id=project.organization_id,
        project_id=project.id,
        case_id=case.id,
        snapshot_id=snapshot.id,
        retry_of_run_id=retry_of.id if retry_of else None,
        run_number=number,
        status=status,
        readiness=readiness,
        recommended_disposition=disposition,
        alternative_dispositions=alternatives,
        blockers=blockers,
        limitations=limitations,
        contradiction_findings=contradiction_findings,
        case_brief=brief,
        policy_versions={"impact": impact.policy_version if impact else "UNSELECTED"},
        formula_version=FORMULA_VERSION,
        idempotency_key=idempotency_key,
        request_hash=digest,
        created_by=actor.actor_id,
        completed_at=datetime.now(UTC),
    )
    session.add(run)
    forecast_value = forecasts[-1] if forecasts else None
    specialist_runs = [
        _safe_specialist(
            run,
            SpecialistKind.EVIDENCE_PROGRESS,
            progress,
            output_key="progress_evaluation_id",
            questions=data.requested_questions,
            contradictions=contradiction_findings,
            attempt=attempt,
        ),
        _safe_specialist(
            run,
            SpecialistKind.SCHEDULE_DEPENDENCY,
            schedule,
            output_key="schedule_assessment_id",
            restricted={"INSUFFICIENT", "VERIFICATION_REQUIRED"},
            questions=data.requested_questions,
            contradictions=contradiction_findings,
            attempt=attempt,
        ),
        _safe_specialist(
            run,
            SpecialistKind.COST_COMMERCIAL,
            cost,
            output_key="cost_assessment_id",
            restricted={"INSUFFICIENT", "VERIFICATION_REQUIRED"},
            questions=data.requested_questions,
            contradictions=contradiction_findings,
            attempt=attempt,
        ),
        _safe_specialist(
            run,
            SpecialistKind.FORECAST_SCENARIO,
            forecast_value,
            output_key="forecast_projection_id",
            restricted={"LIMITED"},
            questions=data.requested_questions,
            contradictions=contradiction_findings,
            attempt=attempt,
        ),
        _safe_specialist(
            run,
            SpecialistKind.IMPACT_PRIORITY,
            impact,
            output_key="impact_assessment_id",
            restricted={"LIMITED", "VERIFICATION_REQUIRED"},
            questions=data.requested_questions,
            contradictions=contradiction_findings,
            attempt=attempt,
        ),
    ]
    failed_kinds = {
        value.specialist_kind
        for value in specialist_runs
        if value.status == SpecialistRunStatus.FAILED
    }
    if SpecialistKind.IMPACT_PRIORITY in failed_kinds:
        run.status = OrchestrationStatus.STOPPED
        run.readiness = DecisionReadiness.VERIFICATION_REQUIRED
        run.recommended_disposition = Disposition.VERIFY
        run.alternative_dispositions = [
            {
                **value,
                "selected": value["disposition"] == Disposition.VERIFY,
                "reason_code": (
                    "SELECTED_BY_FAILURE_STOP"
                    if value["disposition"] == Disposition.VERIFY
                    else "NOT_SELECTED"
                ),
            }
            for value in run.alternative_dispositions
        ]
        run.blockers = [
            *run.blockers,
            {
                "code": "CRITICAL_SPECIALIST_FAILED",
                "specialist_kind": SpecialistKind.IMPACT_PRIORITY.value,
                "description": "Impact specialist failed; stronger disposition is withheld",
            },
        ]
        run.case_brief = {
            **run.case_brief,
            "recommended_disposition": Disposition.VERIFY.value,
            "blockers": run.blockers,
        }
    elif failed_kinds:
        run.status = OrchestrationStatus.LIMITED
        run.readiness = DecisionReadiness.DECISION_READY_WITH_LIMITATIONS
        run.limitations = [
            *run.limitations,
            *[
                {
                    "code": "NONCRITICAL_SPECIALIST_FAILED",
                    "specialist_kind": str(kind),
                    "description": "Recommendation excludes the failed specialist output",
                }
                for kind in sorted(failed_kinds)
            ],
        ]
        run.case_brief = {**run.case_brief, "limitations": run.limitations}
    session.add_all(specialist_runs)
    case.last_orchestration_run_id = run.id
    case.version += 1
    add_ledger(
        session,
        actor,
        case,
        CaseLedgerEventType.ORCHESTRATION_RUN_STARTED,
        "Deterministic specialist orchestration started",
        details={"run_id": str(run.id)},
    )
    add_ledger(
        session,
        actor,
        case,
        CaseLedgerEventType.ORCHESTRATION_RUN_COMPLETED,
        "Deterministic specialist orchestration completed",
        details={
            "run_id": str(run.id),
            "status": status.value,
            "recommended_disposition": disposition.value,
        },
    )
    audit_case(
        session,
        actor,
        case,
        "ORCHESTRATION_RUN_COMPLETED",
        {"run_id": str(run.id), "status": status.value},
    )
    return case, run, specialist_runs
