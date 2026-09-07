from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import ActorContext, get_actor
from app.database import get_db
from app.generated.taxonomies import MaterialityBand, ProjectRole, SignalStatus, SignalType
from app.models import (
    OutboxEvent,
    Signal,
    SignalCorrelationSuggestion,
    SignalScreeningDecision,
)
from app.services.access import get_scoped_project, require_project_roles
from app.services.signals import (
    detect_signals,
    expire_due_signals,
    review_correlation,
    scoped_signal,
    screen_signal,
    suggest_correlation,
)
from app.signal_schemas import (
    CorrelationReviewCreate,
    CorrelationReviewResult,
    CorrelationSuggestionRead,
    ExpireSignalsRead,
    OutboxEventRead,
    ScreeningDecisionRead,
    SignalDetectionCreate,
    SignalDetectionResult,
    SignalRead,
    SignalScreenCreate,
    SignalScreenResult,
)

router = APIRouter(prefix="/api/v1/projects/{project_id}", tags=["signals"])
SessionDep = Annotated[Session, Depends(get_db)]
ActorDep = Annotated[ActorContext, Depends(get_actor)]

READ_ROLES = set(ProjectRole)
DETECT_ROLES = {
    ProjectRole.ORGANIZATION_ADMIN,
    ProjectRole.PROJECT_ADMIN,
    ProjectRole.DATA_CONTRIBUTOR,
    ProjectRole.VERIFIER,
    ProjectRole.ANALYST_CONTROLLER,
}
REVIEW_ROLES = {
    ProjectRole.ORGANIZATION_ADMIN,
    ProjectRole.PROJECT_ADMIN,
    ProjectRole.ANALYST_CONTROLLER,
    ProjectRole.DECISION_OWNER,
}


def project_with_role(session: Session, actor: ActorContext, project_id: uuid.UUID, roles: set):
    project = get_scoped_project(session, actor, project_id)
    require_project_roles(session, actor, project, roles)
    return project


def commit_or_conflict(session: Session, detail: str) -> None:
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from exc


@router.post("/signals/detect", response_model=SignalDetectionResult, status_code=201)
def detect(
    project_id: uuid.UUID,
    data: SignalDetectionCreate,
    session: SessionDep,
    actor: ActorDep,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=200)],
) -> SignalDetectionResult:
    project = project_with_role(session, actor, project_id, DETECT_ROLES)
    run, signals = detect_signals(session, actor, project, data, idempotency_key)
    commit_or_conflict(session, "Signal detection conflicts with an existing run")
    session.refresh(run)
    for signal in signals:
        session.refresh(signal)
    return SignalDetectionResult(run=run, signals=signals)


@router.get("/signals", response_model=list[SignalRead])
def list_signals(
    project_id: uuid.UUID,
    session: SessionDep,
    actor: ActorDep,
    signal_status: SignalStatus | None = None,
    signal_type: SignalType | None = None,
    materiality: MaterialityBand | None = None,
    controlled_object_id: uuid.UUID | None = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[Signal]:
    project = project_with_role(session, actor, project_id, READ_ROLES)
    query = select(Signal).where(Signal.project_id == project.id)
    if signal_status:
        query = query.where(Signal.status == signal_status)
    if signal_type:
        query = query.where(Signal.signal_type == signal_type)
    if materiality:
        query = query.where(Signal.materiality_candidate == materiality)
    if controlled_object_id:
        query = query.where(Signal.controlled_object_id == controlled_object_id)
    return list(
        session.scalars(
            query.order_by(Signal.created_at.desc(), Signal.id).offset(offset).limit(limit)
        )
    )


@router.get("/signals/{signal_id}", response_model=SignalRead)
def get_signal(
    project_id: uuid.UUID, signal_id: uuid.UUID, session: SessionDep, actor: ActorDep
) -> Signal:
    project = project_with_role(session, actor, project_id, READ_ROLES)
    return scoped_signal(session, project, signal_id)


@router.post("/signals/{signal_id}/screen", response_model=SignalScreenResult)
def screen(
    project_id: uuid.UUID,
    signal_id: uuid.UUID,
    data: SignalScreenCreate,
    session: SessionDep,
    actor: ActorDep,
) -> SignalScreenResult:
    project = project_with_role(session, actor, project_id, REVIEW_ROLES)
    signal, decision = screen_signal(session, actor, project, signal_id, data)
    commit_or_conflict(session, "Signal screening conflicts with current workflow state")
    session.refresh(signal)
    session.refresh(decision)
    return SignalScreenResult(signal=signal, decision=decision)


@router.get("/signals/{signal_id}/screenings", response_model=list[ScreeningDecisionRead])
def screening_history(
    project_id: uuid.UUID, signal_id: uuid.UUID, session: SessionDep, actor: ActorDep
) -> list[SignalScreeningDecision]:
    project = project_with_role(session, actor, project_id, READ_ROLES)
    signal = scoped_signal(session, project, signal_id)
    return list(
        session.scalars(
            select(SignalScreeningDecision)
            .where(SignalScreeningDecision.signal_id == signal.id)
            .order_by(SignalScreeningDecision.decided_at)
        )
    )


@router.post("/signals/expire-due", response_model=ExpireSignalsRead)
def expire(project_id: uuid.UUID, session: SessionDep, actor: ActorDep) -> ExpireSignalsRead:
    project = project_with_role(session, actor, project_id, REVIEW_ROLES)
    expired = expire_due_signals(session, actor, project)
    commit_or_conflict(session, "Signal expiration conflict")
    return ExpireSignalsRead(expired_signal_ids=expired)


@router.post(
    "/signals/{signal_id}/correlation-suggestion",
    response_model=CorrelationSuggestionRead,
    status_code=201,
)
def suggest(
    project_id: uuid.UUID, signal_id: uuid.UUID, session: SessionDep, actor: ActorDep
) -> SignalCorrelationSuggestion:
    project = project_with_role(session, actor, project_id, REVIEW_ROLES)
    suggestion = suggest_correlation(session, actor, project, signal_id)
    commit_or_conflict(session, "Correlation suggestion already exists")
    session.refresh(suggestion)
    return suggestion


@router.post(
    "/correlation-suggestions/{suggestion_id}/review",
    response_model=CorrelationReviewResult,
)
def review(
    project_id: uuid.UUID,
    suggestion_id: uuid.UUID,
    data: CorrelationReviewCreate,
    session: SessionDep,
    actor: ActorDep,
) -> CorrelationReviewResult:
    project = project_with_role(session, actor, project_id, REVIEW_ROLES)
    signal, correlation_review, case = review_correlation(
        session, actor, project, suggestion_id, data
    )
    commit_or_conflict(session, "Correlation review conflicts with current workflow state")
    session.refresh(signal)
    session.refresh(correlation_review)
    if case:
        session.refresh(case)
    return CorrelationReviewResult(signal=signal, review=correlation_review, case=case)


@router.get("/outbox-events", response_model=list[OutboxEventRead])
def list_outbox_events(
    project_id: uuid.UUID,
    session: SessionDep,
    actor: ActorDep,
    event_type: str | None = None,
) -> list[OutboxEvent]:
    project = project_with_role(session, actor, project_id, READ_ROLES)
    query = select(OutboxEvent).where(OutboxEvent.project_id == project.id)
    if event_type:
        query = query.where(OutboxEvent.event_type == event_type)
    return list(session.scalars(query.order_by(OutboxEvent.occurred_at)))
