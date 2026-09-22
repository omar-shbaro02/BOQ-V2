from __future__ import annotations

import io

from app.services.ms_project_export import HEADERS, build_ms_project_workbook, parse_boq_items
from app.services.openai_schedule import build_openai_schedule_workbook
from openpyxl import Workbook, load_workbook


def _template() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Tasks"
    sheet.append(HEADERS)
    sheet.append([1, "Dismantle Steel Doors", "4 days", "August 16, 2026", "August 19, 2026", None])
    sheet.append([2, "Other task", "2 days", "August 20, 2026", "August 21, 2026", "1"])
    output = io.BytesIO()
    workbook.save(output)
    return output.getvalue()


def test_boq_scope_is_not_duplicated_as_a_second_task_schedule() -> None:
    text = "1.1 Dismantle Steel Doors  No. 2\n1.2 Lay asphalt surface  m2  30\n"
    assert len(parse_boq_items(text)) == 2
    content, report = build_ms_project_workbook(text, _template())
    workbook = load_workbook(io.BytesIO(content), read_only=True)
    rows = list(workbook["Tasks"].values)
    assert rows[0] == HEADERS
    assert [row[0] for row in rows[1:]] == list(range(1, len(rows)))
    assert rows[2][5] == "1"
    assert not any(row[1] == "Lay asphalt surface" for row in rows[1:])
    assert report["boq_items"] == 2
    assert report["proposed_durations"] == 0
    progress_rows = list(workbook["Progress Report"].values)
    assert progress_rows[3] == (
        "Subdivision",
        "Task ID",
        "Task Name",
        "Proposed Duration",
        "Planned Start",
        "Planned Finish",
        "Work Complete %",
        "Reporting Date",
        "Remarks",
        "Evidence Reference",
        "Responsible Party",
        "Planning Basis",
    )
    assert not any(row[2] == "Lay asphalt surface" for row in progress_rows[4:])
    review_rows = list(workbook["BOQ Review"].values)
    assert any(row[0] == "p1:1.2" and row[1] == "Lay asphalt surface" for row in review_rows)


def test_layout_only_leaves_all_planning_fields_blank() -> None:
    content, _ = build_ms_project_workbook(
        "1.1 Lay asphalt surface  m2  30",
        _template(),
        reuse_template_plan=False,
        propose_missing_durations=False,
    )
    rows = list(load_workbook(io.BytesIO(content), read_only=True)["Tasks"].values)
    assert rows[1] == (1, "Lay asphalt surface", None, None, None, None)


def test_generated_output_cannot_be_reused_as_a_template() -> None:
    content, _ = build_ms_project_workbook("1.1 Dismantle Steel Doors  No. 2", _template())
    try:
        build_ms_project_workbook("1.1 Dismantle Steel Doors  No. 2", content)
    except ValueError as exc:
        assert "generated output workbook" in str(exc)
    else:
        raise AssertionError("Generated output was incorrectly accepted as a workflow template")


def test_incompatible_workflow_fails_instead_of_appending_boq_lines() -> None:
    text = "\n".join(
        f"{index}.1 Unrelated measured scope {index}  m2  {index * 10}" for index in range(1, 21)
    )
    try:
        build_ms_project_workbook(text, _template())
    except ValueError as exc:
        assert "not compatible with this BOQ" in str(exc)
    else:
        raise AssertionError("Incompatible workflow was incorrectly presented as a schedule")


def test_openai_schedule_export_uses_only_six_column_tasks_sheet() -> None:
    content = build_openai_schedule_workbook(
        [
            {
                "id": 1,
                "name": "Mobilization",
                "duration_days": 10,
                "start": "2026-10-01",
                "finish": "2026-10-10",
                "dependency_ids": [],
            },
            {
                "id": 2,
                "name": "Substructure",
                "duration_days": 30,
                "start": "2026-10-11",
                "finish": "2026-11-09",
                "dependency_ids": [1],
            },
        ],
    )
    workbook = load_workbook(io.BytesIO(content), read_only=True)
    assert workbook.sheetnames == ["Tasks"]
    assert list(workbook["Tasks"].values) == [
        HEADERS,
        (1, "Mobilization", "10 days", "2026-10-01", "2026-10-10", None),
        (2, "Substructure", "30 days", "2026-10-11", "2026-11-09", "1"),
    ]


def test_customer_ai_endpoint_accepts_neither_api_key_nor_template() -> None:
    import inspect

    from app.routers.ms_project import generate_ai_schedule

    parameters = inspect.signature(generate_ai_schedule).parameters
    assert "openai_api_key" not in parameters
    assert "template" not in parameters
