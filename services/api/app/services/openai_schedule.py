"""OpenAI-backed BOQ-to-schedule proposal with strict local validation."""

from __future__ import annotations

import io
import json
import uuid
from datetime import date
from typing import Any

import httpx
from app.services.ms_project_export import HEADERS, BoqItem, _safe_text
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

RESPONSES_URL = "https://api.openai.com/v1/responses"


def _schedule_schema() -> dict[str, Any]:
    task = {
        "type": "object",
        "properties": {
            "id": {"type": "integer", "minimum": 1},
            "name": {"type": "string", "minLength": 3},
            "duration_days": {"type": "integer", "minimum": 1},
            "start": {"type": "string"},
            "finish": {"type": "string"},
            "dependency_ids": {"type": "array", "items": {"type": "integer"}},
        },
        "required": ["id", "name", "duration_days", "start", "finish", "dependency_ids"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {"tasks": {"type": "array", "minItems": 5, "items": task}},
        "required": ["tasks"],
        "additionalProperties": False,
    }


def _boq_prompt(items: list[BoqItem], project_start: date, target_finish: date | None) -> str:
    rows = "\n".join(
        f"{item.reference} | {item.number} | {item.description} | {item.unit} | "
        f"{item.quantity if item.quantity is not None else 'unknown'}"
        for item in items
    )
    finish_instruction = (
        f"The required completion date is {target_finish.isoformat()}."
        if target_finish
        else "Propose a realistic completion date from the scope and sequencing."
    )
    return f"""Create a construction time-schedule proposal from this BOQ.
Project start: {project_start.isoformat()}. {finish_instruction}

Return schedule subdivisions/work packages, not one task per BOQ commercial line. Consolidate
related measured items into recognizable executable activities. Include mobilization, design or
submittal approvals, procurement/delivery where material, construction sequences by discipline,
testing/commissioning, snagging, and handover when supported by scope. Use realistic working-day
durations based on quantities, typical construction productivity, access, cure/lead time, and
reasonable parallel crews. Dependencies must reference earlier task IDs only. Dates must be ISO
YYYY-MM-DD and internally consistent. Do not copy or paraphrase every BOQ row. This is a proposal
requiring planner review, not an authorized baseline.

BOQ measured scope:
{rows}"""


async def create_openai_schedule(
    items: list[BoqItem],
    *,
    api_key: str,
    model: str,
    project_start: date,
    target_finish: date | None,
) -> list[dict[str, Any]]:
    body = {
        "model": model,
        "instructions": (
            "You are a senior construction planner. Transform BOQ evidence into a concise, "
            "logically linked schedule proposal. Respect the requested structured schema exactly."
        ),
        "input": _boq_prompt(items, project_start, target_finish),
        "text": {
            "format": {
                "type": "json_schema",
                "name": "boq_schedule",
                "strict": True,
                "schema": _schedule_schema(),
            }
        },
        "max_output_tokens": 20000,
    }
    async with httpx.AsyncClient(timeout=180) as client:
        response = await client.post(
            RESPONSES_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=body,
        )
    if response.status_code >= 400:
        detail = response.json().get("error", {}).get("message", response.text[:500])
        raise ValueError(f"OpenAI schedule generation failed: {detail}")
    payload = response.json()
    output_text = next(
        (
            content.get("text")
            for item in payload.get("output", [])
            for content in item.get("content", [])
            if content.get("type") == "output_text"
        ),
        None,
    )
    if not output_text:
        raise ValueError("OpenAI returned no structured schedule")
    tasks = json.loads(output_text)["tasks"]
    _validate_tasks(tasks, project_start, target_finish)
    return tasks


def _validate_tasks(
    tasks: list[dict[str, Any]], project_start: date, target_finish: date | None
) -> None:
    ids = [task["id"] for task in tasks]
    if ids != list(range(1, len(tasks) + 1)):
        raise ValueError("OpenAI schedule IDs must be consecutive from 1")
    names: set[str] = set()
    for task in tasks:
        normalized = " ".join(task["name"].casefold().split())
        if normalized in names:
            raise ValueError(f"OpenAI schedule contains duplicate subdivision: {task['name']}")
        names.add(normalized)
        start = date.fromisoformat(task["start"])
        finish = date.fromisoformat(task["finish"])
        if start < project_start or finish < start:
            raise ValueError(f"Invalid dates for schedule task {task['id']}")
        if target_finish and finish > target_finish:
            raise ValueError(f"Schedule task {task['id']} exceeds the required completion date")
        if any(dependency >= task["id"] or dependency < 1 for dependency in task["dependency_ids"]):
            raise ValueError(f"Invalid dependency for schedule task {task['id']}")


def build_openai_schedule_workbook(tasks: list[dict[str, Any]]) -> bytes:
    """Create the application-owned MS Project import contract.

    Customers supply project data, never an executable workbook template. Keeping
    the six-column projection here makes the export identical across tenants.
    """
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Tasks"
    sheet.append(HEADERS)
    for task in tasks:
        sheet.append(
            (
                task["id"],
                _safe_text(task["name"]),
                f"{task['duration_days']} days",
                task["start"],
                task["finish"],
                ",".join(str(value) for value in task["dependency_ids"]) or None,
            )
        )
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = f"A1:F{sheet.max_row}"
    for cell in sheet[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="6E1E36")
        cell.alignment = Alignment(horizontal="center")
    for column, width in {"A": 10, "B": 62, "C": 16, "D": 18, "E": 18, "F": 20}.items():
        sheet.column_dimensions[column].width = width
    output = io.BytesIO()
    workbook.save(output)
    return output.getvalue()


def generation_id() -> str:
    return str(uuid.uuid4())
