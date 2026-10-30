"""Workbook assertions become reported evidence, never verified progress or a deadline forecast."""

import io
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation

from app.archive_limits import load_workbook
from app.auth import ActorContext
from app.evidence_schemas import EvidenceItemCreate
from app.generated.taxonomies import AuthorizedContextType
from app.models import ControlledObject, ProgressWorkbookImport, Project
from app.progress_schemas import ProgressMeasurementCreate
from app.services.audit import record_audit
from app.services.evidence import create_evidence_item, scoped_artifact
from app.services.ms_project_export import HEADERS
from app.services.progress import record_measurement
from app.services.progress_columns import progress_input_rows
from app.services.project_context import digest, project_lock
from app.services.project_control import require_current_context
from app.services.schedule import working_days_between
from app.storage import EvidenceStore
from app.workbook_schemas import ProgressWorkbookCreate
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

FORMULA_VERSION = "GOVERNED-WORKBOOK-1.0.0"


def parse_rows(content: bytes) -> list[dict]:
    try:
        workbook = load_workbook(io.BytesIO(content), data_only=False, read_only=True)
        try:
            if "Progress Template Metadata" in workbook:
                metadata = dict(
                    workbook["Progress Template Metadata"].iter_rows(
                        min_row=2, max_col=2, values_only=True
                    )
                )
                if metadata.get("mode") == "SYNTHETIC_SAMPLE":
                    raise ValueError(
                        "Fictional examples cannot be saved as governed progress; "
                        "download a blank template"
                    )
            if "Tasks" not in workbook or "Progress Report" not in workbook:
                raise ValueError("Workbook must contain Tasks and Progress Report")
            tasks = workbook["Tasks"]
            if tuple(cell.value for cell in tasks[1][:6]) != HEADERS:
                raise ValueError("Tasks headers do not match the six-column contract")
            task_rows = {}
            for values in tasks.iter_rows(min_row=2, values_only=True):
                if values[0] is None:
                    continue
                task_id = int(values[0])
                if task_id < 1 or task_id in task_rows or str(values[0]) != str(task_id):
                    raise ValueError("Task IDs must be unique positive integers")
                task_rows[task_id] = values
            progress = workbook["Progress Report"]
            rows = []
            seen = set()
            for values in progress_input_rows(progress):
                if values[1] is None:
                    continue
                task_id = int(values[1])
                if str(values[1]) != str(task_id) or task_id in seen or task_id not in task_rows:
                    raise ValueError("Progress task ID missing or duplicated")
                seen.add(task_id)
                original = task_rows[task_id]
                if str(values[2]) != str(original[1]):
                    raise ValueError("Progress activity name differs from Tasks")
                for progress_date, task_date in (
                    (values[4], original[3]),
                    (values[5], original[4]),
                ):
                    if as_date(progress_date) != as_date(task_date):
                        raise ValueError("Progress activity dates differ from Tasks")
                raw = values[6]
                percent = None if raw in (None, "") else Decimal(str(raw))
                if percent is not None and (not percent.is_finite() or not 0 <= percent <= 100):
                    raise ValueError("Reported completion must be from 0 to 100")
                rows.append(
                    {
                        "task_id": task_id,
                        "task_name": str(values[2]),
                        "start": as_date(original[3]),
                        "finish": as_date(original[4]),
                        "reported_percent": percent,
                        "report_date": as_date(values[7]) if values[7] else None,
                        "remarks": str(values[8] or ""),
                        "reported_evidence_reference": str(values[9] or ""),
                        "responsible_party": str(values[10] or ""),
                    }
                )
            if not rows or seen != set(task_rows):
                raise ValueError("Every workbook task must have exactly one progress row")
            return rows
        finally:
            workbook.close()
    except (ValueError, TypeError, IndexError, KeyError, InvalidOperation) as exc:
        raise HTTPException(422, f"Invalid progress workbook: {exc}") from exc
    except Exception as exc:
        raise HTTPException(422, "Unreadable progress XLSX workbook") from exc


