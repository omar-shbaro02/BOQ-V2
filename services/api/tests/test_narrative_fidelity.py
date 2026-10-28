import uuid
from types import SimpleNamespace

from app.services.orchestration import validate_narrative


def run():
    return SimpleNamespace(
        id=uuid.uuid4(),
        recommended_disposition="INTERVENE",
        case_brief={
            "case_id": "99900000-1234-4567-8910-000000000999",
            "snapshot_id": "12300000-0000-4000-8000-000000000000",
            "confidence": "0.9000",
            "clocks": [{"duration_days": "3", "deadline": "2099-09-09"}],
            "limitations": [{"description": "Unverified claim for 999 dollars"}],
        },
    )


def test_ids_dates_and_reported_text_cannot_authorize_narrative_numbers():
    result = validate_narrative(run(), "The response costs 999 dollars and 2099 units.")
    assert {item["code"] for item in result["violations"]} == {"UNSUPPORTED_NUMBER"}
    assert len(result["violations"]) == 2


def test_exact_references_dates_and_supported_numeric_facts_remain_valid():
    source = run()
    result = validate_narrative(
        source,
        f"Source {source.case_brief['case_id']}, deadline 2099-09-09. "
        "Duration 3 days and confidence 0.9.",
    )
    assert result["valid"] is True
    assert result["formula_version"] == "CASE-BRIEF-FIDELITY-1.1.0"


def test_foreign_record_citation_fails_even_when_its_digits_match_supported_numbers():
    result = validate_narrative(run(), "Source 00000000-0000-0000-0000-000000000003.")
    assert {item["code"] for item in result["violations"]} == {"UNSUPPORTED_SOURCE_REFERENCE"}


def test_numeric_reported_limitations_and_scientific_notation_do_not_bypass_fidelity():
    source = run()
    source.case_brief["limitations"].append({"value": "999"})
    assert validate_narrative(source, "Cost 999 dollars.")["valid"] is False
    assert validate_narrative(source, "Cost 1e3 dollars.")["valid"] is False
