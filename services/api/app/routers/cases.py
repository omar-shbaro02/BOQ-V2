from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import ActorContext, get_actor
from app.case_schemas import (
    ActiveResponseCreate,
    ActiveResponseResult,
    AttachEvidenceCreate,
    AttachEvidenceResult,
    BaselineAssessmentCreate,
    BaselineAssessmentResult,
    CaseBlockCreate,
    CaseCloseCreate,
    CaseLedgerEventRead,
    CaseReopenCreate,
    CaseResumeCreate,
    DecisionCaseRead,
    EvidenceAssemblyRead,
    LifecycleTransitionCreate,
    LimitationResolveCreate,
    LimitationResolveResult,
    SnapshotCreate,
    SnapshotResult,
    SufficiencyAssessCreate,
    SufficiencyAssessmentResult,
    SufficiencyPolicyRead,
)
from app.database import get_db
from app.generated.taxonomies import (
    CaseLifecycle,
    CaseReopenTrigger,
    DecisionReadiness,
    ProjectRole,
)
from app.models import (
    CaseActiveResponse,
    CaseEvidenceAttachment,
    CaseLedgerEvent,
    CaseLimitation,
    CaseSnapshot,
    CaseSufficiencyAssessment,
    DecisionCaseShell,
    EvidenceItem,
    EvidenceRequest,
)
from app.services.access import get_scoped_project, require_project_roles
from app.services.cases import (
    assess_baseline,
    assess_sufficiency,
    attach_evidence,
    block_case,
    close_case,
    create_snapshot,
    policy_projection,
    record_active_response,
    reopen_case,
    resolve_limitation,
    resume_case,
    scoped_case,
    transition_case,
)

router = APIRouter(prefix="/api/v1/projects/{project_id}", tags=["decision-cases"])
SessionDep = Annotated[Session, Depends(get_db)]
ActorDep = Annotated[ActorContext, Depends(get_actor)]

READ_ROLES = set(ProjectRole)
ASSEMBLY_ROLES = {
    ProjectRole.ORGANIZATION_ADMIN,
    ProjectRole.PROJECT_ADMIN,
    ProjectRole.DATA_CONTRIBUTOR,
    ProjectRole.VERIFIER,
    ProjectRole.ANALYST_CONTROLLER,
}
MANAGE_ROLES = {
    ProjectRole.ORGANIZATION_ADMIN,
    ProjectRole.PROJECT_ADMIN,
    ProjectRole.ANALYST_CONTROLLER,
    ProjectRole.DECISION_OWNER,
}
AUTHORITY_ROLES = {
    ProjectRole.ORGANIZATION_ADMIN,
    ProjectRole.PROJECT_ADMIN,
    ProjectRole.DECISION_OWNER,
    ProjectRole.APPROVER_ESCALATION_AUTHORITY,
}
ADMIN_ROLES = {ProjectRole.ORGANIZATION_ADMIN, ProjectRole.PROJECT_ADMIN}


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


@router.get("/decision-cases/policies/sufficiency", response_model=list[SufficiencyPolicyRead])
def get_sufficiency_policies(
    project_id: uuid.UUID, session: SessionDep, actor: ActorDep
) -> list[dict]:
    project_with_role(session, actor, project_id, READ_ROLES)
    return policy_projection()


