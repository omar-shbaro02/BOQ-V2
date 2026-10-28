import shutil
from decimal import Decimal
from pathlib import Path
from xml.sax.saxutils import escape

import pytest
from app.services import boq_pdf
from app.services.bootstrap import HEADER_ALIASES


def layout_page(lines):
    content = []
    for row, cells in enumerate(lines):
        for x, value in cells:
            content.append(
                f'<word xMin="{x}" yMin="{40 + row * 20}" '
                f'xMax="{x + len(value) * 5}" yMax="{50 + row * 20}">{escape(value)}</word>'
            )
    return '<page width="600" height="800">' + "".join(content) + "</page>"


HEADER = [(50, "Item"), (100, "Description"), (400, "Quantity"), (480, "Unit")]


def test_pdf_preserves_pages_empty_cells_headers_and_word_geometry():
    page = layout_page(
        [
            HEADER,
            [(50, "C-01"), (100, "Concrete foundations"), (400, "120"), (480, "m3")],
            [(50, "C-02"), (100, "Concrete columns"), (480, "m3")],
        ]
    )
    rows, manifest, warnings = boq_pdf.parse_layout(
        f"<html><body>{page}{page}</body></html>".encode(), HEADER_ALIASES
    )
    assert len(rows) == 6
    assert [row["sequence_number"] for row in rows] == list(range(1, 7))
    assert rows[1]["raw_values"] == ["C-01", "Concrete foundations", "120", "m3"]
    assert rows[2]["raw_values"] == ["C-02", "Concrete columns", None, "m3"]
    assert rows[4]["sheet_name"] == "PDF page 2"
    assert rows[4]["page_number"] == 2
    assert rows[4]["original_text"] == "C-01 Concrete foundations 120 m3"
    assert rows[4]["region"]["coordinate_unit"] == "PDF_POINT"
    assert rows[4]["region"]["words"][0]["bbox"] == [50, 60, 70, 70]
    assert all(row["extraction_confidence"] == Decimal("0.75") for row in rows)
    assert manifest[1]["header_row"] == 1
    assert warnings == [{"code": "PDF_VISUAL_COMPLETENESS_REVIEW_REQUIRED"}]


def test_empty_and_unmapped_pages_are_preserved_for_review():
    page = layout_page([[(50, "Unmapped text remains visible")]])
    rows, manifest, warnings = boq_pdf.parse_layout(
        f'<html>{page}<page width="600" height="800"/></html>'.encode(), HEADER_ALIASES
    )
    assert rows[0]["raw_values"] == ["Unmapped text remains visible"]
    assert rows[0]["extraction_confidence"] == 0
    assert len(manifest) == 2
    assert {item["code"] for item in warnings} == {
        "PDF_COLUMN_MAPPING_REVIEW_REQUIRED",
        "PDF_PAGE_REQUIRES_OCR",
        "PDF_VISUAL_COMPLETENESS_REVIEW_REQUIRED",
    }


def test_different_tables_on_one_page_require_mapping_review():
    page = layout_page([HEADER, [(x + 10, text) for x, text in HEADER]])
    rows, manifest, warnings = boq_pdf.parse_layout(f"<html>{page}</html>".encode(), HEADER_ALIASES)
    assert len(rows) == 2
    assert manifest[0]["warnings"][0]["code"] == "PDF_MULTIPLE_TABLE_LAYOUTS_REVIEW_REQUIRED"
    assert any(item["code"] == "PDF_MULTIPLE_TABLE_LAYOUTS_REVIEW_REQUIRED" for item in warnings)


@pytest.mark.parametrize(
    "layout",
    [
        b"not XML",
        b"<html/>",
        b'<!DOCTYPE html [<!ENTITY x "expansion">]><html>&x;</html>',
        b'<html><page><word xMin="NaN" yMin="0" xMax="2" yMax="2">text</word></page></html>',
        b'<html><page><word xMin="2" yMin="0" xMax="1" yMax="2">text</word></page></html>',
    ],
)
def test_pdf_malformed_or_hostile_layout_is_rejected(layout):
    with pytest.raises(boq_pdf.PdfExtractionUnavailable):
        boq_pdf.parse_layout(layout, HEADER_ALIASES)


