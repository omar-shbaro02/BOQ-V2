"""Bounded text-native PDF extraction; table geometry remains a reviewable proposal."""

import bisect
import math
import re
import subprocess
import sys
import tempfile
import time
from decimal import Decimal
from pathlib import Path
from typing import Any

from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException

PARSER_NAME = "VAI_BOQ_PDF_TEXT"
PARSER_VERSION = "1.0.0"
MAX_OUTPUT_BYTES = 16 * 1024 * 1024
MAX_INPUT_BYTES = 25 * 1024 * 1024
MAX_PAGES = 200
MAX_WORDS = 100000
TIMEOUT_SECONDS = 30


class PdfExtractionUnavailable(ValueError):
    pass


def _layout(content: bytes) -> bytes:
    if not content.startswith(b"%PDF-"):
        raise PdfExtractionUnavailable("PDF content signature is invalid")
    if len(content) > MAX_INPUT_BYTES:
        raise PdfExtractionUnavailable("PDF input exceeds the supported size limit")
    with tempfile.TemporaryDirectory(prefix="vai-boq-pdf-") as directory:
        output = Path(directory) / "layout.xml"
        errors = Path(directory) / "parser-errors.txt"
        source = Path(directory) / "source.pdf"
        source.write_bytes(content)
        try:
            with errors.open("wb") as stderr:
                process = subprocess.Popen(
                    ["pdftotext", "-bbox-layout", "-enc", "UTF-8", str(source), str(output)],
                    stdout=subprocess.DEVNULL,
                    stderr=stderr,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
                )
                started = time.monotonic()
                try:
                    while process.poll() is None:
                        if time.monotonic() - started > TIMEOUT_SECONDS:
                            raise PdfExtractionUnavailable("PDF extraction timed out")
                        if any(
                            path.exists() and path.stat().st_size > MAX_OUTPUT_BYTES
                            for path in (output, errors)
                        ):
                            raise PdfExtractionUnavailable("PDF extraction exceeds output limit")
                        time.sleep(0.025)
                finally:
                    if process.poll() is None:
                        process.kill()
                    process.wait()
            if process.returncode or not output.exists():
                raise PdfExtractionUnavailable("PDF text extraction failed")
            if any(path.stat().st_size > MAX_OUTPUT_BYTES for path in (output, errors)):
                raise PdfExtractionUnavailable("PDF extraction exceeds output limit")
            return output.read_bytes()
        except OSError as exc:
            raise PdfExtractionUnavailable("PDF text extraction is unavailable") from exc


