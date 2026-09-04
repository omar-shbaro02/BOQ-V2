import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import ActorContext, get_actor
from app.database import get_db
from app.generated.taxonomies import AuthorizedContextType, ProjectRole, SemanticState
from app.models import (
    AuditEvent,
    AuthorityGrant,
    AuthorizedContextVersion,
    ControlledObject,
    ControlledObjectRelation,
    Membership,
    Organization,
    Project,
)
from app.schemas import (
    AuditEventRead,
    AuthorityGrantCreate,
    AuthorityGrantRead,
    ContextActivation,
    ContextVersionCreate,
    ContextVersionRead,
    ControlledObjectCreate,
    ControlledObjectRead,
    MembershipCreate,
    MembershipRead,
    OrganizationCreate,
    OrganizationRead,
    ProjectCreate,
    ProjectRead,
    RelationCreate,
    RelationRead,
)
from app.services.access import get_scoped_project, require_organization, require_project_roles
from app.services.audit import record_audit
from app.services.context import activate_source_version, create_source_version

router = APIRouter(prefix="/api/v1", tags=["control-context"])
SessionDep = Annotated[Session, Depends(get_db)]
ActorDep = Annotated[ActorContext, Depends(get_actor)]

ALL_PROJECT_ROLES = set(ProjectRole)
ADMIN_ROLES = {ProjectRole.ORGANIZATION_ADMIN, ProjectRole.PROJECT_ADMIN}


def commit_or_conflict(session: Session, detail: str) -> None:
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from exc


def flush_or_conflict(session: Session, detail: str) -> None:
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from exc


@router.post("/organizations", response_model=OrganizationRead, status_code=201)
def create_organization(
    data: OrganizationCreate, session: SessionDep, actor: ActorDep
) -> Organization:
    if ProjectRole.ORGANIZATION_ADMIN not in actor.asserted_roles:
        raise HTTPException(status_code=403, detail="Development bootstrap admin role required")
    organization = Organization(id=uuid.uuid4(), name=data.name, slug=data.slug)
    session.add(organization)
    flush_or_conflict(session, "Organization slug already exists")
    session.add(
        Membership(
            id=uuid.uuid4(),
            organization_id=organization.id,
            project_id=None,
            actor_id=actor.actor_id,
            role=ProjectRole.ORGANIZATION_ADMIN,
        )
    )
    record_audit(
        session,
        actor,
        organization_id=organization.id,
        project_id=None,
        action="ORGANIZATION_CREATED",
        object_type="ORGANIZATION",
        object_id=str(organization.id),
    )
    commit_or_conflict(session, "Organization slug already exists")
    session.refresh(organization)
    return organization


@router.post(
    "/organizations/{organization_id}/memberships", response_model=MembershipRead, status_code=201
)
def create_organization_membership(
    organization_id: uuid.UUID,
    data: MembershipCreate,
    session: SessionDep,
    actor: ActorDep,
) -> Membership:
    require_organization(actor, organization_id)
    admin = session.scalar(
        select(Membership).where(
            Membership.organization_id == organization_id,
            Membership.project_id.is_(None),
            Membership.actor_id == actor.actor_id,
            Membership.role == ProjectRole.ORGANIZATION_ADMIN,
            Membership.active.is_(True),
        )
    )
    if admin is None:
        raise HTTPException(status_code=403, detail="Organization admin role required")
    membership = Membership(
        id=uuid.uuid4(),
        organization_id=organization_id,
        project_id=None,
        actor_id=data.actor_id,
        role=data.role,
    )
    session.add(membership)
    record_audit(
        session,
        actor,
        organization_id=organization_id,
        project_id=None,
        action="ORGANIZATION_MEMBERSHIP_CREATED",
        object_type="MEMBERSHIP",
        object_id=str(membership.id),
        details={"member_actor_id": data.actor_id, "role": data.role},
    )
    commit_or_conflict(session, "Membership already exists")
    return membership