@pytest.mark.parametrize("limit", ["MAX_OUTPUT_BYTES", "MAX_PAGES", "MAX_WORDS"])
def test_pdf_layout_resource_limits_fail_without_truncation(monkeypatch, limit):
    monkeypatch.setattr(boq_pdf, limit, 1)
    page = layout_page([HEADER])
    with pytest.raises(boq_pdf.PdfExtractionUnavailable):
        boq_pdf.parse_layout(f"<html>{page}{page}</html>".encode(), HEADER_ALIASES)


@pytest.mark.parametrize("failure", ["missing", "timeout", "output", "error_output", "failed"])
def test_pdf_subprocess_failure_is_bounded_and_cleaned_up(monkeypatch, failure):
    processes = []

    class Process:
        returncode = None
        waited = False

        def poll(self):
            return self.returncode

        def kill(self):
            self.returncode = -1

        def wait(self):
            self.waited = True

    def launch(command, **kwargs):
        if failure == "missing":
            raise FileNotFoundError("No executable")
        process = Process()
        process.output = Path(command[-1])
        if failure == "output":
            process.output.write_bytes(b"x" * 20)
        elif failure == "error_output":
            kwargs["stderr"].write(b"x" * 20)
            kwargs["stderr"].flush()
            process.output.write_bytes(b"<html/>")
            process.returncode = 0
        elif failure == "failed":
            process.returncode = 1
        processes.append(process)
        return process

    monkeypatch.setattr(boq_pdf.subprocess, "Popen", launch)
    monkeypatch.setattr(boq_pdf, "MAX_OUTPUT_BYTES", 10)
    monkeypatch.setattr(boq_pdf, "TIMEOUT_SECONDS", -1 if failure == "timeout" else 30)
    with pytest.raises(boq_pdf.PdfExtractionUnavailable):
        boq_pdf._layout(b"%PDF-1.4\n")
    for process in processes:
        assert process.returncode is not None
        assert process.waited
        assert not process.output.parent.exists()


def test_pdf_input_size_is_bounded_before_starting_parser(monkeypatch):
    monkeypatch.setattr(boq_pdf, "MAX_INPUT_BYTES", 4)
    with pytest.raises(boq_pdf.PdfExtractionUnavailable, match="size limit"):
        boq_pdf._layout(b"%PDF-1.4\n")


def text_pdf():
    """Small text-native, two-page PDF fixture using the built-in Helvetica font."""
    commands = []
    for row, cells in enumerate(
        [
            HEADER,
            [(50, "C-01"), (100, "Concrete foundations"), (400, "120"), (480, "m3")],
            [(50, "C-02"), (100, "Concrete columns"), (400, "80"), (480, "m3")],
        ]
    ):
        for x, value in cells:
            commands.append(f"BT /F1 10 Tf 1 0 0 1 {x} {750 - row * 20} Tm ({value}) Tj ET")
    stream = "\n".join(commands).encode()
    second_stream = stream.replace(b"C-01", b"C-11").replace(b"C-02", b"C-12")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R 6 0 R] /Count 2 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 600 800] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 600 800] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 7 0 R >>",
        f"<< /Length {len(second_stream)} >>\nstream\n".encode() + second_stream + b"\nendstream",
    ]
    content = b"%PDF-1.4\n"
    offsets = [0]
    for number, obj in enumerate(objects, start=1):
        offsets.append(len(content))
        content += f"{number} 0 obj\n".encode() + obj + b"\nendobj\n"
    start = len(content)
    content += f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode()
    content += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets[1:])
    return (
        content
        + f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{start}\n%%EOF".encode()
    )


@pytest.mark.skipif(not shutil.which("pdftotext"), reason="Requires local Poppler executable")
def test_real_poppler_preserves_two_page_text_table(tmp_path):
    content = text_pdf()
    (tmp_path / "text-boq.pdf").write_bytes(content)
    rows, manifest, warnings = boq_pdf.extract_pdf(content, HEADER_ALIASES)
    assert len(manifest) == 2
    assert len(rows) == 6
    assert rows[1]["raw_values"] == ["C-01", "Concrete foundations", "120", "m3"]
    assert rows[5]["raw_values"] == ["C-12", "Concrete columns", "80", "m3"]
    assert warnings == [{"code": "PDF_VISUAL_COMPLETENESS_REVIEW_REQUIRED"}]