@router.get("/decision-cases", response_model=list[DecisionCaseRead])
def list_cases(
    project_id: uuid.UUID,
    session: SessionDep,
    actor: ActorDep,
    lifecycle: CaseLifecycle | None = None,
    readiness: DecisionReadiness | None = None,
    owner_actor_id: str | None = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[DecisionCaseShell]:
    project = project_with_role(session, actor, project_id, READ_ROLES)
    query = select(DecisionCaseShell).where(DecisionCaseShell.project_id == project.id)
    if lifecycle:
        query = query.where(DecisionCaseShell.lifecycle == lifecycle)
    if readiness:
        query = query.where(DecisionCaseShell.readiness == readiness)
    if owner_actor_id:
        query = query.where(DecisionCaseShell.owner_actor_id == owner_actor_id)
    return list(
        session.scalars(
            query.order_by(DecisionCaseShell.opened_at.desc()).offset(offset).limit(limit)
        )
    )


@router.get("/decision-cases/{case_id}", response_model=DecisionCaseRead)
def get_case(
    project_id: uuid.UUID, case_id: uuid.UUID, session: SessionDep, actor: ActorDep
) -> DecisionCaseShell:
    project = project_with_role(session, actor, project_id, READ_ROLES)
    return scoped_case(session, project, case_id)


@router.post("/decision-cases/{case_id}/evidence", response_model=AttachEvidenceResult)
def add_case_evidence(
    project_id: uuid.UUID,
    case_id: uuid.UUID,
    data: AttachEvidenceCreate,
    session: SessionDep,
    actor: ActorDep,
) -> AttachEvidenceResult:
    project = project_with_role(session, actor, project_id, ASSEMBLY_ROLES)
    case, attached = attach_evidence(session, actor, project, case_id, data)
    commit_or_conflict(session, "Case evidence attachment conflict")
    session.refresh(case)
    return AttachEvidenceResult(case=case, attached_evidence_item_ids=attached)


@router.post("/decision-cases/{case_id}/active-responses", response_model=ActiveResponseResult)
def add_active_response(
    project_id: uuid.UUID,
    case_id: uuid.UUID,
    data: ActiveResponseCreate,
    session: SessionDep,
    actor: ActorDep,
) -> ActiveResponseResult:
    project = project_with_role(session, actor, project_id, AUTHORITY_ROLES)
    case, response = record_active_response(session, actor, project, case_id, data)
    commit_or_conflict(session, "Active response reference conflict")
    session.refresh(case)
    session.refresh(response)
    return ActiveResponseResult(case=case, response=response)


@router.post("/decision-cases/{case_id}/snapshots", response_model=SnapshotResult, status_code=201)
def snapshot_case(
    project_id: uuid.UUID,
    case_id: uuid.UUID,
    data: SnapshotCreate,
    session: SessionDep,
    actor: ActorDep,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=200)],
) -> SnapshotResult:
    project = project_with_role(session, actor, project_id, ASSEMBLY_ROLES)
    case, snapshot = create_snapshot(session, actor, project, case_id, data, idempotency_key)
    commit_or_conflict(session, "Case snapshot idempotency conflict")
    session.refresh(case)
    session.refresh(snapshot)
    return SnapshotResult(case=case, snapshot=snapshot)


@router.post(
    "/decision-cases/{case_id}/baseline-assessments",
    response_model=BaselineAssessmentResult,
    status_code=201,
)
def add_baseline_assessment(
    project_id: uuid.UUID,
    case_id: uuid.UUID,
    data: BaselineAssessmentCreate,
    session: SessionDep,
    actor: ActorDep,
) -> BaselineAssessmentResult:
    project = project_with_role(session, actor, project_id, MANAGE_ROLES)
    case, assessment = assess_baseline(session, actor, project, case_id, data)
    commit_or_conflict(session, "Baseline assessment conflict")
    session.refresh(case)
    session.refresh(assessment)
    return BaselineAssessmentResult(case=case, assessment=assessment)


@router.post(
    "/decision-cases/{case_id}/sufficiency-assessments",
    response_model=SufficiencyAssessmentResult,
    status_code=201,
)
def add_sufficiency_assessment(
    project_id: uuid.UUID,
    case_id: uuid.UUID,
    data: SufficiencyAssessCreate,
    session: SessionDep,
    actor: ActorDep,
) -> SufficiencyAssessmentResult:
    project = project_with_role(session, actor, project_id, MANAGE_ROLES)
    case, assessment, limitations, requests = assess_sufficiency(
        session, actor, project, case_id, data
    )
    commit_or_conflict(session, "Sufficiency assessment conflict")
    session.refresh(case)
    session.refresh(assessment)
    for value in [*limitations, *requests]:
        session.refresh(value)
    return SufficiencyAssessmentResult(
        case=case,
        assessment=assessment,
        limitations=limitations,
        evidence_requests=requests,
    )


@router.post(
    "/decision-cases/{case_id}/limitations/{limitation_id}/resolve",
    response_model=LimitationResolveResult,
)
def resolve_case_limitation(
    project_id: uuid.UUID,
    case_id: uuid.UUID,
    limitation_id: uuid.UUID,
    data: LimitationResolveCreate,
    session: SessionDep,
    actor: ActorDep,
) -> LimitationResolveResult:
    project = project_with_role(session, actor, project_id, MANAGE_ROLES)
    case, limitation = resolve_limitation(
        session, actor, project, case_id, limitation_id, data.expected_version, data.resolution
    )
    commit_or_conflict(session, "Limitation resolution conflict")
    session.refresh(case)
    session.refresh(limitation)
    return LimitationResolveResult(case=case, limitation=limitation)


@router.post("/decision-cases/{case_id}/transition", response_model=DecisionCaseRead)
def transition(
    project_id: uuid.UUID,
    case_id: uuid.UUID,
    data: LifecycleTransitionCreate,
    session: SessionDep,
    actor: ActorDep,
) -> DecisionCaseShell:
    project = project_with_role(session, actor, project_id, MANAGE_ROLES)
    case = transition_case(session, actor, project, case_id, data)
    commit_or_conflict(session, "Case transition conflict")
    session.refresh(case)
    return case


@router.post("/decision-cases/{case_id}/block", response_model=DecisionCaseRead)
def block(
    project_id: uuid.UUID,
    case_id: uuid.UUID,
    data: CaseBlockCreate,
    session: SessionDep,
    actor: ActorDep,
) -> DecisionCaseShell:
    project = project_with_role(session, actor, project_id, MANAGE_ROLES)
    case = block_case(session, actor, project, case_id, data)
    commit_or_conflict(session, "Case block conflict")
    session.refresh(case)
    return case


