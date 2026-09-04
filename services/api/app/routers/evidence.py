from __future__ import annotations

import hashlib
import uuid
from datetime import datetime
from pathlib import Path
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Response,
    UploadFile,
    status,
)
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import ActorContext, get_actor
from app.config import get_settings
from app.database import get_db
from app.evidence_schemas import (
    ArtifactRead,
    ContradictionCreate,
    ContradictionRead,
    ContradictionResolve,
    EvidenceItemCreate,
    EvidenceItemRead,
    EvidenceRelationCreate,
    EvidenceRelationRead,
    EvidenceRequestCreate,
    EvidenceRequestRead,
    EvidenceRequestSatisfy,
    ImportBatchRead,
    ImportCommitRead,
    ImportPreviewCreate,
    ReliabilityCreate,
    ReliabilityRead,
    VerificationCreate,
    VerificationRead,
)
from app.generated.taxonomies import DataClassification, ProjectRole
from app.models import (
    Contradiction,
    EvidenceArtifact,
    EvidenceItem,
    EvidenceRelation,
    EvidenceRequest,
    ImportBatch,
    SourceReliabilityAssessment,
    VerificationEvent,
)
from app.security_scan import EvidenceScanner, get_evidence_scanner, validate_evidence_type
from app.services.access import get_scoped_project, require_project_roles
from app.services.audit import record_audit
from app.services.evidence import (
    assess_reliability,
    commit_import,
    create_contradiction,
    create_evidence_item,
    create_evidence_request,
    create_relation,
    preview_import,
    resolve_contradiction,
    satisfy_evidence_request,
    scoped_artifact,
    verify_item,
)
from app.storage import EvidenceStore, get_evidence_store

router = APIRouter(prefix="/api/v1/projects/{project_id}/evidence", tags=["evidence"])
SessionDep = Annotated[Session, Depends(get_db)]
ActorDep = Annotated[ActorContext, Depends(get_actor)]
StoreDep = Annotated[EvidenceStore, Depends(get_evidence_store)]
ScannerDep = Annotated[EvidenceScanner, Depends(get_evidence_scanner)]

