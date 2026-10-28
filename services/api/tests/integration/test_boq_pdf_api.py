import shutil
import uuid

import pytest
from app.services import boq_pdf
from test_boq_pdf import HEADER, layout_page, text_pdf
from test_evidence_api import bootstrap
from test_evidence_api import evidence_api as evidence_api


@pytest.mark.parametrize("mode", ["table", "mixed", "unmapped", "unavailable", "real"])
def test_pdf_boq_preserves_source_lineage_and_gates_incomplete_extraction(
    evidence_api, monkeypatch, mode
):
    if mode == "real" and not shutil.which("pdftotext"):
        pytest.skip("Requires local Poppler executable")
    client, _ = evidence_api
    _, project_id, headers, _ = bootstrap(client)
    page = layout_page(
        [HEADER, [(50, "C-01"), (100, "Concrete foundations"), (400, "120"), (480, "m3")]]
    )
    if mode == "unavailable":

        def unavailable(content):
            raise boq_pdf.PdfExtractionUnavailable("PDF text extraction is unavailable")

        monkeypatch.setattr(boq_pdf, "_layout", unavailable)
    elif mode != "real":
        if mode == "mixed":
            page += '<page width="600" height="800"/>'
        elif mode == "unmapped":
            page = layout_page([[(50, "Scope whose columns need review")]])
        monkeypatch.setattr(boq_pdf, "_layout", lambda content: f"<html>{page}</html>".encode())
    base = f"/api/v1/projects/{project_id}"
    content = text_pdf()
    artifact = client.post(
        f"{base}/evidence/artifacts",
        headers=headers,
        data={"source_type": "BOQ", "source_id": "native-pdf-1"},
        files={"upload": ("boq.pdf", content, "application/pdf")},
    )
    assert artifact.status_code == 201, artifact.text
    source_request = {"artifact_id": artifact.json()["id"]}
    source = client.post(
        f"{base}/bootstrap/boq-sources",
        headers={**headers, "Idempotency-Key": "pdf-source"},
        json=source_request,
    )
    assert source.status_code == 201, source.text
    record = source.json()
    assert record["parser_name"] == "VAI_BOQ_PDF_TEXT"
    assert record["parser_version"] == "1.0.0"
    assert record["content_sha256"] == artifact.json()["sha256"]
    ready = mode in {"table", "real"}
    assert record["extraction_status"] == ("EXTRACTED" if ready else "VERIFICATION_REQUIRED")
    assert record["extraction_confidence"] == ("0.7500" if ready else "0.0000")
    replay = client.post(
        f"{base}/bootstrap/boq-sources",
        headers={**headers, "Idempotency-Key": "pdf-source"},
        json=source_request,
    )
    assert replay.status_code == 201
    assert replay.json()["id"] == record["id"]
    path = f"{base}/bootstrap/boq-sources/{record['id']}"
    detail = client.get(path, headers=headers)
    assert detail.status_code == 200, detail.text
    retained = detail.json()["rows"]
    assert len(retained) == record["extracted_row_count"]
    assert all(row["page_number"] and row["original_text"] for row in retained)
    assert (
        client.get(
            path, headers={**headers, "X-VAI-Organization-ID": str(uuid.uuid4())}
        ).status_code
        == 403
    )
    normalized = client.post(
        f"{path}/normalizations",
        headers={**headers, "Idempotency-Key": "pdf-normalize"},
        json={},
    )
    if not ready:
        assert normalized.status_code == 422
        if mode == "mixed":
            assert record["extracted_row_count"] == 2
            assert record["structure_manifest"][1]["warnings"][0]["code"] == "PDF_PAGE_REQUIRES_OCR"
        return
    assert normalized.status_code == 201, normalized.text
    lines = client.get(f"{path}/normalization", headers=headers).json()["lines"]
    concrete = [line for line in lines if line["classification"] == "DIRECT_EXECUTION_SCOPE"]
    assert len(concrete) == (4 if mode == "real" else 1)
    assert concrete[0]["quantity"] == "120.000000"
    assert concrete[0]["unit"] == "m3"
    assert concrete[0]["review_state"] == "REVIEW_REQUIRED"
    assert all(line["confidence"] != "HIGH" for line in lines)
    assert all(line["source_location"]["region"]["words"] for line in lines)
    assert len({line["stable_line_id"] for line in lines}) == len(lines)
    assert (
        client.get(f"{base}/authorized-context/current/SCHEDULE", headers=headers).status_code
        == 404
    )
