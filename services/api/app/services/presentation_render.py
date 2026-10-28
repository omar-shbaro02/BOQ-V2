"""Self-contained, printable stakeholder slides generated only from a frozen report envelope."""

import base64
import hashlib
import html
import json
import re
import unicodedata
from datetime import UTC, datetime
from html.parser import HTMLParser
from importlib.resources import files

from app.services.control_metrics import shared_metrics

GENERATOR_VERSION = "REPORT-SLIDES-1.0.0"
SOURCE_PATTERN = re.compile(
    r'<script id="source-report" type="application/json">(.*?)</script>', re.S
)


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def digest(value) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def display(value) -> str:
    if value is None:
        return "Unknown"
    if isinstance(value, (dict, list)):
        return canonical(value)
    return str(value)


def timestamp(value: str) -> str:
    parsed = datetime.fromisoformat(value)
    return (parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)).astimezone(UTC).isoformat()


def wrap_line(text: str) -> list[str]:
    """Conservative character-width budget keeps long identifiers and wide scripts legible."""
    lines, current, width = [], "", 0.0

    def character_width(character):
        return (
            2
            if unicodedata.east_asian_width(character) in {"W", "F"}
            else 1.6
            if character in "wmMW@%&#"
            else 1.4
            if character.isupper()
            else 1
        )

    for character in " ".join(text.split()):
        weight = character_width(character)
        if current and width + weight > 78:
            boundary = current.rfind(" ")
            if boundary > len(current) // 2:
                lines.append(current[:boundary])
                current = current[boundary + 1 :]
                width = sum(character_width(char) for char in current)
            else:
                lines.append(current.rstrip())
                current, width = "", 0.0
        current += character
        width += weight
    if current or not lines:
        lines.append(current.rstrip())
    return lines


