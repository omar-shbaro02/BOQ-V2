from __future__ import annotations

import io
import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.assistant_schemas import SnapshotAnswer, SnapshotQuestion
from app.auth import ActorContext, get_actor
from app.database import get_db
from app.generated.taxonomies import ProgressBasis, ProgressMeasurementKind, ProjectRole
from app.models import (
    ProgressEvaluation,
    ProgressMeasurement,
    ProgressThresholdPolicy,
    ProgressWorkbookImport,
    ProjectControlSnapshot,
)
from app.progress_schemas import (
    ProgressEvaluationCreate,
    ProgressEvaluationRead,
    ProgressEvaluationResult,
    ProgressMeasurementCreate,
    ProgressMeasurementRead,
    ProgressPolicyCreate,
    ProgressPolicyRead,
    ProjectControlSnapshotCreate,
    ProjectControlSnapshotRead,
)
from app.services.access import get_scoped_project, require_project_roles
from app.services.governed_workbook import ingest_workbook
from app.services.progress import (
    create_policy,
    evaluate_progress,
    list_policies,
    record_measurement,
)
from app.services.progress_template import build_progress_template
from app.services.project_control import create_project_control_snapshot
from app.services.snapshot_assistant import answer_question
from app.storage import EvidenceStore, get_evidence_store
from app.workbook_schemas import ProgressWorkbookCreate, ProgressWorkbookRead

router = APIRouter(prefix="/api/v1/projects/{project_id}", tags=["progress"])
SessionDep = Annotated[Session, Depends(get_db)]
ActorDep = Annotated[ActorContext, Depends(get_actor)]

READ_ROLES = set(ProjectRole)
MEASUREMENT_ROLES = {
    ProjectRole.ORGANIZATION_ADMIN,
    ProjectRole.PROJECT_ADMIN,
    ProjectRole.DATA_CONTRIBUTOR,
    ProjectRole.VERIFIER,
    ProjectRole.ANALYST_CONTROLLER,
}
ANALYSIS_ROLES = {
    ProjectRole.ORGANIZATION_ADMIN,
    ProjectRole.PROJECT_ADMIN,
    ProjectRole.ANALYST_CONTROLLER,
    ProjectRole.DECISION_OWNER,
}
POLICY_ROLES = {ProjectRole.ORGANIZATION_ADMIN, ProjectRole.PROJECT_ADMIN}


@router.post("/progress/template")
def download_progress_template(
    project_id: uuid.UUID,
    session: SessionDep,
    actor: ActorDep,
    schedule: Annotated[UploadFile, File()],
    as_of: Annotated[date, Form()],
    sample: Annotated[bool, Form()] = False,
) -> StreamingResponse:
    scoped_project(session, actor, project_id, READ_ROLES)
    if not schedule.filename or not schedule.filename.lower().endswith(".xlsx"):
        raise HTTPException(422, "Upload an XLSX schedule workbook")
    content = schedule.file.read(20 * 1024 * 1024 + 1)
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(413, "Schedule workbook must be 20 MB or smaller")
    try:
        output = build_progress_template(
            content, project_id=str(project_id), as_of=as_of, sample=sample
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    filename = "fictional-progress-example.xlsx" if sample else "project-progress-template.xlsx"
    return StreamingResponse(
        io.BytesIO(output),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )


@router.post("/progress/workbook-imports", response_model=ProgressWorkbookRead, status_code=201)
def add_workbook_import(
    project_id: uuid.UUID,
    data: ProgressWorkbookCreate,
    session: SessionDep,
    actor: ActorDep,
    store: Annotated[EvidenceStore, Depends(get_evidence_store)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=200)],
) -> ProgressWorkbookImport:
    project = scoped_project(session, actor, project_id, MEASUREMENT_ROLES)
    record = ingest_workbook(session, actor, project, data, idempotency_key, store)
    commit_or_conflict(session, "Progress workbook import conflict")
    return record


@router.get("/progress/workbook-imports", response_model=list[ProgressWorkbookRead])
def get_workbook_imports(
    project_id: uuid.UUID, session: SessionDep, actor: ActorDep
) -> list[ProgressWorkbookImport]:
    project = scoped_project(session, actor, project_id, READ_ROLES)
    return list(
        session.scalars(
            select(ProgressWorkbookImport)
            .where(ProgressWorkbookImport.project_id == project.id)
            .order_by(ProgressWorkbookImport.recorded_at.desc())
        )
    )


@router.get("/progress/workbook-imports/{import_id}", response_model=ProgressWorkbookRead)
def read_workbook_import(
    project_id: uuid.UUID, import_id: uuid.UUID, session: SessionDep, actor: ActorDep
) -> ProgressWorkbookImport:
    project = scoped_project(session, actor, project_id, READ_ROLES)
    record = session.get(ProgressWorkbookImport, import_id)
    if record is None or record.project_id != project.id:
        raise HTTPException(404, "Progress workbook import not found")
    return record


def scoped_project(session: Session, actor: ActorContext, project_id: uuid.UUID, roles: set):
    project = get_scoped_project(session, actor, project_id)
    require_project_roles(session, actor, project, roles)
    return project


def commit_or_conflict(session: Session, detail: str) -> None:
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from exc


@router.get("/progress/policies", response_model=list[ProgressPolicyRead])
def get_progress_policies(
    project_id: uuid.UUID, session: SessionDep, actor: ActorDep
) -> list[dict | ProgressThresholdPolicy]:
    project = scoped_project(session, actor, project_id, READ_ROLES)
    return list_policies(session, project)


