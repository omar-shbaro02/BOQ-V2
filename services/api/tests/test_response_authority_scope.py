import uuid
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from app.auth import ActorContext
from app.governance_schemas import ResponseAuthorizationCreate
from app.services import governance
from fastapi import HTTPException


@pytest.mark.parametrize("principal", ["HUMAN", "SERVICE", "UNKNOWN"])
def test_response_authorization_rejects_partial_scope_and_nonhuman_principals(
    monkeypatch, principal
):
    project_id, case_id, proposal_id, decision_id, grant_id = (uuid.uuid4() for _ in range(5))
    first, second = uuid.uuid4(), uuid.uuid4()
    actor = ActorContext("operator", uuid.uuid4(), frozenset(), principal)
    case = SimpleNamespace(id=case_id, version=1)
    proposal = SimpleNamespace(id=proposal_id, case_id=case_id, human_decision_id=decision_id)
    decision = SimpleNamespace(id=decision_id)
    grant = SimpleNamespace(
        id=grant_id,
        project_id=project_id,
        actor_id="operator",
        active=True,
        authority_type="RESPONSE_AUTHORIZATION",
        valid_from=None,
        valid_until=None,
        controlled_object_id=first,
    )
    session = Mock()
    session.get.side_effect = lambda model, identifier: {
        proposal_id: proposal,
        decision_id: decision,
        grant_id: grant,
    }[identifier]
    session.scalar.return_value = None
    session.scalars.return_value = [first, second]
    monkeypatch.setattr(governance, "scoped_case", lambda *args, **kwargs: case)
    with pytest.raises(HTTPException) as denied:
        governance.authorize_response(
            session,
            actor,
            SimpleNamespace(id=project_id),
            case_id,
            proposal_id,
            ResponseAuthorizationCreate(
                expected_version=1,
                authority_grant_id=grant_id,
                authorization_reference="Explicit authorization",
            ),
        )
    assert denied.value.status_code == 403
    assert not session.add.called
    if principal == "HUMAN":
        assert "complete case object scope" in denied.value.detail
    else:
        assert "Human principal required" in denied.value.detail
