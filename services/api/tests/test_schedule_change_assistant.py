from __future__ import annotations

import io
import zipfile

import pytest
from app.services.ms_project_export import HEADERS
from app.services.schedule_change_assistant import _read_tasks, _validate_revision, _word_document
from openpyxl import Workbook


def _workbook() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Tasks"
    sheet.append(HEADERS)
    sheet.append([1, "Excavation", "5 days", "2026-10-01", "2026-10-05", None])
    sheet.append([2, "Concrete", "4 days", "2026-10-06", "2026-10-09", "1"])
    output = io.BytesIO()
    workbook.save(output)
    return output.getvalue()


def test_schedule_assistant_only_accepts_the_ms_project_import_contract() -> None:
    _, _, tasks = _read_tasks(_workbook())
    assert [task["id"] for task in tasks] == [1, 2]
    assert tasks[1]["dependency_ids"] == [1]


def test_schedule_assistant_rejects_task_identity_changes_and_cycles() -> None:
    _, _, tasks = _read_tasks(_workbook())
    renamed = [{key: value for key, value in task.items() if key != "row"} for task in tasks]
    renamed[0]["name"] = "Different scope"
    with pytest.raises(ValueError, match="name cannot"):
        _validate_revision(tasks, renamed)
    cyclic = [{key: value for key, value in task.items() if key != "row"} for task in tasks]
    cyclic[0]["dependency_ids"] = [2]
    with pytest.raises(ValueError, match="cycle"):
        _validate_revision(tasks, cyclic)


def test_schedule_assistant_word_report_is_a_valid_docx_package() -> None:
    content = _word_document(
        {
            "request": "Bring the finish forward",
            "summary": "Proposal",
            "feasibility": "CONDITIONAL",
            "construction_strategy": "Parallel fronts",
            "risks_and_constraints": ["Confirm access"],
            "evidence_gaps": ["Crew availability"],
            "planner_actions": ["Recalculate in MS Project"],
        },
        [
            {
                "id": 2,
                "name": "Concrete",
                "change": "duration",
                "rationale": "Split work front",
                "assumption": "Access is available",
            }
        ],
    )
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        assert "word/document.xml" in archive.namelist()
        assert b"VAI Schedule Change Proposal" in archive.read("word/document.xml")
