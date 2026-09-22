from __future__ import annotations

import io
import json
from datetime import date
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from app.config import get_settings
from app.services.ms_project_export import (
    build_ms_project_workbook,
    extract_pdf_text,
    parse_boq_items,
)
from app.services.openai_schedule import build_openai_schedule_workbook, create_openai_schedule

router = APIRouter(prefix="/api/v1/ms-project", tags=["ms-project"])
MAX_UPLOAD = 20 * 1024 * 1024
EXPOSE_HEADERS = ", ".join(
    ("X-VAI-Task-Count", "X-VAI-BOQ-Item-Count", "X-VAI-Proposed-Duration-Count")
)


@router.post("/generate-ai")
async def generate_ai_schedule(
    boq: Annotated[UploadFile, File()],
    project_start: Annotated[date, Form()],
    target_finish: Annotated[date | None, Form()] = None,
) -> StreamingResponse:
    settings = get_settings()
    if settings.environment not in {"development", "test"}:
        raise HTTPException(status_code=403, detail="Local AI scheduler is unavailable")
    if not boq.filename or not boq.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=422, detail="BOQ must be a PDF")
    if target_finish and target_finish <= project_start:
        raise HTTPException(status_code=422, detail="Target finish must follow project start")
    boq_bytes = await boq.read(MAX_UPLOAD + 1)
    if len(boq_bytes) > MAX_UPLOAD:
        raise HTTPException(status_code=413, detail="BOQ must be 20 MB or smaller")
    configured_key = settings.openai_api_key.get_secret_value() if settings.openai_api_key else None
    key = (configured_key or "").strip()
    if not key:
        raise HTTPException(
            status_code=503,
            detail="AI scheduling is not configured. Contact the system administrator.",
        )
    try:
        items = parse_boq_items(extract_pdf_text(boq_bytes))
        tasks = await create_openai_schedule(
            items,
            api_key=key,
            model=settings.openai_schedule_model,
            project_start=project_start,
            target_finish=target_finish,
        )
        content = build_openai_schedule_workbook(tasks)
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": 'attachment; filename="ai_boq_schedule.xlsx"',
            "X-VAI-Task-Count": str(len(tasks)),
            "X-VAI-Model": settings.openai_schedule_model,
            "Access-Control-Expose-Headers": "X-VAI-Task-Count, X-VAI-Model",
        },
    )


@router.post("/convert")
async def convert(
    boq: Annotated[UploadFile, File()],
    template: Annotated[UploadFile, File()],
    reuse_template_plan: Annotated[bool, Form()] = True,
    propose_missing_durations: Annotated[bool, Form()] = True,
) -> StreamingResponse:
    if get_settings().environment not in {"development", "test"}:
        raise HTTPException(
            status_code=403, detail="Local converter is unavailable in this environment"
        )
    if not boq.filename or not boq.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=422, detail="BOQ must be a PDF")
    if not template.filename or not template.filename.lower().endswith(".xlsx"):
        raise HTTPException(status_code=422, detail="Template must be an XLSX workbook")
    boq_bytes = await boq.read(MAX_UPLOAD + 1)
    template_bytes = await template.read(MAX_UPLOAD + 1)
    if len(boq_bytes) > MAX_UPLOAD or len(template_bytes) > MAX_UPLOAD:
        raise HTTPException(status_code=413, detail="Each file must be 20 MB or smaller")
    try:
        content, report = build_ms_project_workbook(
            extract_pdf_text(boq_bytes),
            template_bytes,
            reuse_template_plan=reuse_template_plan,
            propose_missing_durations=propose_missing_durations,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": 'attachment; filename="ms_project_schedule_from_boq.xlsx"',
            "X-VAI-Task-Count": str(report["tasks"]),
            "X-VAI-BOQ-Item-Count": str(report["boq_items"]),
            "X-VAI-Proposed-Duration-Count": str(report["proposed_durations"]),
            "Access-Control-Expose-Headers": EXPOSE_HEADERS,
        },
    )
