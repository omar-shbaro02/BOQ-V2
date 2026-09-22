from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import ActorContext, get_actor
from app.bootstrap_schemas import (
    BoqNormalizationDetail,
    BoqNormalizationRead,
    BoqNormalizeCreate,
    BoqSourceCreate,
    BoqSourceDetail,
    BoqSourceRead,
    PlanningStructureCreate,
    PlanningStructureRead,
    PlanningStructureRevisionCreate,
    RevisionDeltaCreate,
    RevisionDeltaRead,
    ScheduleApprovalCreate,
    ScheduleCalculationCreate,
    ScheduleCalculationRead,
    ScheduleDraftGenerateCreate,
    ScheduleDraftGenerationDetail,
    ScheduleDraftGenerationRead,
    ScheduleLogicCreate,
    ScheduleLogicRead,
    ScheduleReleaseRead,
    ScheduleReviewCreate,
)
from app.database import get_db
from app.generated.taxonomies import ProjectRole
from app.models import (
    BootstrapRevisionDelta,
    BootstrapScheduleCalculation,
    BootstrapScheduleRelease,
    BoqLine,
    BoqNormalizationRun,
    BoqPlanningStructureVersion,
    BoqSourceRow,
    BoqSourceVersion,
    PlanningAssumption,
    ProposedScheduleActivity,
    ScheduleDraftGeneration,
    ScheduleLogicProposal,
)
from app.services.access import get_scoped_project, require_project_roles
from app.services.bootstrap import (
    create_boq_source,
    create_planning_structure,
    create_schedule_logic,
    generate_schedule_draft,
    normalize_boq_source,
    revise_planning_structure,
)
from app.services.bootstrap_schedule import (
    approve_schedule,
    calculate_schedule,
    create_revision_delta,
    export_release,
    review_schedule,
)
from app.services.evidence import scoped_artifact
from app.storage import EvidenceStore, get_evidence_store

router = APIRouter(prefix="/api/v1/projects/{project_id}/bootstrap", tags=["bootstrap"])
SessionDep = Annotated[Session, Depends(get_db)]
ActorDep = Annotated[ActorContext, Depends(get_actor)]
StoreDep = Annotated[EvidenceStore, Depends(get_evidence_store)]

READ_ROLES = set(ProjectRole)
WRITE_ROLES = {
    ProjectRole.ORGANIZATION_ADMIN,
    ProjectRole.PROJECT_ADMIN,
    ProjectRole.DATA_CONTRIBUTOR,
    ProjectRole.ANALYST_CONTROLLER,
}
APPROVAL_ROLES = {
    ProjectRole.ORGANIZATION_ADMIN,
    ProjectRole.PROJECT_ADMIN,
    ProjectRole.APPROVER_ESCALATION_AUTHORITY,
}


def _project(session: Session, actor: ActorContext, project_id: uuid.UUID, roles: set):
    project = get_scoped_project(session, actor, project_id)
    require_project_roles(session, actor, project, roles)
    return project


@router.post("/boq-sources", response_model=BoqSourceRead, status_code=201)
def add_boq_source(
    project_id: uuid.UUID,
    data: BoqSourceCreate,
    session: SessionDep,
    actor: ActorDep,
    store: StoreDep,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=200)],
) -> BoqSourceVersion:
    project = _project(session, actor, project_id, WRITE_ROLES)
    artifact = scoped_artifact(session, project, data.artifact_id)
    try:
        source = create_boq_source(session, actor, project, artifact, data, idempotency_key, store)
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="BOQ source version conflicts with existing data",
        ) from exc
    session.refresh(source)
    return source


@router.get("/boq-sources", response_model=list[BoqSourceRead])
def list_boq_sources(
    project_id: uuid.UUID, session: SessionDep, actor: ActorDep
) -> list[BoqSourceVersion]:
    project = _project(session, actor, project_id, READ_ROLES)
    return list(
        session.scalars(
            select(BoqSourceVersion)
            .where(BoqSourceVersion.project_id == project.id)
            .order_by(BoqSourceVersion.version_number.desc())
        )
    )


@router.get("/boq-sources/{source_id}", response_model=BoqSourceDetail)
def get_boq_source(
    project_id: uuid.UUID,
    source_id: uuid.UUID,
    session: SessionDep,
    actor: ActorDep,
) -> dict:
    project = _project(session, actor, project_id, READ_ROLES)
    source = session.get(BoqSourceVersion, source_id)
    if source is None or source.project_id != project.id:
        raise HTTPException(status_code=404, detail="BOQ source version not found")
    rows = list(
        session.scalars(
            select(BoqSourceRow)
            .where(BoqSourceRow.source_version_id == source.id)
            .order_by(BoqSourceRow.sequence_number)
        )
    )
    result = BoqSourceRead.model_validate(source).model_dump()
    result["rows"] = rows
    return result


