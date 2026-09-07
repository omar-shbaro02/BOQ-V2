from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from app.auth import ActorContext
from app.generated.taxonomies import (
    CaseLedgerEventType,
    CaseLifecycle,
    ContradictionStatus,
    CorrelationOutcome,
    CorrelationReviewStatus,
    EvidenceItemStatus,
    MaterialityBand,
    ScreeningOutcome,
    SignalStatus,
    SignalType,
)
from app.models import (
    CaseLedgerEvent,
    Contradiction,
    DecisionCaseControlledObject,
    DecisionCaseShell,
    DecisionCaseSignal,
    EvidenceItem,
    Project,
    Signal,
    SignalCorrelationReview,
    SignalCorrelationSuggestion,
    SignalDetectionRun,
    SignalEvidence,
    SignalScreeningDecision,
)
from app.services.audit import record_audit
from app.services.events import publish_domain_event
from app.signal_schemas import CorrelationReviewCreate, SignalDetectionCreate, SignalScreenCreate
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

DETECTOR_VERSION = "1.0.0"
PROGRESS_FIELDS = {"progress_variance", "progress_variance_pct", "progress_variance_ratio"}
SCHEDULE_FIELDS = {"schedule_variance_days", "delay_days"}
COST_FIELDS = {"cost_variance_pct", "cost_variance_ratio", "cost_overrun_pct"}
MILESTONE_FIELDS = {"milestone_days_to_impact", "days_to_milestone", "milestone_exposed"}