def as_date(value: object) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def ingest_workbook(
    session: Session,
    actor: ActorContext,
    project: Project,
    data: ProgressWorkbookCreate,
    key: str,
    store: EvidenceStore,
) -> ProgressWorkbookImport:
    from zoneinfo import ZoneInfo

    project_lock(session, project)
    request_hash = digest(data.model_dump(mode="json"))
    existing = session.scalar(
        select(ProgressWorkbookImport).where(
            ProgressWorkbookImport.project_id == project.id,
            ProgressWorkbookImport.idempotency_key == key,
        )
    )
    if existing:
        if existing.request_hash != request_hash:
            raise HTTPException(409, "Idempotency key payload mismatch")
        return existing
    if data.data_date > datetime.now(UTC):
        raise HTTPException(422, "Progress cut-off cannot be future-dated")
    context = require_current_context(
        session, project, data.schedule_context_id, AuthorizedContextType.SCHEDULE, data.data_date
    )
    artifact = scoped_artifact(session, project, data.artifact_id)
    if not artifact.original_filename.lower().endswith(".xlsx") or artifact.scan_result != "CLEAN":
        raise HTTPException(422, "Use a scanned project XLSX evidence artifact")
    duplicate = session.scalar(
        select(ProgressWorkbookImport).where(
            ProgressWorkbookImport.project_id == project.id,
            ProgressWorkbookImport.artifact_id == artifact.id,
            ProgressWorkbookImport.schedule_context_id == context.id,
            ProgressWorkbookImport.data_date == data.data_date,
        )
    )
    if duplicate:
        raise HTTPException(409, "This artifact/cut-off/schedule has already been imported")
    content = store.get(artifact.storage_key)
    import hashlib

    if hashlib.sha256(content).hexdigest() != artifact.sha256:
        raise HTTPException(409, "Stored artifact hash mismatch")
    rows = parse_rows(content)
    mappings = {mapping.task_id: mapping for mapping in data.mappings}
    if set(mappings) != {row["task_id"] for row in rows}:
        raise HTTPException(422, "Exact mappings for every workbook task are required")
    activities = {activity["code"]: activity for activity in context.payload["activities"]}
    cutoff_date = data.data_date.astimezone(ZoneInfo(project.timezone)).date()
    result_rows = []
    for row in rows:
        mapping = mappings[row["task_id"]]
        activity = activities.get(mapping.activity_code)
        obj = session.get(ControlledObject, mapping.controlled_object_id)
        if (
            activity is None
            or obj is None
            or obj.project_id != project.id
            or not obj.active
            or obj.code != (activity.get("controlled_object_code") or activity["code"])
        ):
            raise HTTPException(
                422, "Mapping must name the exact authorized project activity/object"
            )
        if (
            activity["name"] != row["task_name"]
            or as_date(activity["planned_start"]) != row["start"]
            or as_date(activity["planned_finish"]) != row["finish"]
        ):
            raise HTTPException(
                422, "Workbook activity differs from the authorized schedule version"
            )
        calendar_id = activity.get("calendar_id", "PROJECT")
        calendar = next(
            (
                item
                for item in context.payload.get("calendars", [])
                if item["calendar_id"] == calendar_id
            ),
            None,
        )
        if calendar is None or not calendar.get("working_weekdays"):
            raise HTTPException(422, "An explicit authorized working calendar is required")
        reported = row["reported_percent"]
        if reported is not None and row["report_date"] != cutoff_date:
            raise HTTPException(
                422, "Each reported row must match the project-local reporting cut-off"
            )
        evidence_id = measurement_id = None
        if reported is not None:
            evidence = create_evidence_item(
                session,
                actor,
                project,
                EvidenceItemCreate(
                    artifact_id=artifact.id,
                    controlled_object_id=obj.id,
                    field_name="workbook_reported_progress",
                    value=str(reported),
                    unit="percent",
                    measurement_basis="REPORTED_PERCENT_COMPLETE",
                    semantic_state="REPORTED",
                    truth_type="REPORTED_CLAIM",
                    as_of=data.data_date,
                    confidence=data.reported_confidence,
                ),
            )
            session.flush()
            measurement = record_measurement(
                session,
                actor,
                project,
                ProgressMeasurementCreate(
                    evidence_item_id=evidence.id,
                    measurement_kind="REPORTED",
                    numerator=reported,
                    denominator=100,
                    unit="percent",
                ),
            )
            evidence_id, measurement_id = str(evidence.id), str(measurement.id)
        planned = next(
            (
                point["numerator"]
                for point in activity.get("progress_plan", [])
                if point["as_of"] == cutoff_date.isoformat()
                and point["measurement_basis"] == "REPORTED_PERCENT_COMPLETE"
                and Decimal(str(point["denominator"])) == 100
                and point["unit"] == "percent"
            ),
            None,
        )
        result_rows.append(
            {
                **row,
                "start": row["start"].isoformat(),
                "finish": row["finish"].isoformat(),
                "report_date": row["report_date"].isoformat() if row["report_date"] else None,
                "reported_percent": str(reported) if reported is not None else None,
                "activity_code": activity["code"],
                "controlled_object_id": str(obj.id),
                "evidence_item_id": evidence_id,
                "measurement_id": measurement_id,
                "planned_percent": str(planned) if planned is not None else None,
                "authorized_working_days_elapsed": str(
                    working_days_between(
                        row["start"] - timedelta(days=1), min(cutoff_date, row["finish"]), calendar
                    )
                ),
                "semantic_state": "REPORTED",
                "truth_type": "REPORTED_CLAIM" if reported is not None else "UNKNOWN",
            }
        )
    record = ProgressWorkbookImport(
        id=uuid.uuid4(),
        organization_id=project.organization_id,
        project_id=project.id,
        artifact_id=artifact.id,
        schedule_context_id=context.id,
        data_date=data.data_date,
        rows=result_rows,
        network_basis=context.payload,
        limitations=[
            {
                "code": "REPORTED_ONLY",
                "description": "Workbook claims require separate verification and acceptance.",
            },
            {
                "code": "DEADLINE_EXPOSURE_UNKNOWN",
                "description": (
                    "No max-task or calendar-day approximation is authoritative. "
                    "Use governed schedule assessment on verified evidence."
                ),
            },
        ],
        formula_version=FORMULA_VERSION,
        idempotency_key=key,
        request_hash=request_hash,
        recorded_by=actor.actor_id,
    )
    session.add(record)
    record_audit(
        session,
        actor,
        organization_id=project.organization_id,
        project_id=project.id,
        action="PROGRESS_WORKBOOK_IMPORTED",
        object_type="PROGRESS_WORKBOOK_IMPORT",
        object_id=str(record.id),
        details={
            "artifact_id": str(artifact.id),
            "schedule_context_id": str(context.id),
            "formula_version": FORMULA_VERSION,
        },
    )
    return record
