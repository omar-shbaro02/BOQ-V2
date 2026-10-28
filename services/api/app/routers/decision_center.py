from __future__ import annotations

import csv
import io
import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import ActorContext, get_actor
from app.database import get_db
from app.decision_center_schemas import (
    DecisionQueueItem,
    GovernedReport,
    ReportLifecycleCreate,
    ReportLifecycleRead,
    ReportSnapshotCreate,
    ReportSnapshotRead,
    ReviewQueues,
)
from app.generated.taxonomies import ProjectRole
from app.models import ReportSnapshot
from app.services.access import get_scoped_project, require_project_roles
from app.services.cases import scoped_case
from app.services.decision_center import (
    case_dossier,
    conformity_report,
    decision_queue,
    exception_report,
    pilot_kpi_report,
    review_queues,
    weekly_brief,
)
from app.services.reports import (
    create_report,
    lifecycle_events,
    transition_report,
)

router = APIRouter(prefix="/api/v1/projects/{project_id}/decision-center", tags=["decision-center"])
SessionDep = Annotated[Session, Depends(get_db)]
ActorDep = Annotated[ActorContext, Depends(get_actor)]


def scoped_project(session: Session, actor: ActorContext, project_id: uuid.UUID):
    project = get_scoped_project(session, actor, project_id)
    require_project_roles(session, actor, project, set(ProjectRole))
    return project


def report_read(session: Session, report: ReportSnapshot) -> dict:
    events = lifecycle_events(session, report.id)
    return {
        **{column.name: getattr(report, column.name) for column in report.__table__.columns},
        "lifecycle_status": events[-1].to_status,
        "lifecycle_events": events,
    }


def commit_or_conflict(session: Session, detail: str) -> None:
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from exc


@router.get("/queue", response_model=list[DecisionQueueItem])
def get_decision_queue(
    project_id: uuid.UUID, session: SessionDep, actor: ActorDep
) -> list[DecisionQueueItem]:
    return decision_queue(session, scoped_project(session, actor, project_id))


@router.get("/review-queues", response_model=ReviewQueues)
def get_review_queues(
    project_id: uuid.UUID,
    session: SessionDep,
    actor: ActorDep,
    as_of: Annotated[datetime | None, Query()] = None,
) -> ReviewQueues:
    project = scoped_project(session, actor, project_id)
    return review_queues(session, project, as_of or datetime.now(UTC))


@router.get("/exports/decision-queue.csv", response_class=Response)
def export_decision_queue_csv(
    project_id: uuid.UUID, session: SessionDep, actor: ActorDep
) -> Response:
    project = scoped_project(session, actor, project_id)
    output = io.StringIO(newline="")
    fields = list(DecisionQueueItem.model_fields)
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for item in decision_queue(session, project):
        writer.writerow(item.model_dump(mode="json"))
    return Response(
        content=output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="decision-queue.csv"',
            "X-VAI-Export-Schema": "DECISION_QUEUE-1.0.0",
            "X-VAI-Semantic-Notice": "recommendation-is-not-human-decision",
            "X-VAI-Project-Timezone": project.timezone,
        },
    )


@router.get("/reports/weekly-decision-brief", response_model=GovernedReport)
def get_weekly_brief(
    project_id: uuid.UUID,
    session: SessionDep,
    actor: ActorDep,
    as_of: Annotated[datetime | None, Query()] = None,
) -> GovernedReport:
    project = scoped_project(session, actor, project_id)
    return weekly_brief(session, actor, project, as_of or datetime.now(UTC))


@router.get("/reports/case-dossier/{case_id}", response_model=GovernedReport)
def get_case_dossier(
    project_id: uuid.UUID,
    case_id: uuid.UUID,
    session: SessionDep,
    actor: ActorDep,
    as_of: Annotated[datetime | None, Query()] = None,
) -> GovernedReport:
    project = scoped_project(session, actor, project_id)
    case = scoped_case(session, project, case_id)
    return case_dossier(session, actor, project, case, as_of or datetime.now(UTC))


@router.get("/reports/project-control-exceptions", response_model=GovernedReport)
def get_exception_report(
    project_id: uuid.UUID,
    session: SessionDep,
    actor: ActorDep,
    as_of: Annotated[datetime | None, Query()] = None,
) -> GovernedReport:
    project = scoped_project(session, actor, project_id)
    return exception_report(session, actor, project, as_of or datetime.now(UTC))