def utc_value(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def as_decimal(value: Any) -> Decimal | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def scoped_signal(
    session: Session,
    project: Project,
    signal_id: uuid.UUID,
    *,
    for_update: bool = False,
) -> Signal:
    query = select(Signal).where(Signal.id == signal_id)
    if for_update:
        query = query.with_for_update()
    signal = session.scalar(query)
    if signal is None or signal.project_id != project.id:
        raise HTTPException(status_code=404, detail="Signal not found")
    return signal


def request_digest(data: SignalDetectionCreate) -> str:
    payload = {
        "evidence_item_ids": sorted(str(value) for value in data.evidence_item_ids),
        "contradiction_ids": sorted(str(value) for value in data.contradiction_ids),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def fingerprint(parts: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(parts, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def classify_evidence(item: EvidenceItem) -> dict[str, Any] | None:
    numeric = as_decimal(item.value)
    field = item.field_name.lower()
    if field in PROGRESS_FIELDS and numeric is not None and abs(numeric) >= Decimal("0.10"):
        magnitude = abs(numeric)
        return {
            "signal_type": SignalType.PROGRESS_VARIANCE,
            "title": f"Material progress variance on {item.field_name}",
            "summary": f"Progress variance {numeric} crossed the 0.10 ratio threshold.",
            "materiality": (
                MaterialityBand.HIGH if magnitude >= Decimal("0.20") else MaterialityBand.MEDIUM
            ),
            "details": {"threshold": "0.10", "comparison": "ABS_GTE", "unit": "ratio"},
            "expiry_days": 14,
        }
    if field in SCHEDULE_FIELDS and numeric is not None and numeric >= Decimal("5"):
        return {
            "signal_type": SignalType.SCHEDULE_VARIANCE,
            "title": f"Schedule delay candidate on {item.field_name}",
            "summary": f"Schedule delay {numeric} days crossed the 5-day threshold.",
            "materiality": MaterialityBand.HIGH if numeric >= 15 else MaterialityBand.MEDIUM,
            "details": {"threshold": "5", "comparison": "GTE", "unit": "days"},
            "expiry_days": 14,
        }
    if field in COST_FIELDS and numeric is not None and numeric >= Decimal("0.05"):
        return {
            "signal_type": SignalType.COST_VARIANCE,
            "title": f"Cost variance candidate on {item.field_name}",
            "summary": f"Cost variance {numeric} crossed the 0.05 ratio threshold.",
            "materiality": (
                MaterialityBand.HIGH if numeric >= Decimal("0.10") else MaterialityBand.MEDIUM
            ),
            "details": {"threshold": "0.05", "comparison": "GTE", "unit": "ratio"},
            "expiry_days": 14,
        }
    milestone_triggered = field in MILESTONE_FIELDS and (
        item.value is True or (numeric is not None and Decimal("0") <= numeric <= Decimal("14"))
    )
    if milestone_triggered:
        return {
            "signal_type": SignalType.MILESTONE_EXPOSURE,
            "title": f"Milestone exposure candidate on {item.field_name}",
            "summary": "Milestone exposure entered the configured 14-day review window.",
            "materiality": MaterialityBand.HIGH,
            "details": {"threshold": "14", "comparison": "LTE", "unit": "days_or_boolean"},
            "expiry_days": 7,
        }
    return None


def upsert_candidate(
    session: Session,
    actor: ActorContext,
    project: Project,
    *,
    item: EvidenceItem | None,
    contradiction: Contradiction | None,
    candidate: dict[str, Any],
) -> Signal:
    observed_at = utc_value(item.as_of) if item else utc_value(contradiction.created_at)
    controlled_object_id = item.controlled_object_id if item else contradiction.controlled_object_id
    source_field = item.field_name if item else contradiction.field_name
    observed_value = (
        item.value
        if item
        else {
            "left_item_id": str(contradiction.left_item_id),
            "right_item_id": str(contradiction.right_item_id),
            "material": contradiction.material,
        }
    )
    identity = fingerprint(
        {
            "project_id": str(project.id),
            "signal_type": candidate["signal_type"],
            "controlled_object_id": str(controlled_object_id),
            "source_field": source_field,
            "observed_value": observed_value,
            "as_of": observed_at.isoformat(),
        }
    )
    signal = session.scalar(
        select(Signal).where(Signal.project_id == project.id, Signal.fingerprint == identity)
    )
    is_new = signal is None
    if signal is None:
        signal = Signal(
            id=uuid.uuid4(),
            organization_id=project.organization_id,
            project_id=project.id,
            controlled_object_id=controlled_object_id,
            signal_type=candidate["signal_type"],
            status=SignalStatus.CANDIDATE,
            title=candidate["title"],
            summary=candidate["summary"],
            source_field=source_field,
            source_evidence_ids=[str(item.id)] if item else [],
            source_contradiction_id=contradiction.id if contradiction else None,
            observed_value=observed_value,
            detector_details=candidate["details"],
            materiality_candidate=candidate["materiality"],
            fingerprint=identity,
            occurrence_count=1,
            detector_name="VAI_DETERMINISTIC_SIGNAL_DETECTORS",
            detector_version=DETECTOR_VERSION,
            first_observed_at=observed_at,
            last_observed_at=observed_at,
            expires_at=observed_at + timedelta(days=candidate["expiry_days"]),
            workflow_version=1,
            created_by=actor.actor_id,
        )
        session.add(signal)
        session.flush()
        record_audit(
            session,
            actor,
            organization_id=project.organization_id,
            project_id=project.id,
            action="SIGNAL_RAISED",
            object_type="SIGNAL",
            object_id=str(signal.id),
            details={"signal_type": signal.signal_type, "fingerprint": identity},
        )
        publish_domain_event(
            session,
            actor,
            project,
            event_type="SignalRaised",
            aggregate_type="SIGNAL",
            aggregate_id=signal.id,
            aggregate_version=signal.workflow_version,
            payload={"signal_type": signal.signal_type, "status": signal.status},
        )
    if item is not None:
        link = session.get(SignalEvidence, (signal.id, item.id))
        if link is None:
            session.add(SignalEvidence(signal_id=signal.id, evidence_item_id=item.id))
            if not is_new:
                signal.source_evidence_ids = [*signal.source_evidence_ids, str(item.id)]
                signal.occurrence_count += 1
                signal.last_observed_at = max(utc_value(signal.last_observed_at), observed_at)
    return signal


def detect_signals(
    session: Session,
    actor: ActorContext,
    project: Project,
    data: SignalDetectionCreate,
    idempotency_key: str,
) -> tuple[SignalDetectionRun, list[Signal]]:
    digest = request_digest(data)
    existing = session.scalar(
        select(SignalDetectionRun).where(
            SignalDetectionRun.project_id == project.id,
            SignalDetectionRun.idempotency_key == idempotency_key,
        )
    )
    if existing:
        if existing.request_hash != digest:
            raise HTTPException(status_code=409, detail="Idempotency key payload mismatch")
        ids = [uuid.UUID(value) for value in existing.signal_ids]
        return existing, list(session.scalars(select(Signal).where(Signal.id.in_(ids))))

    evidence_query = select(EvidenceItem).where(
        EvidenceItem.project_id == project.id,
        EvidenceItem.status == EvidenceItemStatus.ACTIVE,
    )
    if data.evidence_item_ids:
        evidence_query = evidence_query.where(EvidenceItem.id.in_(data.evidence_item_ids))
    contradiction_query = select(Contradiction).where(
        Contradiction.project_id == project.id,
        Contradiction.status == ContradictionStatus.OPEN,
    )
    if data.contradiction_ids:
        contradiction_query = contradiction_query.where(
            Contradiction.id.in_(data.contradiction_ids)
        )

    signals: dict[uuid.UUID, Signal] = {}
    for item in session.scalars(evidence_query):
        candidate = classify_evidence(item)
        if candidate:
            signal = upsert_candidate(
                session, actor, project, item=item, contradiction=None, candidate=candidate
            )
            signals[signal.id] = signal
    for contradiction in session.scalars(contradiction_query):
        candidate = {
            "signal_type": SignalType.EVIDENCE_CONFLICT,
            "title": f"Unresolved evidence conflict on {contradiction.field_name}",
            "summary": "Conflicting assertions require relevance and materiality screening.",
            "materiality": MaterialityBand.HIGH if contradiction.material else MaterialityBand.LOW,
            "details": {
                "contradiction_id": str(contradiction.id),
                "material": contradiction.material,
            },
            "expiry_days": 7,
        }
        signal = upsert_candidate(
            session,
            actor,
            project,
            item=None,
            contradiction=contradiction,
            candidate=candidate,
        )
        signals[signal.id] = signal

    run = SignalDetectionRun(
        id=uuid.uuid4(),
        organization_id=project.organization_id,
        project_id=project.id,
        idempotency_key=idempotency_key,
        request_hash=digest,
        detector_version=DETECTOR_VERSION,
        signal_ids=[str(signal_id) for signal_id in signals],
        created_by=actor.actor_id,
    )
    session.add(run)
    return run, list(signals.values())


def screen_signal(
    session: Session,
    actor: ActorContext,
    project: Project,
    signal_id: uuid.UUID,
    data: SignalScreenCreate,
) -> tuple[Signal, SignalScreeningDecision]:
    signal = scoped_signal(session, project, signal_id, for_update=True)
    if signal.workflow_version != data.expected_version:
        raise HTTPException(status_code=409, detail="Signal version is stale")
    if signal.status in {SignalStatus.CORRELATED, SignalStatus.EXPIRED}:
        raise HTTPException(
            status_code=409, detail="Signal cannot be screened in its current state"
        )
    now = datetime.now(UTC)
    if data.defer_until and data.defer_until <= now:
        raise HTTPException(status_code=422, detail="defer_until must be in the future")
    decision = SignalScreeningDecision(
        id=uuid.uuid4(),
        organization_id=project.organization_id,
        project_id=project.id,
        signal_id=signal.id,
        signal_version=signal.workflow_version,
        outcome=data.outcome,
        reason_code=data.reason_code,
        rationale=data.rationale,
        materiality_candidate=data.materiality_candidate,
        defer_until=data.defer_until,
        decided_by=actor.actor_id,
    )
    session.add(decision)
    signal.materiality_candidate = data.materiality_candidate
    signal.deferred_until = data.defer_until
    signal.status = {
        ScreeningOutcome.RELEVANT: SignalStatus.SCREENED,
        ScreeningOutcome.DEFER: SignalStatus.DEFERRED,
        ScreeningOutcome.DISMISS: SignalStatus.DISMISSED,
    }[data.outcome]
    signal.workflow_version += 1
    record_audit(
        session,
        actor,
        organization_id=project.organization_id,
        project_id=project.id,
        action="SIGNAL_SCREENED",
        object_type="SIGNAL",
        object_id=str(signal.id),
        object_version=signal.workflow_version,
        details={"outcome": data.outcome, "reason_code": data.reason_code},
    )
    publish_domain_event(
        session,
        actor,
        project,
        event_type="SignalScreened",
        aggregate_type="SIGNAL",
        aggregate_id=signal.id,
        aggregate_version=signal.workflow_version,
        payload={"outcome": data.outcome, "status": signal.status},
    )
    return signal, decision


def expire_due_signals(session: Session, actor: ActorContext, project: Project) -> list[uuid.UUID]:
    now = datetime.now(UTC)
    query = (
        select(Signal)
        .where(
            Signal.project_id == project.id,
            Signal.status.in_(
                [SignalStatus.CANDIDATE, SignalStatus.SCREENED, SignalStatus.DEFERRED]
            ),
            Signal.expires_at <= now,
        )
        .with_for_update()
    )
    expired: list[uuid.UUID] = []
    for signal in session.scalars(query):
        signal.status = SignalStatus.EXPIRED
        signal.workflow_version += 1
        expired.append(signal.id)
        record_audit(
            session,
            actor,
            organization_id=project.organization_id,
            project_id=project.id,
            action="SIGNAL_EXPIRED",
            object_type="SIGNAL",
            object_id=str(signal.id),
            object_version=signal.workflow_version,
        )
    return expired


def suggest_correlation(
    session: Session,
    actor: ActorContext,
    project: Project,
    signal_id: uuid.UUID,
) -> SignalCorrelationSuggestion:
    signal = scoped_signal(session, project, signal_id)
    if signal.status != SignalStatus.SCREENED:
        raise HTTPException(status_code=409, detail="Only relevant screened signals can correlate")
    existing = session.scalar(
        select(SignalCorrelationSuggestion).where(
            SignalCorrelationSuggestion.signal_id == signal.id,
            SignalCorrelationSuggestion.signal_version == signal.workflow_version,
        )
    )
    if existing:
        return existing
    cases: list[DecisionCaseShell] = []
    if signal.controlled_object_id:
        cases = list(
            session.scalars(
                select(DecisionCaseShell)
                .join(
                    DecisionCaseControlledObject,
                    DecisionCaseControlledObject.case_id == DecisionCaseShell.id,
                )
                .where(
                    DecisionCaseShell.project_id == project.id,
                    DecisionCaseControlledObject.controlled_object_id
                    == signal.controlled_object_id,
                    DecisionCaseShell.lifecycle != CaseLifecycle.CLOSED,
                )
            )
        )
    if not cases:
        outcome, target, children, confidence, rationale = (
            CorrelationOutcome.OPEN_NEW,
            None,
            [],
            Decimal("0.7000"),
            "No open case shares the signal's controlled object.",
        )
    elif len(cases) == 1:
        outcome, target, children, confidence, rationale = (
            CorrelationOutcome.LINK_EXISTING,
            cases[0].id,
            [],
            Decimal("0.8500"),
            "One open case shares the signal's controlled object.",
        )
    else:
        outcome, target, children, confidence, rationale = (
            CorrelationOutcome.CROSS_CUTTING_PARENT_CHILD,
            None,
            [str(case.id) for case in cases],
            Decimal("0.7500"),
            "Multiple independent open cases share the controlled object; human review "
            "must decide whether a cross-cutting parent is justified.",
        )
    suggestion = SignalCorrelationSuggestion(
        id=uuid.uuid4(),
        organization_id=project.organization_id,
        project_id=project.id,
        signal_id=signal.id,
        signal_version=signal.workflow_version,
        suggested_outcome=outcome,
        target_case_id=target,
        child_case_ids=children,
        confidence=confidence,
        rationale=rationale,
        status=CorrelationReviewStatus.PENDING,
        created_by=actor.actor_id,
    )
    session.add(suggestion)
    return suggestion


def scoped_case(session: Session, project: Project, case_id: uuid.UUID) -> DecisionCaseShell:
    case = session.get(DecisionCaseShell, case_id)
    if case is None or case.project_id != project.id:
        raise HTTPException(status_code=404, detail="Decision case not found")
    return case


def open_case_shell(
    session: Session,
    actor: ActorContext,
    project: Project,
    signal: Signal,
    *,
    title: str,
    owner: str,
    parent_case_id: uuid.UUID | None = None,
) -> DecisionCaseShell:
    case_id = uuid.uuid4()
    case = DecisionCaseShell(
        id=case_id,
        organization_id=project.organization_id,
        project_id=project.id,
        case_number=f"DC-{case_id.hex[:10].upper()}",
        title=title,
        case_type=signal.signal_type,
        lifecycle=CaseLifecycle.OPEN,
        owner_actor_id=owner,
        parent_case_id=parent_case_id,
        version=1,
        created_by=actor.actor_id,
    )
    session.add(case)
    session.flush()
    session.add(
        CaseLedgerEvent(
            id=uuid.uuid4(),
            organization_id=project.organization_id,
            project_id=project.id,
            case_id=case.id,
            case_version=case.version,
            event_type=CaseLedgerEventType.CASE_OPENED,
            from_lifecycle=None,
            to_lifecycle=CaseLifecycle.OPEN,
            actor_id=actor.actor_id,
            reason="Correlation review opened a Decision Case",
            details={"source_signal_id": str(signal.id)},
        )
    )
    if signal.controlled_object_id:
        session.add(
            DecisionCaseControlledObject(
                case_id=case.id, controlled_object_id=signal.controlled_object_id
            )
        )
    return case


def link_signal(
    session: Session,
    actor: ActorContext,
    case: DecisionCaseShell,
    signal: Signal,
    rationale: str,
) -> None:
    existing = session.get(DecisionCaseSignal, (case.id, signal.id))
    if existing is None:
        session.add(
            DecisionCaseSignal(
                case_id=case.id,
                signal_id=signal.id,
                correlation_rationale=rationale,
                linked_by=actor.actor_id,
            )
        )


def review_correlation(
    session: Session,
    actor: ActorContext,
    project: Project,
    suggestion_id: uuid.UUID,
    data: CorrelationReviewCreate,
) -> tuple[Signal, SignalCorrelationReview, DecisionCaseShell | None]:
    suggestion = session.scalar(
        select(SignalCorrelationSuggestion)
        .where(SignalCorrelationSuggestion.id == suggestion_id)
        .with_for_update()
    )
    if suggestion is None or suggestion.project_id != project.id:
        raise HTTPException(status_code=404, detail="Correlation suggestion not found")
    if suggestion.status != CorrelationReviewStatus.PENDING:
        raise HTTPException(status_code=409, detail="Correlation suggestion already reviewed")
    signal = scoped_signal(session, project, suggestion.signal_id, for_update=True)
    if signal.workflow_version != data.expected_signal_version:
        raise HTTPException(status_code=409, detail="Signal version is stale")

    case: DecisionCaseShell | None = None
    if data.status == CorrelationReviewStatus.ACCEPTED:
        outcome = data.selected_outcome
        if outcome == CorrelationOutcome.LINK_EXISTING:
            case = scoped_case(session, project, data.target_case_id)
            link_signal(session, actor, case, signal, data.rationale)
            signal.status = SignalStatus.CORRELATED
        elif outcome in {
            CorrelationOutcome.OPEN_NEW,
            CorrelationOutcome.CROSS_CUTTING_PARENT_CHILD,
        }:
            children = [scoped_case(session, project, case_id) for case_id in data.child_case_ids]
            case = open_case_shell(
                session,
                actor,
                project,
                signal,
                title=data.case_title,
                owner=data.case_owner_actor_id,
            )
            link_signal(session, actor, case, signal, data.rationale)
            for child in children:
                child.parent_case_id = case.id
                child.version += 1
            signal.status = SignalStatus.CORRELATED
        elif outcome == CorrelationOutcome.DEFER:
            signal.status = SignalStatus.DEFERRED
            signal.deferred_until = data.defer_until
        elif outcome == CorrelationOutcome.DISMISS:
            signal.status = SignalStatus.DISMISSED
        else:
            raise HTTPException(status_code=422, detail="Unsupported correlation outcome")
        signal.workflow_version += 1
    suggestion.status = data.status
    review = SignalCorrelationReview(
        id=uuid.uuid4(),
        organization_id=project.organization_id,
        project_id=project.id,
        suggestion_id=suggestion.id,
        selected_outcome=data.selected_outcome,
        target_case_id=data.target_case_id,
        created_case_id=case.id if case else None,
        child_case_ids=[str(value) for value in data.child_case_ids],
        rationale=data.rationale,
        status=data.status,
        reviewed_by=actor.actor_id,
    )
    session.add(review)
    action = (
        "SIGNAL_CORRELATION_ACCEPTED"
        if data.status == CorrelationReviewStatus.ACCEPTED
        else "SIGNAL_CORRELATION_REJECTED"
    )
    record_audit(
        session,
        actor,
        organization_id=project.organization_id,
        project_id=project.id,
        action=action,
        object_type="SIGNAL_CORRELATION",
        object_id=str(review.id),
        details={"signal_id": str(signal.id), "outcome": data.selected_outcome},
    )
    if case:
        publish_domain_event(
            session,
            actor,
            project,
            event_type="CaseOpened",
            aggregate_type="DECISION_CASE",
            aggregate_id=case.id,
            aggregate_version=case.version,
            payload={"case_number": case.case_number, "signal_id": str(signal.id)},
        )
        publish_domain_event(
            session,
            actor,
            project,
            event_type="SignalLinked",
            aggregate_type="SIGNAL",
            aggregate_id=signal.id,
            aggregate_version=signal.workflow_version,
            payload={"case_id": str(case.id)},
        )
    return signal, review, case