@router.post(
    "/organizations/{organization_id}/projects", response_model=ProjectRead, status_code=201
)
def create_project(
    organization_id: uuid.UUID,
    data: ProjectCreate,
    session: SessionDep,
    actor: ActorDep,
) -> Project:
    require_organization(actor, organization_id)
    admin = session.scalar(
        select(Membership).where(
            Membership.organization_id == organization_id,
            Membership.project_id.is_(None),
            Membership.actor_id == actor.actor_id,
            Membership.role == ProjectRole.ORGANIZATION_ADMIN,
            Membership.active.is_(True),
        )
    )
    if admin is None:
        raise HTTPException(status_code=403, detail="Organization admin role required")
    project = Project(
        id=uuid.uuid4(), organization_id=organization_id, **data.model_dump(mode="json")
    )
    session.add(project)
    flush_or_conflict(session, "Project code already exists in organization")
    session.add(
        Membership(
            id=uuid.uuid4(),
            organization_id=organization_id,
            project_id=project.id,
            actor_id=actor.actor_id,
            role=ProjectRole.PROJECT_ADMIN,
        )
    )
    record_audit(
        session,
        actor,
        organization_id=organization_id,
        project_id=project.id,
        action="PROJECT_CREATED",
        object_type="PROJECT",
        object_id=str(project.id),
    )
    commit_or_conflict(session, "Project code already exists in organization")
    session.refresh(project)
    return project


@router.get("/projects/{project_id}", response_model=ProjectRead)
def get_project(project_id: uuid.UUID, session: SessionDep, actor: ActorDep) -> Project:
    project = get_scoped_project(session, actor, project_id)
    require_project_roles(session, actor, project, ALL_PROJECT_ROLES)
    return project


@router.get("/organizations/{organization_id}/projects", response_model=list[ProjectRead])
def list_projects(
    organization_id: uuid.UUID, session: SessionDep, actor: ActorDep
) -> list[Project]:
    require_organization(actor, organization_id)
    membership = session.scalar(
        select(Membership.id).where(
            Membership.organization_id == organization_id,
            Membership.actor_id == actor.actor_id,
            Membership.active.is_(True),
        )
    )
    if membership is None:
        raise HTTPException(status_code=403, detail="Organization membership required")
    return list(
        session.scalars(
            select(Project).where(Project.organization_id == organization_id).order_by(Project.code)
        )
    )


@router.post("/projects/{project_id}/memberships", response_model=MembershipRead, status_code=201)
def create_project_membership(
    project_id: uuid.UUID,
    data: MembershipCreate,
    session: SessionDep,
    actor: ActorDep,
) -> Membership:
    project = get_scoped_project(session, actor, project_id)
    require_project_roles(session, actor, project, ADMIN_ROLES)
    membership = Membership(
        id=uuid.uuid4(),
        organization_id=project.organization_id,
        project_id=project.id,
        actor_id=data.actor_id,
        role=data.role,
    )
    session.add(membership)
    record_audit(
        session,
        actor,
        organization_id=project.organization_id,
        project_id=project.id,
        action="PROJECT_MEMBERSHIP_CREATED",
        object_type="MEMBERSHIP",
        object_id=str(membership.id),
        details={"member_actor_id": data.actor_id, "role": data.role},
    )
    commit_or_conflict(session, "Membership already exists")
    return membership


@router.get("/projects/{project_id}/memberships", response_model=list[MembershipRead])
def list_project_memberships(
    project_id: uuid.UUID, session: SessionDep, actor: ActorDep
) -> list[Membership]:
    project = get_scoped_project(session, actor, project_id)
    require_project_roles(session, actor, project, ADMIN_ROLES)
    return list(
        session.scalars(
            select(Membership)
            .where(Membership.project_id == project.id)
            .order_by(Membership.actor_id, Membership.role)
        )
    )


@router.post(
    "/projects/{project_id}/controlled-objects",
    response_model=ControlledObjectRead,
    status_code=201,
)
def create_controlled_object(
    project_id: uuid.UUID,
    data: ControlledObjectCreate,
    session: SessionDep,
    actor: ActorDep,
) -> ControlledObject:
    project = get_scoped_project(session, actor, project_id)
    require_project_roles(
        session,
        actor,
        project,
        ADMIN_ROLES | {ProjectRole.DATA_CONTRIBUTOR, ProjectRole.ANALYST_CONTROLLER},
    )
    controlled_object = ControlledObject(
        id=uuid.uuid4(),
        organization_id=project.organization_id,
        project_id=project.id,
        **data.model_dump(),
    )
    session.add(controlled_object)
    record_audit(
        session,
        actor,
        organization_id=project.organization_id,
        project_id=project.id,
        action="CONTROLLED_OBJECT_CREATED",
        object_type="CONTROLLED_OBJECT",
        object_id=str(controlled_object.id),
        details={"type": data.object_type, "code": data.code},
    )
    commit_or_conflict(session, "Controlled-object code already exists in project")
    return controlled_object