READ_ROLES = set(ProjectRole)
WRITE_ROLES = {
    ProjectRole.ORGANIZATION_ADMIN,
    ProjectRole.PROJECT_ADMIN,
    ProjectRole.DATA_CONTRIBUTOR,
    ProjectRole.ANALYST_CONTROLLER,
    ProjectRole.VERIFIER,
}
VERIFY_ROLES = {
    ProjectRole.ORGANIZATION_ADMIN,
    ProjectRole.PROJECT_ADMIN,
    ProjectRole.VERIFIER,
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


@router.post("/artifacts", response_model=ArtifactRead, status_code=201)
async def upload_artifact(
    project_id: uuid.UUID,
    session: SessionDep,
    actor: ActorDep,
    store: StoreDep,
    scanner: ScannerDep,
    upload: Annotated[UploadFile, File()],
    source_type: Annotated[str, Form(min_length=1, max_length=80)],
    source_id: Annotated[str, Form(min_length=1, max_length=200)],
    classification: Annotated[DataClassification, Form()] = DataClassification.INTERNAL,
    captured_at: Annotated[datetime | None, Form()] = None,
    observed_at: Annotated[datetime | None, Form()] = None,
    parser_version: Annotated[str | None, Form(max_length=80)] = None,
    supersedes_artifact_id: Annotated[uuid.UUID | None, Form()] = None,
) -> EvidenceArtifact:
    project = project_with_role(session, actor, project_id, WRITE_ROLES)
    for timestamp in (captured_at, observed_at):
        if timestamp is not None and timestamp.tzinfo is None:
            raise HTTPException(status_code=422, detail="Evidence timestamps must include timezone")
    if supersedes_artifact_id:
        scoped_artifact(session, project, supersedes_artifact_id)

    content = await upload.read(get_settings().max_upload_bytes + 1)
    if not content:
        raise HTTPException(status_code=422, detail="Evidence artifact cannot be empty")
    if len(content) > get_settings().max_upload_bytes:
        raise HTTPException(status_code=413, detail="Evidence artifact exceeds upload limit")

    artifact_id = uuid.uuid4()
    digest = hashlib.sha256(content).hexdigest()
    filename = Path(upload.filename or "evidence.bin").name
    validate_evidence_type(filename, content)
    scan = scanner.scan(filename, content)
    suffix = Path(filename).suffix.lower()[:16]
    storage_key = f"{project.organization_id}/{project.id}/{artifact_id}/{digest}{suffix}"
    store.put(storage_key, content)
    artifact = EvidenceArtifact(
        id=artifact_id,
        organization_id=project.organization_id,
        project_id=project.id,
        storage_key=storage_key,
        original_filename=filename,
        media_type=upload.content_type or "application/octet-stream",
        size_bytes=len(content),
        sha256=digest,
        source_type=source_type,
        source_id=source_id,
        provided_by_actor=actor.actor_id,
        captured_at=captured_at,
        observed_at=observed_at,
        classification=classification,
        parser_version=parser_version,
        scan_result=scan.result,
        scan_engine=scan.engine,
        scan_signature_version=scan.signature_version,
        scanned_at=scan.scanned_at,
        supersedes_artifact_id=supersedes_artifact_id,
    )
    session.add(artifact)
    record_audit(
        session,
        actor,
        organization_id=project.organization_id,
        project_id=project.id,
        action="EVIDENCE_ARTIFACT_RECEIVED",
        object_type="EVIDENCE_ARTIFACT",
        object_id=str(artifact.id),
        details={
            "sha256": digest,
            "size_bytes": len(content),
            "source_id": source_id,
            "scan_engine": scan.engine,
            "scan_signature_version": scan.signature_version,
        },
    )
    try:
        commit_or_conflict(session, "Evidence artifact metadata conflicts with existing data")
    except HTTPException:
        store.delete(storage_key)
        raise
    session.refresh(artifact)
    return artifact


@router.get("/artifacts", response_model=list[ArtifactRead])
def list_artifacts(
    project_id: uuid.UUID, session: SessionDep, actor: ActorDep
) -> list[EvidenceArtifact]:
    project = project_with_role(session, actor, project_id, READ_ROLES)
    return list(
        session.scalars(
            select(EvidenceArtifact)
            .where(EvidenceArtifact.project_id == project.id)
            .order_by(EvidenceArtifact.received_at.desc(), EvidenceArtifact.id)
        )
    )


@router.get("/artifacts/{artifact_id}/content")
def download_artifact(
    project_id: uuid.UUID,
    artifact_id: uuid.UUID,
    session: SessionDep,
    actor: ActorDep,
    store: StoreDep,
) -> Response:
    project = project_with_role(session, actor, project_id, READ_ROLES)
    artifact = scoped_artifact(session, project, artifact_id)
    try:
        content = store.get(artifact.storage_key)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail="Evidence content is unavailable") from exc
    safe_name = artifact.original_filename.replace('"', "")
    return Response(
        content=content,
        media_type=artifact.media_type,
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
    )


@router.post("/items", response_model=EvidenceItemRead, status_code=201)
def add_item(
    project_id: uuid.UUID, data: EvidenceItemCreate, session: SessionDep, actor: ActorDep
) -> EvidenceItem:
    project = project_with_role(session, actor, project_id, WRITE_ROLES)
    item = create_evidence_item(session, actor, project, data)
    commit_or_conflict(session, "Evidence item conflicts with existing data")
    session.refresh(item)
    return item


@router.get("/items", response_model=list[EvidenceItemRead])
def list_items(
    project_id: uuid.UUID,
    session: SessionDep,
    actor: ActorDep,
    status_filter: str | None = None,
    field_name: str | None = None,
) -> list[EvidenceItem]:
    project = project_with_role(session, actor, project_id, READ_ROLES)
    query = select(EvidenceItem).where(EvidenceItem.project_id == project.id)
    if status_filter:
        query = query.where(EvidenceItem.status == status_filter)
    if field_name:
        query = query.where(EvidenceItem.field_name == field_name)
    return list(session.scalars(query.order_by(EvidenceItem.created_at.desc(), EvidenceItem.id)))