@router.post(
    "/boq-sources/{source_id}/normalizations",
    response_model=BoqNormalizationRead,
    status_code=201,
)
def add_boq_normalization(
    project_id: uuid.UUID,
    source_id: uuid.UUID,
    data: BoqNormalizeCreate,
    session: SessionDep,
    actor: ActorDep,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=200)],
) -> BoqNormalizationRun:
    project = _project(session, actor, project_id, WRITE_ROLES)
    source = session.get(BoqSourceVersion, source_id)
    if source is None or source.project_id != project.id:
        raise HTTPException(status_code=404, detail="BOQ source version not found")
    try:
        run = normalize_boq_source(session, actor, project, source, data, idempotency_key)
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="BOQ normalization conflicts with existing data",
        ) from exc
    session.refresh(run)
    return run


@router.get(
    "/boq-sources/{source_id}/normalization",
    response_model=BoqNormalizationDetail,
)
def get_boq_normalization(
    project_id: uuid.UUID,
    source_id: uuid.UUID,
    session: SessionDep,
    actor: ActorDep,
) -> dict:
    project = _project(session, actor, project_id, READ_ROLES)
    source = session.get(BoqSourceVersion, source_id)
    if source is None or source.project_id != project.id:
        raise HTTPException(status_code=404, detail="BOQ source version not found")
    run = session.scalar(
        select(BoqNormalizationRun).where(BoqNormalizationRun.source_version_id == source.id)
    )
    if run is None:
        raise HTTPException(status_code=404, detail="BOQ normalization not found")
    lines = list(
        session.scalars(
            select(BoqLine)
            .join(BoqSourceRow, BoqSourceRow.id == BoqLine.source_row_id)
            .where(BoqLine.normalization_run_id == run.id)
            .order_by(BoqSourceRow.sequence_number)
        )
    )
    result = BoqNormalizationRead.model_validate(run).model_dump()
    result["lines"] = lines
    return result


@router.post(
    "/boq-sources/{source_id}/planning-structures",
    response_model=PlanningStructureRead,
    status_code=201,
)
def add_planning_structure(
    project_id: uuid.UUID,
    source_id: uuid.UUID,
    data: PlanningStructureCreate,
    session: SessionDep,
    actor: ActorDep,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=200)],
) -> BoqPlanningStructureVersion:
    project = _project(session, actor, project_id, WRITE_ROLES)
    normalization = session.scalar(
        select(BoqNormalizationRun).where(
            BoqNormalizationRun.source_version_id == source_id,
            BoqNormalizationRun.project_id == project.id,
        )
    )
    if normalization is None:
        raise HTTPException(status_code=422, detail="BOQ normalization is required")
    try:
        structure = create_planning_structure(
            session, actor, project, normalization, data, idempotency_key
        )
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="Planning structure conflicts") from exc
    session.refresh(structure)
    return structure


@router.get(
    "/boq-sources/{source_id}/planning-structures",
    response_model=list[PlanningStructureRead],
)
def list_planning_structures(
    project_id: uuid.UUID,
    source_id: uuid.UUID,
    session: SessionDep,
    actor: ActorDep,
) -> list[BoqPlanningStructureVersion]:
    project = _project(session, actor, project_id, READ_ROLES)
    normalization = session.scalar(
        select(BoqNormalizationRun.id).where(
            BoqNormalizationRun.source_version_id == source_id,
            BoqNormalizationRun.project_id == project.id,
        )
    )
    if normalization is None:
        raise HTTPException(status_code=404, detail="BOQ normalization not found")
    return list(
        session.scalars(
            select(BoqPlanningStructureVersion)
            .where(BoqPlanningStructureVersion.normalization_run_id == normalization)
            .order_by(BoqPlanningStructureVersion.version_number)
        )
    )


@router.post(
    "/planning-structures/{structure_id}/revisions",
    response_model=PlanningStructureRead,
    status_code=201,
)
def revise_structure(
    project_id: uuid.UUID,
    structure_id: uuid.UUID,
    data: PlanningStructureRevisionCreate,
    session: SessionDep,
    actor: ActorDep,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=200)],
) -> BoqPlanningStructureVersion:
    project = _project(session, actor, project_id, WRITE_ROLES)
    current = session.get(BoqPlanningStructureVersion, structure_id)
    if current is None or current.project_id != project.id:
        raise HTTPException(status_code=404, detail="Planning structure not found")
    try:
        revised = revise_planning_structure(session, actor, project, current, data, idempotency_key)
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=409, detail="Planning structure revision conflicts"
        ) from exc
    session.refresh(revised)
    return revised