@router.get("/projects/{project_id}/controlled-objects", response_model=list[ControlledObjectRead])
def list_controlled_objects(
    project_id: uuid.UUID, session: SessionDep, actor: ActorDep
) -> list[ControlledObject]:
    project = get_scoped_project(session, actor, project_id)
    require_project_roles(session, actor, project, ALL_PROJECT_ROLES)
    return list(
        session.scalars(
            select(ControlledObject)
            .where(ControlledObject.project_id == project.id)
            .order_by(ControlledObject.code)
        )
    )


@router.post("/projects/{project_id}/relations", response_model=RelationRead, status_code=201)
def create_relation(
    project_id: uuid.UUID,
    data: RelationCreate,
    session: SessionDep,
    actor: ActorDep,
) -> ControlledObjectRelation:
    project = get_scoped_project(session, actor, project_id)
    require_project_roles(
        session,
        actor,
        project,
        ADMIN_ROLES | {ProjectRole.DATA_CONTRIBUTOR, ProjectRole.ANALYST_CONTROLLER},
    )
    if data.source_id == data.target_id:
        raise HTTPException(status_code=422, detail="A controlled object cannot relate to itself")
    objects = list(
        session.scalars(
            select(ControlledObject).where(
                ControlledObject.project_id == project.id,
                ControlledObject.id.in_([data.source_id, data.target_id]),
            )
        )
    )
    if len(objects) != 2:
        raise HTTPException(
            status_code=422, detail="Both controlled objects must belong to project"
        )
    relation = ControlledObjectRelation(
        id=uuid.uuid4(),
        organization_id=project.organization_id,
        project_id=project.id,
        **data.model_dump(),
    )
    session.add(relation)
    record_audit(
        session,
        actor,
        organization_id=project.organization_id,
        project_id=project.id,
        action="CONTROLLED_OBJECT_RELATION_CREATED",
        object_type="CONTROLLED_OBJECT_RELATION",
        object_id=str(relation.id),
        details={"relation_type": data.relation_type},
    )
    commit_or_conflict(session, "Controlled-object relation already exists")
    return relation


@router.get("/projects/{project_id}/relations", response_model=list[RelationRead])
def list_relations(
    project_id: uuid.UUID, session: SessionDep, actor: ActorDep
) -> list[ControlledObjectRelation]:
    project = get_scoped_project(session, actor, project_id)
    require_project_roles(session, actor, project, ALL_PROJECT_ROLES)
    return list(
        session.scalars(
            select(ControlledObjectRelation).where(
                ControlledObjectRelation.project_id == project.id
            )
        )
    )


@router.post(
    "/projects/{project_id}/authority-grants",
    response_model=AuthorityGrantRead,
    status_code=201,
)
def create_authority_grant(
    project_id: uuid.UUID,
    data: AuthorityGrantCreate,
    session: SessionDep,
    actor: ActorDep,
) -> AuthorityGrant:
    project = get_scoped_project(session, actor, project_id)
    require_project_roles(session, actor, project, ADMIN_ROLES)
    if data.controlled_object_id:
        controlled_object = session.get(ControlledObject, data.controlled_object_id)
        if controlled_object is None or controlled_object.project_id != project.id:
            raise HTTPException(status_code=422, detail="Authority object must belong to project")
    grant = AuthorityGrant(
        id=uuid.uuid4(),
        organization_id=project.organization_id,
        project_id=project.id,
        **data.model_dump(),
    )
    session.add(grant)
    record_audit(
        session,
        actor,
        organization_id=project.organization_id,
        project_id=project.id,
        action="AUTHORITY_GRANT_CREATED",
        object_type="AUTHORITY_GRANT",
        object_id=str(grant.id),
        details={"grantee": data.actor_id, "authority_type": data.authority_type},
    )
    commit_or_conflict(session, "Authority grant conflict")
    return grant


@router.get("/projects/{project_id}/authority-grants", response_model=list[AuthorityGrantRead])
def list_authority_grants(
    project_id: uuid.UUID, session: SessionDep, actor: ActorDep
) -> list[AuthorityGrant]:
    project = get_scoped_project(session, actor, project_id)
    require_project_roles(session, actor, project, ADMIN_ROLES)
    return list(
        session.scalars(
            select(AuthorityGrant)
            .where(AuthorityGrant.project_id == project.id)
            .order_by(AuthorityGrant.actor_id, AuthorityGrant.authority_type)
        )
    )