@router.post("/relations", response_model=EvidenceRelationRead, status_code=201)
def add_relation(
    project_id: uuid.UUID, data: EvidenceRelationCreate, session: SessionDep, actor: ActorDep
):
    project = project_with_role(session, actor, project_id, WRITE_ROLES)
    relation = create_relation(session, actor, project, data)
    commit_or_conflict(session, "Evidence relation already exists")
    session.refresh(relation)
    return relation


@router.get("/relations", response_model=list[EvidenceRelationRead])
def list_relations(
    project_id: uuid.UUID,
    session: SessionDep,
    actor: ActorDep,
    item_id: uuid.UUID | None = None,
) -> list[EvidenceRelation]:
    project = project_with_role(session, actor, project_id, READ_ROLES)
    query = select(EvidenceRelation).where(EvidenceRelation.project_id == project.id)
    if item_id:
        query = query.where(
            (EvidenceRelation.from_item_id == item_id) | (EvidenceRelation.to_item_id == item_id)
        )
    return list(session.scalars(query.order_by(EvidenceRelation.created_at.desc())))


@router.post("/items/{item_id}/verify", response_model=VerificationRead, status_code=201)
def verify(
    project_id: uuid.UUID,
    item_id: uuid.UUID,
    data: VerificationCreate,
    session: SessionDep,
    actor: ActorDep,
):
    project = project_with_role(session, actor, project_id, VERIFY_ROLES)
    event = verify_item(session, actor, project, item_id, data)
    commit_or_conflict(session, "Verification conflicts with existing evidence")
    session.refresh(event)
    return event


@router.get("/verifications", response_model=list[VerificationRead])
def list_verifications(
    project_id: uuid.UUID,
    session: SessionDep,
    actor: ActorDep,
    item_id: uuid.UUID | None = None,
) -> list[VerificationEvent]:
    project = project_with_role(session, actor, project_id, READ_ROLES)
    query = select(VerificationEvent).where(VerificationEvent.project_id == project.id)
    if item_id:
        query = query.where(VerificationEvent.evidence_item_id == item_id)
    return list(session.scalars(query.order_by(VerificationEvent.occurred_at.desc())))


@router.post("/reliability", response_model=ReliabilityRead, status_code=201)
def add_reliability(
    project_id: uuid.UUID, data: ReliabilityCreate, session: SessionDep, actor: ActorDep
):
    project = project_with_role(session, actor, project_id, VERIFY_ROLES)
    assessment = assess_reliability(session, actor, project, data)
    commit_or_conflict(session, "Reliability assessment conflicts with existing data")
    session.refresh(assessment)
    return assessment


@router.get("/reliability", response_model=list[ReliabilityRead])
def list_reliability(
    project_id: uuid.UUID,
    session: SessionDep,
    actor: ActorDep,
    source_id: str | None = None,
) -> list[SourceReliabilityAssessment]:
    project = project_with_role(session, actor, project_id, READ_ROLES)
    query = select(SourceReliabilityAssessment).where(
        SourceReliabilityAssessment.project_id == project.id
    )
    if source_id:
        query = query.where(SourceReliabilityAssessment.source_id == source_id)
    return list(session.scalars(query.order_by(SourceReliabilityAssessment.valid_from.desc())))


@router.post("/contradictions", response_model=ContradictionRead, status_code=201)
def add_contradiction(
    project_id: uuid.UUID, data: ContradictionCreate, session: SessionDep, actor: ActorDep
):
    project = project_with_role(session, actor, project_id, WRITE_ROLES)
    contradiction = create_contradiction(session, actor, project, data)
    commit_or_conflict(session, "Contradiction relation already exists")
    session.refresh(contradiction)
    return contradiction