@router.get("/reports/pilot-kpis", response_model=GovernedReport)
def get_pilot_kpis(
    project_id: uuid.UUID,
    session: SessionDep,
    actor: ActorDep,
    as_of: Annotated[datetime | None, Query()] = None,
) -> GovernedReport:
    project = scoped_project(session, actor, project_id)
    return pilot_kpi_report(session, actor, project, as_of or datetime.now(UTC))


@router.get("/reports/governance-conformity", response_model=GovernedReport)
def get_conformity_report(
    project_id: uuid.UUID,
    session: SessionDep,
    actor: ActorDep,
    as_of: Annotated[datetime | None, Query()] = None,
) -> GovernedReport:
    project = scoped_project(session, actor, project_id)
    return conformity_report(session, actor, project, as_of or datetime.now(UTC))


@router.get("/report-snapshots", response_model=list[ReportSnapshotRead])
def get_report_snapshots(project_id: uuid.UUID, session: SessionDep, actor: ActorDep) -> list[dict]:
    project = scoped_project(session, actor, project_id)
    reports = session.scalars(
        select(ReportSnapshot)
        .where(ReportSnapshot.project_id == project.id)
        .order_by(ReportSnapshot.report_number.desc())
    )
    return [report_read(session, report) for report in reports]


@router.get("/report-snapshots/{report_id}", response_model=ReportSnapshotRead)
def get_report_snapshot(
    project_id: uuid.UUID, report_id: uuid.UUID, session: SessionDep, actor: ActorDep
) -> dict:
    project = scoped_project(session, actor, project_id)
    report = session.get(ReportSnapshot, report_id)
    if report is None or report.project_id != project.id:
        raise HTTPException(status_code=404, detail="Report snapshot not found")
    return report_read(session, report)


@router.post("/report-snapshots", response_model=ReportSnapshotRead, status_code=201)
def add_report_snapshot(
    project_id: uuid.UUID,
    data: ReportSnapshotCreate,
    session: SessionDep,
    actor: ActorDep,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=200)],
) -> dict:
    project = scoped_project(session, actor, project_id)
    require_project_roles(
        session,
        actor,
        project,
        {
            ProjectRole.ORGANIZATION_ADMIN,
            ProjectRole.PROJECT_ADMIN,
            ProjectRole.ANALYST_CONTROLLER,
            ProjectRole.DECISION_OWNER,
        },
    )
    report = create_report(session, actor, project, data, idempotency_key)
    commit_or_conflict(session, "Report snapshot idempotency conflict")
    session.refresh(report)
    return report_read(session, report)


@router.post(
    "/report-snapshots/{report_id}/lifecycle-events",
    response_model=ReportLifecycleRead,
    status_code=201,
)
def add_report_lifecycle_event(
    project_id: uuid.UUID,
    report_id: uuid.UUID,
    data: ReportLifecycleCreate,
    session: SessionDep,
    actor: ActorDep,
) -> ReportLifecycleRead:
    project = scoped_project(session, actor, project_id)
    require_project_roles(
        session,
        actor,
        project,
        {
            ProjectRole.ORGANIZATION_ADMIN,
            ProjectRole.PROJECT_ADMIN,
            ProjectRole.ANALYST_CONTROLLER,
            ProjectRole.DECISION_OWNER,
            ProjectRole.APPROVER_ESCALATION_AUTHORITY,
        },
    )
    report = session.get(ReportSnapshot, report_id)
    if report is None or report.project_id != project.id:
        raise HTTPException(status_code=404, detail="Report snapshot not found")
    event = transition_report(session, actor, project, report, data)
    commit_or_conflict(session, "Report lifecycle transition conflict")
    session.refresh(event)
    return event


@router.get("/approved-report-snapshots/{report_id}", response_model=ReportSnapshotRead)
def get_approved_report_snapshot(
    project_id: uuid.UUID, report_id: uuid.UUID, session: SessionDep, actor: ActorDep
) -> dict:
    project = scoped_project(session, actor, project_id)
    report = session.get(ReportSnapshot, report_id)
    if report is None or report.project_id != project.id:
        raise HTTPException(status_code=404, detail="Report snapshot not found")
    result = report_read(session, report)
    if result["lifecycle_status"] != "APPROVED":
        raise HTTPException(status_code=409, detail="Report is not approved for external use")
    return result
