"""Bound queue-query growth without inventing measurements for unevaluated cases."""

import json
import time
import uuid
from datetime import UTC, datetime, timedelta

from app.models import ControlledObject, DecisionCaseControlledObject, DecisionCaseShell, Project
from app.services.decision_center import decision_queue
from sqlalchemy import event
from test_control_context_api import api as api
from test_project_control_api import bootstrap_project


def seed_queue_workload(session, organization_id, project_id, case_count=50):
    objects = [
        ControlledObject(
            id=uuid.uuid4(),
            organization_id=organization_id,
            project_id=project_id,
            object_type="WORK_PACKAGE",
            code=f"PERF-WP-{number}",
            name=f"Probe package {number}",
        )
        for number in range(10)
    ]
    session.add_all(objects)
    session.flush()
    cases = []
    for number in range(case_count):
        case = DecisionCaseShell(
            id=uuid.uuid4(),
            organization_id=organization_id,
            project_id=project_id,
            case_number=f"PERF-{number:03}",
            title=f"Unevaluated probe case {number}",
            case_type="PROGRESS",
            lifecycle="CLOSED" if number % 10 == 0 else "OPEN",
            closed_at=datetime(2026, 1, 2, tzinfo=UTC) if number % 10 == 0 else None,
            close_reason="Synthetic administrative load-fixture closure"
            if number % 10 == 0
            else None,
            owner_actor_id="probe@test",
            created_by="probe@test",
            governance_state="HUMAN_REVIEW_REQUIRED",
            opened_at=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=number),
        )
        session.add(case)
        session.flush()
        session.add(
            DecisionCaseControlledObject(
                case_id=case.id, controlled_object_id=objects[number % 10].id
            )
        )
        cases.append(case)
    session.commit()
    return cases


def test_queue_query_budget_and_unknown_semantics_for_fifty_cases(api, tmp_path):
    client, sessions = api
    org, project_id, _ = bootstrap_project(client, "queue-performance")
    foreign_org, foreign_project, _ = bootstrap_project(client, "foreign-queue-performance")
    with sessions() as session:
        seed_queue_workload(session, uuid.UUID(org), uuid.UUID(project_id))
        seed_queue_workload(
            session, uuid.UUID(foreign_org), uuid.UUID(foreign_project), case_count=1
        )
    statements = []
    engine = sessions.kw["bind"]

    def count_statement(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    with sessions() as session:
        project = session.get(Project, uuid.UUID(project_id))
        event.listen(engine, "before_cursor_execute", count_statement)
        started = time.perf_counter()
        try:
            queue = decision_queue(session, project)
        finally:
            elapsed = time.perf_counter() - started
            event.remove(engine, "before_cursor_execute", count_statement)
    (tmp_path / "queue-query-budget.json").write_text(
        json.dumps(
            {
                "cases": 50,
                "work_packages": 10,
                "selects": len(statements),
                "seconds": elapsed,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    assert len(queue) == 50
    assert sum(item.lifecycle == "CLOSED" for item in queue) == 5
    assert all(item.controlled_object_count == 1 for item in queue)
    assert all(
        item.recommended_disposition is None
        and item.human_disposition is None
        and item.overall_confidence is None
        and item.priority_score is None
        for item in queue
    )
    assert queue[0].case_number == "PERF-049"
    assert all(item.lifecycle == "CLOSED" for item in queue[-5:])
    assert len(statements) <= 12, f"50-case read issued {len(statements)} SQL statements"
