"""Explicitly opted-in contract smoke test; synthetic input only, no project mutations."""

import pytest
from app.config import get_settings
from app.generated.taxonomies import SpecialistKind
from app.services.agent_automation import run_specialist_agent


@pytest.mark.live_adapter
def test_live_specialist_empty_snapshot_preserves_evidence_boundary() -> None:
    settings = get_settings()
    assert settings.openai_api_key and settings.openai_api_key.get_secret_value(), (
        "The live profile requires VAI_OPENAI_API_KEY"
    )
    result = run_specialist_agent(
        SpecialistKind.EVIDENCE_PROGRESS,
        api_key=settings.openai_api_key.get_secret_value(),
        model=settings.openai_agent_model,
        snapshot_id="synthetic-empty-live-smoke-v1",
        selected_input={"evidence": [], "limitations": ["No evidence supplied"]},
        requested_questions=["Identify evidence gaps; there are no project facts to assess."],
        allowed_evidence_ids=set(),
    )
    assert result.response_id != "unknown"
    assert result.output["evidence_references"] == []
    assert result.output["limitations"] or result.output["requested_evidence"]
