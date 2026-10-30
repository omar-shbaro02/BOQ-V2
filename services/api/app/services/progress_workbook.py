"""Deterministic review of the editable Progress Report in a VAI schedule workbook."""

from __future__ import annotations

import io
import re
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from app.archive_limits import load_workbook
from app.services.ms_project_export import HEADERS
from app.services.progress_columns import progress_input_rows


def _date(value: object, label: str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value).strip())
    except ValueError as exc:
        raise ValueError(f"{label} must be a valid Excel or ISO date") from exc


def _duration(value: object) -> int:
    match = re.search(r"\d+", str(value or ""))
    if not match or int(match.group()) < 1:
        raise ValueError("Every progress row must have a positive proposed duration")
    return int(match.group())


def analyze_progress_workbook(content: bytes, as_of: date) -> dict[str, Any]:
    try:
        workbook = load_workbook(io.BytesIO(content), data_only=True, read_only=True)
    except Exception as exc:  # openpyxl raises several format-specific exceptions
        raise ValueError("The uploaded file is not a readable XLSX workbook") from exc
    if "Tasks" not in workbook or "Progress Report" not in workbook:
        raise ValueError("Use a VAI schedule workbook containing Tasks and Progress Report sheets")
    tasks = workbook["Tasks"]
    if tuple(cell.value for cell in tasks[1][:6]) != HEADERS:
        raise ValueError("The Tasks sheet does not match the VAI six-column schedule contract")
    task_ids = {
        int(row[0]) for row in tasks.iter_rows(min_row=2, values_only=True) if row[0] is not None
    }
    progress = workbook["Progress Report"]

    rows: list[dict[str, Any]] = []
    seen: set[int] = set()
    for values in progress_input_rows(progress):
        if values[1] is None:
            continue
        task_id = int(values[1])
        if task_id not in task_ids or task_id in seen:
            raise ValueError(f"Progress row Task ID {task_id} is missing or duplicated")
        seen.add(task_id)
        start, finish = _date(values[4], "Planned Start"), _date(values[5], "Planned Finish")
        duration = _duration(values[3])
        raw_actual = values[6]
        actual = None if raw_actual in (None, "") else float(raw_actual)
        if actual is not None and not 0 <= actual <= 100:
            raise ValueError(f"Task {task_id} Work Complete % must be from 0 to 100")
        if as_of < start:
            planned = 0.0
        elif as_of >= finish:
            planned = 100.0
        else:
            elapsed = max(0, (as_of - start).days + 1)
            total = max(1, (finish - start).days + 1)
            planned = min(100.0, elapsed / total * 100)
        if actual is None:
            status = "NOT REPORTED"
            variance_days = None
        else:
            variance = actual - planned
            status = "EARLY" if variance > 5 else "LATE" if variance < -5 else "ON TIME"
            variance_days = float(
                (Decimal(str(variance)) / 100 * duration).quantize(
                    Decimal("0.1"), rounding=ROUND_HALF_UP
                )
            )
        evidence = str(values[9] or "").strip()
        rows.append(
            {
                "task_id": task_id,
                "subdivision": str(values[0] or ""),
                "task_name": str(values[2] or ""),
                "planned_percent": round(planned, 1),
                "reported_percent": actual,
                "status": status,
                "schedule_variance_days": variance_days,
                "evidence_reference": evidence or None,
                "evidence_state": "EVIDENCE REFERENCED" if evidence else "REPORTED ONLY",
                "recommendation": _recommendation(status, evidence),
            }
        )
    if seen != task_ids:
        missing = ", ".join(str(item) for item in sorted(task_ids - seen)[:10])
        raise ValueError(f"Progress Report is missing schedule Task IDs: {missing}")
    counts = {
        status: sum(row["status"] == status for row in rows)
        for status in ("EARLY", "ON TIME", "LATE", "NOT REPORTED")
    }
    synthetic_sample = False
    if "Progress Template Metadata" in workbook:
        metadata = dict(
            workbook["Progress Template Metadata"].iter_rows(min_row=2, max_col=2, values_only=True)
        )
        synthetic_sample = metadata.get("mode") == "SYNTHETIC_SAMPLE"
    late_days = [
        abs(row["schedule_variance_days"])
        for row in rows
        if row["status"] == "LATE" and row["schedule_variance_days"] is not None
    ]
    return {
        "mode": "UNPERSISTED_PREVIEW",
        "semantic_notice": (
            ("Fictional sample data for testing only. " if synthetic_sample else "")
            + "Workbook-only approximation; not authorized progress, verification, "
            "or a deadline forecast."
        ),
        "as_of": as_of.isoformat(),
        "counts": counts,
        "potential_deadline_exposure_days": max(late_days, default=0),
        "deadline_basis": (
            "Provisional scenario using task progress variance. Confirm critical path, float, "
            "calendar and evidence in Microsoft Project before treating it as a deadline forecast."
        ),
        "rows": rows,
    }


def _recommendation(status: str, evidence: str) -> str:
    if status == "LATE":
        prefix = (
            "Verify the reported quantity and evidence. "
            if not evidence
            else "Review the cited evidence. "
        )
        return prefix + (
            "Check prerequisites, available work fronts and successor logic; use the "
            "schedule-change assistant for a reviewed recovery proposal."
        )
    if status == "EARLY":
        return (
            "Confirm the gain is evidenced and that successor access, inspections and "
            "approvals can support the earlier handover."
        )
    if status == "ON TIME":
        return (
            "Maintain the current sequence and update the evidence reference at the next "
            "reporting cut-off."
        )
    return (
        "Enter the observed completion percentage and reporting evidence before drawing a "
        "schedule conclusion."
    )