def _token(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def parse_layout(
    layout: bytes, aliases: dict[str, set[str]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Preserve each visible text row, with page-local columns and exact word geometry."""
    if len(layout) > MAX_OUTPUT_BYTES:
        raise PdfExtractionUnavailable("PDF extraction exceeds output limit")
    try:
        # Poppler emits a public XHTML doctype, but no entities are needed or permitted.
        root = ElementTree.fromstring(layout, forbid_entities=True, forbid_external=True)
        pages = root.findall(".//{*}page")
        if not pages or len(pages) > MAX_PAGES:
            raise PdfExtractionUnavailable("PDF page count is empty or exceeds the supported limit")
        rows, manifest, warnings = [], [], []
        word_count = 0
        for page_number, page in enumerate(pages, start=1):
            words = []
            for word in page.findall(".//{*}word"):
                text = "".join(word.itertext()).strip()
                if not text:
                    continue
                box = [float(word.attrib[key]) for key in ("xMin", "yMin", "xMax", "yMax")]
                if not all(math.isfinite(value) and value >= 0 for value in box):
                    raise PdfExtractionUnavailable("PDF text geometry is invalid")
                if box[2] < box[0] or box[3] < box[1]:
                    raise PdfExtractionUnavailable("PDF text geometry is invalid")
                words.append({"text": text, "bbox": box})
                word_count += 1
                if word_count > MAX_WORDS:
                    raise PdfExtractionUnavailable("PDF text exceeds the supported word limit")
            lines: list[list[dict[str, Any]]] = []
            for word in sorted(words, key=lambda item: (item["bbox"][1], item["bbox"][0])):
                if not lines or abs(word["bbox"][1] - lines[-1][0]["bbox"][1]) > 2:
                    lines.append([])
                lines[-1].append(word)
            lines = [sorted(line, key=lambda item: item["bbox"][0]) for line in lines]
            candidates = []
            for row_number, line in enumerate(lines, start=1):
                headers = []
                index = 0
                while index < len(line):
                    matched = False
                    for size in range(min(4, len(line) - index), 0, -1):
                        segment = line[index : index + size]
                        if any(
                            right["bbox"][0] - left["bbox"][2] > 12
                            for left, right in zip(segment, segment[1:], strict=False)
                        ):
                            continue
                        phrase = " ".join(item["text"] for item in segment)
                        field = next(
                            (field for field, names in aliases.items() if _token(phrase) in names),
                            None,
                        )
                        if field:
                            headers.append({"field": field, "x": line[index]["bbox"][0]})
                            index += size
                            matched = True
                            break
                    if not matched:
                        index += 1
                fields = [header["field"] for header in headers]
                if (
                    len(fields) == len(set(fields))
                    and "description" in fields
                    and "quantity" in fields
                    and len(fields) >= 3
                ):
                    candidates.append((row_number, headers))
            header_row, headers = max(candidates, key=lambda item: len(item[1]), default=(0, []))
            page_warnings = []
            if not words:
                page_warnings.append({"code": "PDF_PAGE_REQUIRES_OCR", "page_number": page_number})
            elif not headers:
                page_warnings.append(
                    {"code": "PDF_COLUMN_MAPPING_REVIEW_REQUIRED", "page_number": page_number}
                )
            elif any(candidate != headers for _, candidate in candidates):
                page_warnings.append(
                    {
                        "code": "PDF_MULTIPLE_TABLE_LAYOUTS_REVIEW_REQUIRED",
                        "page_number": page_number,
                    }
                )
            warnings.extend(page_warnings)
            for row_number, line in enumerate(lines, start=1):
                text = " ".join(item["text"] for item in line)
                values: list[str | None] = [None] * len(headers) if headers else [text]
                if headers:
                    for word in line:
                        column = max(
                            0,
                            bisect.bisect_right([item["x"] for item in headers], word["bbox"][0])
                            - 1,
                        )
                        values[column] = " ".join(filter(None, [values[column], word["text"]]))
                rows.append(
                    {
                        "sequence_number": len(rows) + 1,
                        "sheet_name": f"PDF page {page_number}",
                        "page_number": page_number,
                        "row_number": row_number,
                        "region": {
                            "coordinate_unit": "PDF_POINT",
                            "bbox": [
                                min(word["bbox"][0] for word in line),
                                min(word["bbox"][1] for word in line),
                                max(word["bbox"][2] for word in line),
                                max(word["bbox"][3] for word in line),
                            ],
                            "words": line,
                        },
                        "raw_values": values,
                        "original_text": text,
                        "extraction_confidence": Decimal("0.7500") if headers else Decimal("0"),
                        "warnings": [
                            {"code": "PDF_LAYOUT_REVIEW_REQUIRED", "page_number": page_number},
                            *page_warnings,
                        ],
                    }
                )
            manifest.append(
                {
                    "page_number": page_number,
                    "sheet_name": f"PDF page {page_number}",
                    "width_points": page.attrib.get("width"),
                    "height_points": page.attrib.get("height"),
                    "retained_nonempty_rows": len(lines),
                    "header_row": header_row or None,
                    "proposed_columns": headers,
                    "warnings": page_warnings,
                }
            )
        warnings.append({"code": "PDF_VISUAL_COMPLETENESS_REVIEW_REQUIRED"})
        return rows, manifest, warnings
    except PdfExtractionUnavailable:
        raise
    except (ValueError, KeyError, ElementTree.ParseError, DefusedXmlException) as exc:
        raise PdfExtractionUnavailable("PDF text layout is malformed") from exc


def extract_pdf(
    content: bytes, aliases: dict[str, set[str]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    return parse_layout(_layout(content), aliases)