@router.post("/progress/policies", response_model=ProgressPolicyRead, status_code=201)
def add_progress_policy(
    project_id: uuid.UUID,
    data: ProgressPolicyCreate,
    session: SessionDep,
    actor: ActorDep,
) -> ProgressThresholdPolicy:
    project = scoped_project(session, actor, project_id, POLICY_ROLES)
    policy = create_policy(session, actor, project, data)
    commit_or_conflict(session, "Progress policy version conflict")
    session.refresh(policy)
    return policy


@router.get("/progress/measurements", response_model=list[ProgressMeasurementRead])
def get_progress_measurements(
    project_id: uuid.UUID,
    session: SessionDep,
    actor: ActorDep,
    controlled_object_id: uuid.UUID | None = None,
    measurement_kind: ProgressMeasurementKind | None = None,
    measurement_basis: ProgressBasis | None = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[ProgressMeasurement]:
    project = scoped_project(session, actor, project_id, READ_ROLES)
    query = select(ProgressMeasurement).where(ProgressMeasurement.project_id == project.id)
    if controlled_object_id:
        query = query.where(ProgressMeasurement.controlled_object_id == controlled_object_id)
    if measurement_kind:
        query = query.where(ProgressMeasurement.measurement_kind == measurement_kind)
    if measurement_basis:
        query = query.where(ProgressMeasurement.measurement_basis == measurement_basis)
    return list(
        session.scalars(
            query.order_by(ProgressMeasurement.as_of.desc()).offset(offset).limit(limit)
        )
    )


@router.post("/progress/measurements", response_model=ProgressMeasurementRead, status_code=201)
def add_progress_measurement(
    project_id: uuid.UUID,
    data: ProgressMeasurementCreate,
    session: SessionDep,
    actor: ActorDep,
) -> ProgressMeasurement:
    project = scoped_project(session, actor, project_id, MEASUREMENT_ROLES)
    measurement = record_measurement(session, actor, project, data)
    commit_or_conflict(session, "Progress measurement normalization conflict")
    session.refresh(measurement)
    return measurement


@router.get("/project-control/snapshots", response_model=list[ProjectControlSnapshotRead])
def get_project_control_snapshots(
    project_id: uuid.UUID,
    session: SessionDep,
    actor: ActorDep,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[ProjectControlSnapshot]:
    project = scoped_project(session, actor, project_id, READ_ROLES)
    return list(
        session.scalars(
            select(ProjectControlSnapshot)
            .where(ProjectControlSnapshot.project_id == project.id)
            .order_by(ProjectControlSnapshot.snapshot_number.desc())
            .offset(offset)
            .limit(limit)
        )
    )


@router.get("/project-control/snapshots/{snapshot_id}", response_model=ProjectControlSnapshotRead)
def get_project_control_snapshot(
    project_id: uuid.UUID,
    snapshot_id: uuid.UUID,
    session: SessionDep,
    actor: ActorDep,
) -> ProjectControlSnapshot:
    project = scoped_project(session, actor, project_id, READ_ROLES)
    snapshot = session.get(ProjectControlSnapshot, snapshot_id)
    if snapshot is None or snapshot.project_id != project.id:
        raise HTTPException(status_code=404, detail="Project control snapshot not found")
    return snapshot


@router.post(
    "/project-control/snapshots", response_model=ProjectControlSnapshotRead, status_code=201
)
def add_project_control_snapshot(
    project_id: uuid.UUID,
    data: ProjectControlSnapshotCreate,
    session: SessionDep,
    actor: ActorDep,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=200)],
) -> ProjectControlSnapshot:
    project = scoped_project(session, actor, project_id, ANALYSIS_ROLES)
    if data.health_policy:
        require_project_roles(session, actor, project, POLICY_ROLES)
    snapshot = create_project_control_snapshot(session, actor, project, data, idempotency_key)
    commit_or_conflict(session, "Project control snapshot idempotency conflict")
    session.refresh(snapshot)
    return snapshot


@router.post("/project-control/snapshots/{snapshot_id}/assistant", response_model=SnapshotAnswer)
def query_snapshot_assistant(
    project_id: uuid.UUID,
    snapshot_id: uuid.UUID,
    data: SnapshotQuestion,
    session: SessionDep,
    actor: ActorDep,
) -> dict:
    snapshot = get_project_control_snapshot(project_id, snapshot_id, session, actor)
    return answer_question(snapshot, data)


@router.get(
    "/decision-cases/{case_id}/progress-evaluations",
    response_model=list[ProgressEvaluationRead],
)
def get_progress_evaluations(
    project_id: uuid.UUID,
    case_id: uuid.UUID,
    session: SessionDep,
    actor: ActorDep,
) -> list[ProgressEvaluation]:
    project = scoped_project(session, actor, project_id, READ_ROLES)
    return list(
        session.scalars(
            select(ProgressEvaluation)
            .where(
                ProgressEvaluation.project_id == project.id,
                ProgressEvaluation.case_id == case_id,
            )
            .order_by(ProgressEvaluation.evaluation_number)
        )
    )


@router.post(
    "/decision-cases/{case_id}/progress-evaluations",
    response_model=ProgressEvaluationResult,
    status_code=201,
)
def add_progress_evaluation(
    project_id: uuid.UUID,
    case_id: uuid.UUID,
    data: ProgressEvaluationCreate,
    session: SessionDep,
    actor: ActorDep,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=200)],
) -> ProgressEvaluationResult:
    project = scoped_project(session, actor, project_id, ANALYSIS_ROLES)
    case, evaluation = evaluate_progress(session, actor, project, case_id, data, idempotency_key)
    commit_or_conflict(session, "Progress evaluation idempotency conflict")
    session.refresh(case)
    session.refresh(evaluation)
    return ProgressEvaluationResult(case=case, evaluation=evaluation)
