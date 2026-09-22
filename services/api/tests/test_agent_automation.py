from __future__ import annotations

import json

from app.generated.taxonomies import SpecialistKind
from app.services import agent_automation


def test_every_specialist_has_a_versioned_json_prompt() -> None:
    prompts = [agent_automation.load_agent_prompt(kind) for kind in SpecialistKind]
    assert {prompt["specialist_kind"] for prompt in prompts} == {
        kind.value for kind in SpecialistKind
    }
    assert all(prompt["version"] == "1.0.0" for prompt in prompts)
    assert all(prompt["prohibited_actions"] for prompt in prompts)


def test_agent_uses_structured_output_and_validates_evidence(monkeypatch) -> None:
    output = {
        "findings": [],
        "calculations": [],
        "evidence_references": ["evidence-1"],
        "truth_labels": ["DERIVED"],
        "assumptions": [],
        "contradictions": [],
        "confidence": 0.7,
        "limitations": [],
        "requested_evidence": [],
    }

    class Response:
        status_code = 200

        def json(self):
            return {
                "id": "resp_test",
                "output": [{"content": [{"type": "output_text", "text": json.dumps(output)}]}],
            }

    def post(*args, **kwargs):
        schema = kwargs["json"]["text"]["format"]
        assert schema["type"] == "json_schema"
        assert schema["strict"] is True
        return Response()

    monkeypatch.setattr(agent_automation.httpx, "post", post)
    result = agent_automation.run_specialist_agent(
        SpecialistKind.EVIDENCE_PROGRESS,
        api_key="test-key",
        model="test-model",
        snapshot_id="snapshot-1",
        selected_input={"id": "result-1"},
        requested_questions=["What changed?"],
        allowed_evidence_ids={"evidence-1"},
    )
    assert result.response_id == "resp_test"
    assert result.output["confidence"] == 0.7