@router.get("/contradictions", response_model=list[ContradictionRead])
def list_contradictions(
    project_id: uuid.UUID, session: SessionDep, actor: ActorDep
) -> list[Contradiction]:
    project = project_with_role(session, actor, project_id, READ_ROLES)
    return list(
        session.scalars(
            select(Contradiction)
            .where(Contradiction.project_id == project.id)
            .order_by(Contradiction.created_at.desc())
        )
    )


@router.post("/contradictions/{contradiction_id}/resolve", response_model=ContradictionRead)
def resolve(
    project_id: uuid.UUID,
    contradiction_id: uuid.UUID,
    data: ContradictionResolve,
    session: SessionDep,
    actor: ActorDep,
):
    project = project_with_role(session, actor, project_id, VERIFY_ROLES)
    contradiction = resolve_contradiction(session, actor, project, contradiction_id, data)
    commit_or_conflict(session, "Contradiction resolution conflicts with existing data")
    session.refresh(contradiction)
    return contradiction


@router.post("/requests", response_model=EvidenceRequestRead, status_code=201)
def add_request(
    project_id: uuid.UUID, data: EvidenceRequestCreate, session: SessionDep, actor: ActorDep
):
    project = project_with_role(session, actor, project_id, WRITE_ROLES)
    request = create_evidence_request(session, actor, project, data)
    commit_or_conflict(session, "Evidence request conflicts with existing data")
    session.refresh(request)
    return request


@router.get("/requests", response_model=list[EvidenceRequestRead])
def list_requests(
    project_id: uuid.UUID, session: SessionDep, actor: ActorDep
) -> list[EvidenceRequest]:
    project = project_with_role(session, actor, project_id, READ_ROLES)
    return list(
        session.scalars(
            select(EvidenceRequest)
            .where(EvidenceRequest.project_id == project.id)
            .order_by(EvidenceRequest.due_at, EvidenceRequest.created_at)
        )
    )


@router.post("/requests/{request_id}/satisfy", response_model=EvidenceRequestRead)
def satisfy_request(
    project_id: uuid.UUID,
    request_id: uuid.UUID,
    data: EvidenceRequestSatisfy,
    session: SessionDep,
    actor: ActorDep,
):
    project = project_with_role(session, actor, project_id, WRITE_ROLES)
    request = satisfy_evidence_request(session, actor, project, request_id, data.evidence_item_id)
    commit_or_conflict(session, "Evidence request update conflicts with existing data")
    session.refresh(request)
    return request


@router.post("/imports/preview", response_model=ImportBatchRead, status_code=201)
def import_preview(
    project_id: uuid.UUID,
    data: ImportPreviewCreate,
    session: SessionDep,
    actor: ActorDep,
    store: StoreDep,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=200)],
):
    project = project_with_role(session, actor, project_id, WRITE_ROLES)
    artifact = scoped_artifact(session, project, data.artifact_id)
    batch = preview_import(session, actor, project, artifact, data.mapping, idempotency_key, store)
    commit_or_conflict(session, "Import idempotency key already exists")
    session.refresh(batch)
    return batch


@router.get("/imports/{batch_id}", response_model=ImportBatchRead)
def get_import(
    project_id: uuid.UUID, batch_id: uuid.UUID, session: SessionDep, actor: ActorDep
) -> ImportBatch:
    project = project_with_role(session, actor, project_id, READ_ROLES)
    batch = session.get(ImportBatch, batch_id)
    if batch is None or batch.project_id != project.id:
        raise HTTPException(status_code=404, detail="Import batch not found")
    return batch


@router.post("/imports/{batch_id}/commit", response_model=ImportCommitRead)
def import_commit(
    project_id: uuid.UUID, batch_id: uuid.UUID, session: SessionDep, actor: ActorDep
) -> ImportCommitRead:
    project = project_with_role(session, actor, project_id, WRITE_ROLES)
    batch, item_ids = commit_import(session, actor, project, batch_id)
    commit_or_conflict(session, "Import commit conflicts with existing evidence")
    session.refresh(batch)
    return ImportCommitRead(batch=batch, evidence_item_ids=item_ids)