@router.post(
    "/planning-structures/{structure_id}/schedule-drafts",
    response_model=ScheduleDraftGenerationRead,
    status_code=201,
)
def add_schedule_draft(
    project_id: uuid.UUID,
    structure_id: uuid.UUID,
    data: ScheduleDraftGenerateCreate,
    session: SessionDep,
    actor: ActorDep,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=200)],
) -> ScheduleDraftGeneration:
    project = _project(session, actor, project_id, WRITE_ROLES)
    structure = session.get(BoqPlanningStructureVersion, structure_id)
    if structure is None or structure.project_id != project.id:
        raise HTTPException(status_code=404, detail="Planning structure not found")
    try:
        generation = generate_schedule_draft(
            session, actor, project, structure, data, idempotency_key
        )
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="Schedule draft conflicts") from exc
    session.refresh(generation)
    return generation


@router.get(
    "/schedule-drafts/{generation_id}",
    response_model=ScheduleDraftGenerationDetail,
)
def get_schedule_draft(
    project_id: uuid.UUID,
    generation_id: uuid.UUID,
    session: SessionDep,
    actor: ActorDep,
) -> dict:
    project = _project(session, actor, project_id, READ_ROLES)
    generation = session.get(ScheduleDraftGeneration, generation_id)
    if generation is None or generation.project_id != project.id:
        raise HTTPException(status_code=404, detail="Schedule draft not found")
    activities = list(
        session.scalars(
            select(ProposedScheduleActivity)
            .where(ProposedScheduleActivity.generation_id == generation.id)
            .order_by(ProposedScheduleActivity.activity_code)
        )
    )
    assumptions = list(
        session.scalars(
            select(PlanningAssumption)
            .where(PlanningAssumption.generation_id == generation.id)
            .order_by(PlanningAssumption.created_at, PlanningAssumption.id)
        )
    )
    result = ScheduleDraftGenerationRead.model_validate(generation).model_dump()
    result["activities"] = activities
    result["assumptions"] = assumptions
    return result


@router.post(
    "/schedule-drafts/{generation_id}/logic",
    response_model=ScheduleLogicRead,
    status_code=201,
)
def add_schedule_logic(
    project_id: uuid.UUID,
    generation_id: uuid.UUID,
    data: ScheduleLogicCreate,
    session: SessionDep,
    actor: ActorDep,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=200)],
) -> ScheduleLogicProposal:
    project = _project(session, actor, project_id, WRITE_ROLES)
    generation = session.get(ScheduleDraftGeneration, generation_id)
    if generation is None or generation.project_id != project.id:
        raise HTTPException(status_code=404, detail="Schedule draft not found")
    try:
        proposal = create_schedule_logic(session, actor, project, generation, data, idempotency_key)
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="Schedule logic conflicts") from exc
    session.refresh(proposal)
    return proposal


@router.get(
    "/schedule-drafts/{generation_id}/logic",
    response_model=ScheduleLogicRead,
)
def get_schedule_logic(
    project_id: uuid.UUID,
    generation_id: uuid.UUID,
    session: SessionDep,
    actor: ActorDep,
) -> ScheduleLogicProposal:
    project = _project(session, actor, project_id, READ_ROLES)
    proposal = session.scalar(
        select(ScheduleLogicProposal).where(
            ScheduleLogicProposal.generation_id == generation_id,
            ScheduleLogicProposal.project_id == project.id,
        )
    )
    if proposal is None:
        raise HTTPException(status_code=404, detail="Schedule logic not found")
    return proposal


@router.post(
    "/schedule-drafts/{generation_id}/calculations",
    response_model=ScheduleCalculationRead,
    status_code=201,
)
def add_schedule_calculation(
    project_id: uuid.UUID,
    generation_id: uuid.UUID,
    data: ScheduleCalculationCreate,
    session: SessionDep,
    actor: ActorDep,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=200)],
) -> BootstrapScheduleCalculation:
    project = _project(session, actor, project_id, WRITE_ROLES)
    logic = session.scalar(
        select(ScheduleLogicProposal).where(
            ScheduleLogicProposal.generation_id == generation_id,
            ScheduleLogicProposal.project_id == project.id,
        )
    )
    if logic is None:
        raise HTTPException(status_code=422, detail="Schedule logic is required")
    try:
        calculation = calculate_schedule(session, actor, project, logic, data, idempotency_key)
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="Schedule calculation conflicts") from exc
    session.refresh(calculation)
    return calculation


