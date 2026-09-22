"""BOQ-to-MS-Project spreadsheet projection.

The supplied workbook is a planning reference, not authorization. Its six-column
Tasks layout is preserved, while source matching and corrections remain visible
on a separate review sheet.
"""

from __future__ import annotations

import argparse
import io
import math
import re
import subprocess
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from openpyxl import load_workbook
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

HEADERS = ("ID", "Name", "Duration", "Start", "Finish", "Dependency")
PROGRESS_HEADERS = (
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
ITEM_RE = re.compile(r"^\s*(?P<number>\d+(?:\.\d+){1,5})\s+(?P<body>.*)$")
UNIT_QTY_RE = re.compile(
    r"\s{2,}(?P<unit>m2|m3|m²|m³|Lm|lm|Ton|ton|Kg|kg|No\.?|Item|LS|Set|Unit|Nos\.?)"
    r"\s+(?P<quantity>[\d,]+(?:\.\d+)?|Included)(?=\s|$)",
    re.IGNORECASE,
)
STOPWORDS = {
    "a",
    "all",
    "and",
    "at",
    "by",
    "for",
    "from",
    "in",
    "including",
    "install",
    "installation",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
    "work",
    "works",
    "new",
    "supply",
    "construct",
    "construction",
    "execution",
    "execute",
    "material",
    "submittal",
    "procurement",
    "coordination",
    "fabrication",
    "testing",
    "test",
    "commissioning",
    "handover",
    "inspection",
    "signoff",
    "setting",
    "preparation",
    "first",
    "fix",
    "curing",
    "phase",
    "batch",
}
NON_SCHEDULE_WORDS = (
    "insurance",
    "monthly progress report",
    "program of works",
    "project billboard",
    "price summary",
    "carried to",
    "provisional sum",
)


@dataclass(frozen=True)
class BoqItem:
    number: str
    description: str
    unit: str
    quantity: Decimal | None
    page: int

    @property
    def reference(self) -> str:
        return f"p{self.page}:{self.number}"


def extract_pdf_text(content: bytes) -> str:
    if not content.startswith(b"%PDF-"):
        raise ValueError("BOQ must be a PDF file")
    try:
        result = subprocess.run(
            ["pdftotext", "-layout", "-enc", "UTF-8", "-", "-"],
            input=content,
            capture_output=True,
            check=False,
            timeout=60,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        raise ValueError("PDF text extraction is unavailable") from exc
    if result.returncode != 0:
        raise ValueError("PDF text extraction failed")
    text = result.stdout.decode("utf-8", errors="replace")
    if len(text.strip()) < 100:
        raise ValueError("No extractable BOQ text found; scanned PDF requires OCR")
    return text


def parse_boq_items(text: str) -> list[BoqItem]:
    items: list[BoqItem] = []
    for page_number, page in enumerate(text.split("\f"), start=1):
        previous_text = ""
        for line in page.splitlines():
            item_match = ITEM_RE.match(line)
            if not item_match:
                if line.strip() and not re.search(r"Bill of Quantities|CHAPTER|PART\s", line):
                    previous_text = line.strip()
                continue
            body = item_match.group("body")
            unit_match = UNIT_QTY_RE.search(body)
            if unit_match is None:
                previous_text = ""
                continue
            description = body[: unit_match.start()].strip(" :.-")
            if not description and previous_text:
                description = previous_text.strip(" :.-")
            previous_text = ""
            if not description:
                continue
            raw_quantity = unit_match.group("quantity")
            try:
                quantity = Decimal(raw_quantity.replace(",", ""))
            except InvalidOperation:
                quantity = None
            items.append(
                BoqItem(
                    number=item_match.group("number"),
                    description=" ".join(description.split()),
                    unit=unit_match.group("unit"),
                    quantity=quantity,
                    page=page_number,
                )
            )
    if not items:
        raise ValueError("No measurable BOQ item rows could be extracted from this PDF")
    return items


def _tokens(value: str) -> set[str]:
    normalized = unicodedata.normalize("NFKD", value).casefold()
    normalized = "".join(
        character for character in normalized if not unicodedata.combining(character)
    )
    return {
        token
        for token in re.findall(r"[a-z]+\d*[a-z\d]*|\d+[a-z\d]*", normalized)
        if token not in STOPWORDS and len(token) > 1
    }


def _score(task_name: str, item: BoqItem) -> float:
    task_tokens = _tokens(task_name)
    item_tokens = _tokens(item.description)
    if not task_tokens or not item_tokens:
        return 0.0
    overlap = task_tokens & item_tokens
    if not overlap:
        return 0.0
    coverage = len(overlap) / min(len(task_tokens), len(item_tokens))
    jaccard = len(overlap) / len(task_tokens | item_tokens)
    sequence = SequenceMatcher(
        None, " ".join(sorted(task_tokens)), " ".join(sorted(item_tokens))
    ).ratio()
    return round(0.45 * coverage + 0.35 * jaccard + 0.20 * sequence, 3)


def _safe_text(value: str) -> str:
    return f"'{value}" if value.startswith(("=", "+", "-", "@")) else value


def _duration_days(value: Any) -> int | None:
    match = re.search(r"(\d+(?:\.\d+)?)", str(value or ""))
    return max(1, math.ceil(float(match.group(1)))) if match else None


def _proposed_duration(item: BoqItem, reference_rows: list[tuple[Any, ...]]) -> tuple[int, str]:
    """Return a visibly provisional duration; it never represents planner approval."""
    analogues = sorted(
        ((_score(str(row[1]), item), row) for row in reference_rows if _duration_days(row[2])),
        key=lambda pair: pair[0],
        reverse=True,
    )
    if analogues and analogues[0][0] >= 0.30:
        score, row = analogues[0]
        return _duration_days(
            row[2]
        ) or 1, f"ANALOGOUS_TEMPLATE_TASK · {row[1]} · confidence {score:.3f}"

    # Controlled fallback rates are intentionally conservative planning assumptions.
    # They are surfaced in the workbook and require planner confirmation.
    unit = item.unit.casefold().replace("²", "2").replace("³", "3").rstrip(".")
    rates = {
        "m2": Decimal("20"),
        "m3": Decimal("8"),
        "lm": Decimal("20"),
        "kg": Decimal("400"),
        "ton": Decimal("4"),
        "no": Decimal("4"),
        "nos": Decimal("4"),
        "unit": Decimal("4"),
        "set": Decimal("2"),
        "item": Decimal("1"),
        "ls": Decimal("1"),
    }
    rate = rates.get(unit, Decimal("1"))
    quantity = item.quantity or Decimal("1")
    duration = max(1, math.ceil(float(quantity / rate)))
    return (
        duration,
        "DEFAULT_PRODUCTIVITY_ASSUMPTION · "
        f"{rate.normalize()} {item.unit}/working day · LOW confidence",
    )


def build_ms_project_workbook(
    boq_text: str,
    template_content: bytes,
    *,
    reuse_template_plan: bool = True,
    propose_missing_durations: bool = True,
) -> tuple[bytes, dict[str, int]]:
    items = parse_boq_items(boq_text)
    try:
        workbook = load_workbook(io.BytesIO(template_content))
    except Exception as exc:
        raise ValueError("Template must be a readable XLSX workbook") from exc
    if "Tasks" not in workbook.sheetnames:
        raise ValueError("Template must contain a Tasks sheet")
    if "BOQ Review" in workbook.sheetnames:
        raise ValueError(
            "This is a generated output workbook, not a clean workflow template. "
            "Choose the original project workflow XLSX."
        )
    tasks = workbook["Tasks"]
    if tuple(tasks.cell(1, column).value for column in range(1, 7)) != HEADERS:
        raise ValueError(
            "Template Tasks headers must be ID, Name, Duration, Start, Finish, Dependency"
        )
    reference_rows = [
        tuple(tasks.cell(row, column).value for column in range(1, 7))
        for row in range(2, tasks.max_row + 1)
        if tasks.cell(row, 2).value
    ]
    if reuse_template_plan and not reference_rows:
        raise ValueError("Template has no planning rows to reuse")

    planning_basis: dict[int, str] = {}
    if reuse_template_plan:
        old_id_positions: dict[str, list[int]] = defaultdict(list)
        for position, row in enumerate(reference_rows, start=1):
            old_id_positions[str(row[0])].append(position)
        output_rows: list[tuple[Any, ...]] = []
        dependency_warnings = 0
        for position, row in enumerate(reference_rows, start=1):
            predecessors: list[int] = []
            for raw_id in str(row[5] or "").split(","):
                old_id = raw_id.strip()
                if not old_id:
                    continue
                earlier = [
                    candidate
                    for candidate in old_id_positions.get(old_id, [])
                    if candidate < position
                ]
                if not earlier:
                    dependency_warnings += 1
                    continue
                if len(old_id_positions[old_id]) > 1:
                    dependency_warnings += 1
                predecessor = earlier[-1]
                if predecessor not in predecessors:
                    predecessors.append(predecessor)
            output_rows.append(
                (
                    position,
                    _safe_text(str(row[1])),
                    row[2],
                    row[3],
                    row[4],
                    ",".join(str(value) for value in predecessors) or None,
                )
            )
            planning_basis[position] = "SAVED_WORKFLOW_TEMPLATE · requires planner confirmation"
    else:
        eligible = [
            item
            for item in items
            if item.quantity is not None
            and not any(term in item.description.casefold() for term in NON_SCHEDULE_WORDS)
        ]
        output_rows = []
        for position, item in enumerate(eligible, start=1):
            duration, basis = (
                _proposed_duration(item, reference_rows)
                if propose_missing_durations
                else (None, "UNRESOLVED")
            )
            output_rows.append(
                (
                    position,
                    _safe_text(item.description),
                    f"{duration} days" if duration else None,
                    None,
                    None,
                    None,
                )
            )
            planning_basis[position] = basis
        dependency_warnings = 0

    if tasks.max_row > 1:
        tasks.delete_rows(2, tasks.max_row - 1)
    for row in output_rows:
        tasks.append(row)

    review = (
        workbook.create_sheet("BOQ Review")
        if "BOQ Review" not in workbook
        else workbook["BOQ Review"]
    )
    review.append(
        [
            "PROPOSAL ONLY",
            "BOQ text is source evidence; timing and logic come from the supplied "
            "example workbook when reused.",
        ]
    )
    review.append(
        ["Import", "Import only the Tasks sheet into MS Project. Map Dependency to Predecessors."]
    )
    review.append(
        [
            "Warning",
            "Blank timing in layout-only mode requires planner input; "
            "no duration or date was invented.",
        ]
    )
    review.append(
        [
            "Task ID",
            "Task Name",
            "BOQ Ref",
            "BOQ Description",
            "Unit",
            "Quantity",
            "PDF Page",
            "Match Score",
            "Review Status",
            "Duration / planning basis",
        ]
    )
    matched_refs: set[str] = set()
    match_count = 0
    review_count = 0
    for task_id, task_name, *_ in output_rows:
        ranked = sorted(
            ((_score(str(task_name), item), item) for item in items),
            key=lambda pair: pair[0],
            reverse=True,
        )
        top_score, top_item = ranked[0]
        second_score = ranked[1][0] if len(ranked) > 1 else 0.0
        if top_score >= 0.70 and top_score - second_score >= 0.045:
            state = "MATCHED"
            match_count += 1
            matched_refs.add(top_item.reference)
        elif top_score >= 0.45:
            state = "REVIEW_MATCH"
            review_count += 1
        else:
            state = "UNMATCHED_TEMPLATE_TASK" if reuse_template_plan else "BOQ_TASK"
        review.append(
            [
                task_id,
                task_name,
                top_item.reference if top_score >= 0.45 else None,
                top_item.description if top_score >= 0.45 else None,
                top_item.unit if top_score >= 0.45 else None,
                str(top_item.quantity)
                if top_score >= 0.45 and top_item.quantity is not None
                else None,
                top_item.page if top_score >= 0.45 else None,
                top_score,
                state,
                planning_basis.get(int(task_id), "UNRESOLVED"),
            ]
        )
    unscheduled_items = [
        item for item in items if item.quantity is not None and item.reference not in matched_refs
    ]
    coverage = len(matched_refs) / len(items)
    if reuse_template_plan and len(items) >= 20 and coverage < 0.10:
        raise ValueError(
            "Workflow template is not compatible with this BOQ: only "
            f"{len(matched_refs)} of {len(items)} measured lines mapped confidently. "
            "Choose the correct project workflow or build consolidated work packages; "
            "the converter will not append BOQ lines as a fake second schedule."
        )
    # BOQ commercial lines are not a second activity list. Unmatched scope remains
    # visible below for package-level planning instead of being appended as hundreds
    # of paraphrased, unlinked tasks.
    review.append([])
    review.append(["BOQ items needing planner timing and scope review"])
    review.append(["BOQ Ref", "Description", "Unit", "Quantity", "PDF Page"])
    for item in unscheduled_items:
        if item.quantity is not None:
            review.append(
                [
                    item.reference,
                    _safe_text(item.description),
                    item.unit,
                    str(item.quantity),
                    item.page,
                ]
            )
    review.append([])
    review.append(
        [
            "Coverage warning",
            f"{len(unscheduled_items)} of {len(items)} BOQ lines are not confidently mapped. "
            "Create consolidated work packages before treating this as a complete schedule.",
        ]
    )
    review.append([])
    review.append(["Numbered PDF lines not parsed as measured BOQ items; check for omissions"])
    review.append(["PDF Page", "Item Number", "Raw PDF text"])
    for page_number, page in enumerate(boq_text.split("\f"), start=1):
        for line in page.splitlines():
            number_match = ITEM_RE.match(line)
            if number_match and UNIT_QTY_RE.search(number_match.group("body")) is None:
                review.append([page_number, number_match.group("number"), _safe_text(line.strip())])
    review.freeze_panes = "A5"
    review.auto_filter.ref = f"A4:J{4 + len(output_rows)}"
    for cell in review[4]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="24405C")
        cell.alignment = Alignment(wrap_text=True)
    for column, width in {
        "A": 14,
        "B": 54,
        "C": 20,
        "D": 70,
        "E": 12,
        "F": 14,
        "G": 12,
        "H": 14,
        "I": 24,
        "J": 66,
    }.items():
        review.column_dimensions[column].width = width

    progress = (
        workbook["Progress Report"]
        if "Progress Report" in workbook
        else workbook.create_sheet("Progress Report")
    )
    if progress.max_row:
        progress.delete_rows(1, progress.max_row)
    progress.append(
        [
            "PROGRESS INPUT",
            "Enter only observed progress. A percentage is reported information "
            "until supported and verified.",
        ]
    )
    progress.append(
        [
            "Project schedule",
            "Proposal-only tasks and durations remain subject to planner approval.",
        ]
    )
    progress.append([])
    progress.append(PROGRESS_HEADERS)
    item_by_description = {item.description: item for item in items}
    for task_id, task_name, duration, start, finish, _dependency in output_rows:
        plain_name = str(task_name).lstrip("'")
        item = item_by_description.get(plain_name)
        subdivision = item.number.split(".")[0] if item else "WORKFLOW"
        progress.append(
            [
                subdivision,
                task_id,
                task_name,
                duration,
                start,
                finish,
                None,
                None,
                None,
                None,
                None,
                planning_basis.get(int(task_id), "SAVED_WORKFLOW_TEMPLATE"),
            ]
        )
    percent_validation = DataValidation(
        type="decimal", operator="between", formula1="0", formula2="100", allow_blank=True
    )
    percent_validation.error = "Enter a percentage from 0 to 100."
    percent_validation.errorTitle = "Invalid progress percentage"
    progress.add_data_validation(percent_validation)
    percent_validation.add(f"G5:G{progress.max_row}")
    progress.conditional_formatting.add(
        f"G5:G{progress.max_row}",
        CellIsRule(
            operator="greaterThan", formula=["100"], fill=PatternFill("solid", fgColor="FFC7CE")
        ),
    )
    progress.freeze_panes = "A5"
    progress.auto_filter.ref = f"A4:L{progress.max_row}"
    for cell in progress[4]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="7A1735")
        cell.alignment = Alignment(wrap_text=True)
    for column, width in {
        "A": 14,
        "B": 10,
        "C": 52,
        "D": 18,
        "E": 18,
        "F": 18,
        "G": 18,
        "H": 18,
        "I": 40,
        "J": 26,
        "K": 24,
        "L": 66,
    }.items():
        progress.column_dimensions[column].width = width

    output = io.BytesIO()
    workbook.save(output)
    return output.getvalue(), {
        "tasks": len(output_rows),
        "boq_items": len(items),
        "matched_tasks": match_count,
        "review_matches": review_count,
        "dependency_warnings": dependency_warnings,
        "proposed_durations": sum(
            1 for basis in planning_basis.values() if "ASSUMPTION" in basis or "ANALOGOUS" in basis
        ),
        "confidently_mapped_boq_lines": len(matched_refs),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create an MS Project import workbook from a BOQ")
    parser.add_argument("--boq", type=Path, required=True)
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--layout-only", action="store_true")
    arguments = parser.parse_args()
    data, report = build_ms_project_workbook(
        extract_pdf_text(arguments.boq.read_bytes()),
        arguments.template.read_bytes(),
        reuse_template_plan=not arguments.layout_only,
    )
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_bytes(data)
    print(report)