@router.post("/decision-cases/{case_id}/resume", response_model=DecisionCaseRead)
def resume(
    project_id: uuid.UUID,
    case_id: uuid.UUID,
    data: CaseResumeCreate,
    session: SessionDep,
    actor: ActorDep,
) -> DecisionCaseShell:
    project = project_with_role(session, actor, project_id, MANAGE_ROLES)
    case = resume_case(session, actor, project, case_id, data)
    commit_or_conflict(session, "Case resume conflict")
    session.refresh(case)
    return case


@router.post("/decision-cases/{case_id}/close", response_model=DecisionCaseRead)
def close(
    project_id: uuid.UUID,
    case_id: uuid.UUID,
    data: CaseCloseCreate,
    session: SessionDep,
    actor: ActorDep,
) -> DecisionCaseShell:
    project = project_with_role(
        session,
        actor,
        project_id,
        AUTHORITY_ROLES if data.outcome_reference else ADMIN_ROLES,
    )
    case = close_case(session, actor, project, case_id, data)
    commit_or_conflict(session, "Case closure conflict")
    session.refresh(case)
    return case


@router.post("/decision-cases/{case_id}/reopen", response_model=DecisionCaseRead)
def reopen(
    project_id: uuid.UUID,
    case_id: uuid.UUID,
    data: CaseReopenCreate,
    session: SessionDep,
    actor: ActorDep,
) -> DecisionCaseShell:
    roles = (
        ADMIN_ROLES
        if data.trigger == CaseReopenTrigger.ADMINISTRATIVE_CORRECTION
        else AUTHORITY_ROLES
    )
    project = project_with_role(session, actor, project_id, roles)
    case = reopen_case(session, actor, project, case_id, data)
    commit_or_conflict(session, "Case reopen conflict")
    session.refresh(case)
    return case


@router.get("/decision-cases/{case_id}/ledger", response_model=list[CaseLedgerEventRead])
def get_case_ledger(
    project_id: uuid.UUID, case_id: uuid.UUID, session: SessionDep, actor: ActorDep
) -> list[CaseLedgerEvent]:
    project = project_with_role(session, actor, project_id, READ_ROLES)
    case = scoped_case(session, project, case_id)
    return list(
        session.scalars(
            select(CaseLedgerEvent)
            .where(CaseLedgerEvent.case_id == case.id)
            .order_by(CaseLedgerEvent.case_version, CaseLedgerEvent.occurred_at)
        )
    )


@router.get("/decision-cases/{case_id}/evidence-assembly", response_model=EvidenceAssemblyRead)
def get_evidence_assembly(
    project_id: uuid.UUID, case_id: uuid.UUID, session: SessionDep, actor: ActorDep
) -> EvidenceAssemblyRead:
    project = project_with_role(session, actor, project_id, READ_ROLES)
    case = scoped_case(session, project, case_id)
    assessments = list(
        session.scalars(
            select(CaseSufficiencyAssessment)
            .where(CaseSufficiencyAssessment.case_id == case.id)
            .order_by(CaseSufficiencyAssessment.assessed_at)
        )
    )
    request_ids = {
        uuid.UUID(value) for assessment in assessments for value in assessment.evidence_request_ids
    }
    evidence = list(
        session.scalars(
            select(EvidenceItem)
            .join(
                CaseEvidenceAttachment,
                CaseEvidenceAttachment.evidence_item_id == EvidenceItem.id,
            )
            .where(CaseEvidenceAttachment.case_id == case.id)
            .order_by(EvidenceItem.created_at)
        )
    )
    return EvidenceAssemblyRead(
        case=case,
        evidence=evidence,
        requests=list(
            session.scalars(
                select(EvidenceRequest)
                .where(EvidenceRequest.id.in_(request_ids))
                .order_by(EvidenceRequest.created_at)
            )
        ),
        active_responses=list(
            session.scalars(
                select(CaseActiveResponse)
                .where(CaseActiveResponse.case_id == case.id)
                .order_by(CaseActiveResponse.recorded_at)
            )
        ),
        limitations=list(
            session.scalars(
                select(CaseLimitation)
                .where(CaseLimitation.case_id == case.id)
                .order_by(CaseLimitation.created_at)
            )
        ),
        snapshots=list(
            session.scalars(
                select(CaseSnapshot)
                .where(CaseSnapshot.case_id == case.id)
                .order_by(CaseSnapshot.snapshot_number)
            )
        ),
        assessments=assessments,
        ledger=list(
            session.scalars(
                select(CaseLedgerEvent)
                .where(CaseLedgerEvent.case_id == case.id)
                .order_by(CaseLedgerEvent.case_version, CaseLedgerEvent.occurred_at)
            )
        ),
    )