def build_presentation(envelope: dict) -> bytes:
    report = envelope["report"]
    control = report["payload"]["project_control"]
    metrics = shared_metrics(control)
    slides = []

    def section(title: str, paragraphs: list[str]):
        lines = []
        for paragraph in paragraphs:
            lines.extend(wrap_line(str(paragraph)))
        for index in range(0, max(1, len(lines)), 12):
            slides.append(
                (title if index == 0 else f"{title} (continued)", lines[index : index + 12])
            )

    identity = report["payload"].get("project_identity", {})
    section(
        "Project control report",
        [
            identity.get("name") or "Project identity unavailable in this legacy report",
            report["report_type"].replace("_", " ").title(),
            f"Report date: {timestamp(report['report_date'])}",
            f"Source data date: {metrics['data_date']}",
            "Source report approval and presentation approval are recorded separately.",
        ],
    )
    section(
        "Project completion",
        [
            f"Authorized planned completion: {metrics['planned']['display']}",
            f"Verified or accepted completion: {metrics['actual']['display']}",
            f"Actual minus planned: {metrics['variance']['display']} (percentage points)",
            f"Progress position: {metrics['progress_status']}",
            f"Minimum verified progress confidence: {metrics['confidence']}",
            f"Data date: {metrics['data_date']}",
        ],
    )
    health = control.get("health") or {}
    section(
        "Project health",
        [
            f"Derived management attention: {health.get('status', 'UNKNOWN')}",
            *[
                f"{name.title()}: {result['status']}"
                for name, result in health.get("dimensions", {}).items()
            ],
            *[display(item) for item in health.get("limitations", [])],
        ],
    )
    for package in control.get("package_results", []):
        section(
            "Work package contribution",
            [
                f"Package: {package['controlled_object_code']}",
                f"Authorized weight: {package['weight']}",
                f"Planned completion ratio: {package['planned_ratio']}",
                f"Actual completion ratio: {package['actual_ratio']}",
                f"Actual gate: {package['actual_measurement_kind']}",
                f"Truth: {package['actual_truth_type']}",
                f"Confidence: {package['actual_confidence']}",
                f"Planned contribution: {package['planned_contribution']}",
                f"Actual contribution: {package['actual_contribution']}",
            ],
        )
    if not metrics["cost_assessments"]:
        section("Cost position", ["Unknown. This report binds no cost assessment."])
    for cost in metrics["cost_assessments"]:
        section(
            "Cost assessment",
            [
                f"Work scope: {cost['controlled_object_id']}",
                f"Assessment: {cost['assessment_status']}",
                f"Data date: {cost['data_date']}",
                *[
                    f"{field.replace('_', ' ').title()}: {display(value)} {cost['currency']}"
                    for field, value in cost["values"].items()
                ],
                *[display(item) for item in cost["limitations"]],
                "Amounts belong to this assessment. No unsupported project total is inferred.",
            ],
        )
    if not metrics["forecast_projections"]:
        section("Forecast", ["Unknown. No supported forecast projection is bound to this report."])
    for forecast in metrics["forecast_projections"]:
        section(
            "Forecast projection",
            [
                f"Target: {forecast['target']}",
                f"Scenario basis: {forecast['scenario_type']}",
                f"Status: {forecast['status']}",
                f"Point: {display(forecast['result_point'])} {forecast['result_unit']}",
                f"Range: {display(forecast['result_lower'])} to "
                f"{display(forecast['result_upper'])} {forecast['result_unit']}",
                f"Source date: {forecast['data_date']}",
                f"Horizon: {forecast['horizon_end']}",
                f"Valid until: {forecast['valid_until']}",
                f"Horizon confidence: {forecast['horizon_confidence']}",
                *[display(item) for item in forecast["limitations"]],
            ],
        )
    for record in control.get("supporting_context", {}).get("project_context", []):
        if record["record_type"] in {"RISK", "ISSUE", "CHANGE_REQUEST", "CHARTER", "DAILY_UPDATE"}:
            section(
                f"{record['record_type'].replace('_', ' ').title()} context",
                [
                    f"Recorded status: {record['status']}",
                    f"Effective from: {record['effective_from']}",
                    *[
                        f"{field.replace('_', ' ').title()}: {display(value)}"
                        for field, value in record["payload"].items()
                    ],
                    record["semantic_notice"],
                ],
            )
    queue = report["payload"].get("decision_queue", [])
    for case in queue:
        section(
            "Decision Case",
            [
                f"{case.get('case_number', 'Case')} {case.get('title', '')}",
                f"Latest system recommendation: {display(case.get('recommended_disposition'))}",
                f"Signed decision basis: {display(case.get('decision_basis_recommendation'))}",
                f"Human disposition: {display(case.get('human_disposition'))}",
                f"Governance route: {display(case.get('governance_state'))}",
                f"Readiness: {display(case.get('readiness'))}",
                f"Next recorded action: {display(case.get('next_action'))}",
            ],
        )
    section(
        "Limitations and evidence",
        [
            *[display(item) for item in control.get("limitations", [])],
            *[
                f"Evidence reference: {item}"
                for item in report["source_refs"].get("evidence_item_ids", [])
            ],
            report["semantic_notice"],
        ],
    )
    section(
        "Selected recipients",
        [
            *[
                f"{item['payload']['name']}: {item['payload']['project_role']}. "
                f"Communication rules: {display(item['payload']['communication_rules'])}"
                for item in envelope["recipients"]
            ],
            "This artifact does not send messages or authorize execution.",
        ],
    )
    section(
        "Source and approval lineage",
        [
            f"Source report: {report['id']}",
            f"Report content hash: {report['content_hash']}",
            f"Source report approval: {envelope['source_report_approval_event_id']}",
            f"Presentation record: {envelope['presentation_id']}",
            f"Generator: {GENERATOR_VERSION}",
            "The complete frozen source report and selected recipient records "
            "are embedded in this file.",
        ],
    )
    if len(slides) > 1000:
        raise ValueError(
            "The report is too large for a reviewable presentation; use a narrower report scope"
        )
    assets = files("app").joinpath("presentation_assets")
    css = assets.joinpath("slides.css").read_text(encoding="utf-8")
    script = assets.joinpath("slides.js").read_text(encoding="utf-8")
    encoded_source = (
        canonical({**envelope, "shared_metrics": metrics})
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
    )
    source_download = base64.b64encode(encoded_source.encode()).decode()
    style_hash = base64.b64encode(hashlib.sha256(css.encode()).digest()).decode()
    script_hash = base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()
    csp = (
        f"default-src 'none'; style-src 'sha256-{style_hash}'; "
        f"script-src 'sha256-{script_hash}'; base-uri 'none'; form-action 'none'"
    )
    content = [
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">',
        f'<meta http-equiv="Content-Security-Policy" content="{html.escape(csp, quote=True)}">'
        f"<title>Project control presentation</title><style>{css}</style></head><body>",
        '<nav aria-label="Presentation controls"><button id="print" type="button">'
        "Print or save PDF</button>",
        f'<a download="source-report.json" href="data:application/json;base64,{source_download}">'
        "Complete source report</a><span>Arrow keys move between slides</span></nav>",
    ]
    for index, (title, lines) in enumerate(slides, 1):
        content.append(
            f'<section class="slide" aria-label="Slide {index} of {len(slides)}">'
            f'<h1>{html.escape(title)}</h1><div class="body">'
        )
        content.extend(f"<p>{html.escape(line) if line else '&nbsp;'}</p>" for line in lines)
        content.append(
            f"</div><footer>{html.escape(report['semantic_notice'])}<br>"
            f"Source report {report['id']} / slide {index} of {len(slides)}</footer></section>"
        )
    content.append(
        f'<script id="source-report" type="application/json">{encoded_source}</script>'
        f"<script>{script}</script></body></html>"
    )
    return "".join(content).encode()


def inspect_source(content: bytes) -> dict:
    match = SOURCE_PATTERN.search(content.decode())
    if not match:
        raise ValueError("Presentation has no frozen source report")
    source = json.loads(match.group(1))
    if digest(source["report"]["payload"]) != source["report"]["content_hash"]:
        raise ValueError("Presentation source report hash mismatch")
    if source["shared_metrics"] != shared_metrics(source["report"]["payload"]["project_control"]):
        raise ValueError("Presentation metric fidelity mismatch")
    parser = BodyText()
    parser.feed(content.decode())
    metrics = source["shared_metrics"]
    for line in (
        f"Authorized planned completion: {metrics['planned']['display']}",
        f"Verified or accepted completion: {metrics['actual']['display']}",
        f"Actual minus planned: {metrics['variance']['display']} (percentage points)",
    ):
        if line not in parser.lines:
            raise ValueError("Visible presentation metric differs from the source report")
    return source


class BodyText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.body = False
        self.paragraph = False
        self.buffer = ""
        self.lines = []

    def handle_starttag(self, tag, attrs):
        if tag == "div" and dict(attrs).get("class") == "body":
            self.body = True
        if tag == "p" and self.body:
            self.paragraph, self.buffer = True, ""

    def handle_data(self, data):
        if self.paragraph:
            self.buffer += data

    def handle_endtag(self, tag):
        if tag == "p" and self.paragraph:
            self.lines.append(self.buffer.strip())
            self.paragraph = False
        if tag == "div":
            self.body = False