@router.post(
    "/projects/{project_id}/authorized-context/versions",
    response_model=ContextVersionRead,
    status_code=201,
)
def create_context_version(
    project_id: uuid.UUID,
    data: ContextVersionCreate,
    session: SessionDep,
    actor: ActorDep,
):
    project = get_scoped_project(session, actor, project_id)
    require_project_roles(
        session,
        actor,
        project,
        ADMIN_ROLES | {ProjectRole.DATA_CONTRIBUTOR, ProjectRole.ANALYST_CONTROLLER},
    )
    version = create_source_version(session, actor, project, data)
    commit_or_conflict(session, "Context version conflict")
    return version


@router.post(
    "/projects/{project_id}/authorized-context/activate",
    response_model=ContextVersionRead,
    status_code=201,
)
def activate_context_version(
    project_id: uuid.UUID,
    data: ContextActivation,
    session: SessionDep,
    actor: ActorDep,
):
    project = get_scoped_project(session, actor, project_id)
    require_project_roles(
        session,
        actor,
        project,
        ADMIN_ROLES | {ProjectRole.APPROVER_ESCALATION_AUTHORITY},
    )
    version = activate_source_version(session, actor, project, data)
    commit_or_conflict(session, "Context activation conflict")
    return version


@router.get(
    "/projects/{project_id}/authorized-context/versions",
    response_model=list[ContextVersionRead],
)
def list_context_versions(
    project_id: uuid.UUID,
    session: SessionDep,
    actor: ActorDep,
    context_type: AuthorizedContextType | None = None,
) -> list[AuthorizedContextVersion]:
    project = get_scoped_project(session, actor, project_id)
    require_project_roles(session, actor, project, ALL_PROJECT_ROLES)
    query = select(AuthorizedContextVersion).where(
        AuthorizedContextVersion.project_id == project.id
    )
    if context_type:
        query = query.where(AuthorizedContextVersion.context_type == context_type)
    return list(
        session.scalars(
            query.order_by(
                AuthorizedContextVersion.context_type,
                AuthorizedContextVersion.version_number,
            )
        )
    )


@router.get(
    "/projects/{project_id}/authorized-context/current/{context_type}",
    response_model=ContextVersionRead,
)
def get_current_context(
    project_id: uuid.UUID,
    context_type: AuthorizedContextType,
    session: SessionDep,
    actor: ActorDep,
) -> AuthorizedContextVersion:
    project = get_scoped_project(session, actor, project_id)
    require_project_roles(session, actor, project, ALL_PROJECT_ROLES)
    current = session.scalar(
        select(AuthorizedContextVersion).where(
            AuthorizedContextVersion.project_id == project.id,
            AuthorizedContextVersion.context_type == context_type,
            AuthorizedContextVersion.semantic_state == SemanticState.CURRENT_AUTHORIZED,
        )
    )
    if current is None:
        raise HTTPException(status_code=404, detail="Current authorized context not found")
    return current


@router.post("/projects/{project_id}/activate", response_model=ProjectRead)
def activate_project(project_id: uuid.UUID, session: SessionDep, actor: ActorDep) -> Project:
    project = get_scoped_project(session, actor, project_id)
    require_project_roles(session, actor, project, ADMIN_ROLES)
    current_schedule = session.scalar(
        select(AuthorizedContextVersion.id).where(
            AuthorizedContextVersion.project_id == project.id,
            AuthorizedContextVersion.context_type == AuthorizedContextType.SCHEDULE,
            AuthorizedContextVersion.semantic_state == SemanticState.CURRENT_AUTHORIZED,
        )
    )
    if current_schedule is None:
        raise HTTPException(
            status_code=409,
            detail="Project activation requires a current authorized schedule",
        )
    project.status = "ACTIVE"
    record_audit(
        session,
        actor,
        organization_id=project.organization_id,
        project_id=project.id,
        action="PROJECT_ACTIVATED",
        object_type="PROJECT",
        object_id=str(project.id),
        details={"authorized_schedule_version_id": str(current_schedule)},
    )
    session.commit()
    return project


@router.get("/projects/{project_id}/audit-events", response_model=list[AuditEventRead])
def list_project_audit_events(
    project_id: uuid.UUID, session: SessionDep, actor: ActorDep
) -> list[AuditEvent]:
    project = get_scoped_project(session, actor, project_id)
    require_project_roles(
        session,
        actor,
        project,
        ADMIN_ROLES | {ProjectRole.AUDITOR_READ_ONLY},
    )
    return list(
        session.scalars(
            select(AuditEvent)
            .where(AuditEvent.project_id == project.id)
            .order_by(AuditEvent.occurred_at, AuditEvent.event_id)
        )
    )
