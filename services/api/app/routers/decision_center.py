from __future__ import annotations

import csv
import io
import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.auth import ActorContext, get_actor
from app.database import get_db
from app.decision_center_schemas import DecisionQueueItem, GovernedReport, ReviewQueues
from app.generated.taxonomies import ProjectRole
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

router = APIRouter(prefix="/api/v1/projects/{project_id}/decision-center", tags=["decision-center"])
SessionDep = Annotated[Session, Depends(get_db)]
ActorDep = Annotated[ActorContext, Depends(get_actor)]


def scoped_project(session: Session, actor: ActorContext, project_id: uuid.UUID):
    project = get_scoped_project(session, actor, project_id)
    require_project_roles(session, actor, project, set(ProjectRole))
    return project


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