@router.get(
    "/schedule-drafts/{generation_id}/calculation",
    response_model=ScheduleCalculationRead,
)
def get_schedule_calculation(
    project_id: uuid.UUID, generation_id: uuid.UUID, session: SessionDep, actor: ActorDep
) -> BootstrapScheduleCalculation:
    project = _project(session, actor, project_id, READ_ROLES)
    calculation = session.scalar(
        select(BootstrapScheduleCalculation).where(
            BootstrapScheduleCalculation.generation_id == generation_id,
            BootstrapScheduleCalculation.project_id == project.id,
        )
    )
    if calculation is None:
        raise HTTPException(status_code=404, detail="Schedule calculation not found")
    return calculation


@router.post(
    "/schedule-calculations/{calculation_id}/reviews",
    response_model=ScheduleReleaseRead,
    status_code=201,
)
def add_schedule_review(
    project_id: uuid.UUID,
    calculation_id: uuid.UUID,
    data: ScheduleReviewCreate,
    session: SessionDep,
    actor: ActorDep,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=200)],
) -> BootstrapScheduleRelease:
    project = _project(session, actor, project_id, WRITE_ROLES)
    calculation = session.get(BootstrapScheduleCalculation, calculation_id)
    if calculation is None or calculation.project_id != project.id:
        raise HTTPException(status_code=404, detail="Schedule calculation not found")
    try:
        release = review_schedule(session, actor, project, calculation, data, idempotency_key)
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="Schedule review conflicts") from exc
    session.refresh(release)
    return release


@router.post(
    "/schedule-releases/{release_id}/approve",
    response_model=ScheduleReleaseRead,
    status_code=201,
)
def approve_schedule_release(
    project_id: uuid.UUID,
    release_id: uuid.UUID,
    data: ScheduleApprovalCreate,
    session: SessionDep,
    actor: ActorDep,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=200)],
) -> BootstrapScheduleRelease:
    project = _project(session, actor, project_id, APPROVAL_ROLES)
    release = session.get(BootstrapScheduleRelease, release_id)
    if release is None or release.project_id != project.id:
        raise HTTPException(status_code=404, detail="Schedule release not found")
    try:
        approved = approve_schedule(session, actor, project, release, data, idempotency_key)
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="Schedule approval conflicts") from exc
    session.refresh(approved)
    return approved


@router.get("/schedule-releases", response_model=list[ScheduleReleaseRead])
def list_schedule_releases(
    project_id: uuid.UUID, session: SessionDep, actor: ActorDep
) -> list[BootstrapScheduleRelease]:
    project = _project(session, actor, project_id, READ_ROLES)
    return list(
        session.scalars(
            select(BootstrapScheduleRelease)
            .where(BootstrapScheduleRelease.project_id == project.id)
            .order_by(BootstrapScheduleRelease.created_at)
        )
    )


@router.get("/schedule-releases/{release_id}/export/{export_format}")
def download_schedule_release(
    project_id: uuid.UUID,
    release_id: uuid.UUID,
    export_format: str,
    session: SessionDep,
    actor: ActorDep,
) -> Response:
    project = _project(session, actor, project_id, READ_ROLES)
    release = session.get(BootstrapScheduleRelease, release_id)
    if release is None or release.project_id != project.id:
        raise HTTPException(status_code=404, detail="Schedule release not found")
    normalized_format = export_format.upper()
    if normalized_format not in {"JSON", "CSV", "XLSX"}:
        raise HTTPException(status_code=422, detail="Export format must be JSON, CSV, or XLSX")
    content, media_type, filename = export_release(release, normalized_format)
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post(
    "/boq-sources/{source_id}/revision-delta", response_model=RevisionDeltaRead, status_code=201
)
def add_revision_delta(
    project_id: uuid.UUID,
    source_id: uuid.UUID,
    data: RevisionDeltaCreate,
    session: SessionDep,
    actor: ActorDep,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=200)],
) -> BootstrapRevisionDelta:
    project = _project(session, actor, project_id, WRITE_ROLES)
    source = session.get(BoqSourceVersion, source_id)
    if source is None or source.project_id != project.id:
        raise HTTPException(status_code=404, detail="BOQ source version not found")
    try:
        delta = create_revision_delta(session, actor, project, source, data, idempotency_key)
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="BOQ revision delta conflicts") from exc
    session.refresh(delta)
    return delta


@router.get("/boq-sources/{source_id}/revision-delta", response_model=RevisionDeltaRead)
def get_revision_delta(
    project_id: uuid.UUID,
    source_id: uuid.UUID,
    session: SessionDep,
    actor: ActorDep,
) -> BootstrapRevisionDelta:
    project = _project(session, actor, project_id, READ_ROLES)
    delta = session.scalar(
        select(BootstrapRevisionDelta).where(
            BootstrapRevisionDelta.new_source_version_id == source_id,
            BootstrapRevisionDelta.project_id == project.id,
        )
    )
    if delta is None:
        raise HTTPException(status_code=404, detail="BOQ revision delta not found")
    return delta
