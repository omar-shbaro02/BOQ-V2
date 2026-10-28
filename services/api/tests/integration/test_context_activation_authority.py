import uuid

from app.models import AuditEvent, AuthorityGrant, AuthorizedContextVersion
from sqlalchemy import select
from test_control_context_api import api as api
from test_project_control_api import bootstrap_project


def test_context_activation_exact_grants_replay_predecessors_and_frozen_authority(api):
    client, sessions = api
    _, project, headers = bootstrap_project(client, "context-authority")
    base = f"/api/v1/projects/{project}"

    def source(label, value):
        response = client.post(
            f"{base}/authorized-context/versions",
            headers=headers,
            json={
                "context_type": "BUDGET",
                "semantic_state": "PROPOSED",
                "effective_from": "2026-01-01T00:00:00Z",
                "payload": {"currency": "USD", "approved_budget": value},
            },
        )
        assert response.status_code == 201, response.text
        return response.json()

    first = source("first", "100")
    body = {
        "source_version_id": first["id"],
        "expected_current_context_id": None,
        "approval_reference": "Budget approval",
        "reason": "Explicit project-wide human approval",
    }

    def activate(data, key):
        return client.post(
            f"{base}/authorized-context/activate",
            headers={**headers, "Idempotency-Key": key},
            json=data,
        )

    assert activate(body, "no-grant").status_code == 403
    assert (
        activate({**body, "authority_grant_id": str(uuid.uuid4())}, "unknown-grant").status_code
        == 403
    )
    object_response = client.post(
        f"{base}/controlled-objects",
        headers=headers,
        json={"object_type": "WORK_PACKAGE", "code": "WP-BOUND", "name": "Bounded package"},
    )
    assert object_response.status_code == 201
    for name, changes in {
        "WRONG_ACTOR": {"actor_id": "other-approver"},
        "WRONG_TYPE": {"authority_type": "CURRENT_SCHEDULE_APPROVAL"},
        "CHANGE_BYPASS": {"authority_type": "CHANGE_APPROVAL"},
        "EXPIRED": {"valid_until": "2000-01-01"},
        "FUTURE": {"valid_from": "2099-01-01"},
        "BOUNDED_PACKAGE": {"controlled_object_id": object_response.json()["id"]},
        "BOUNDED_AMOUNT": {"max_amount": "100", "currency": "USD"},
        "INACTIVE": {},
    }.items():
        grant = client.post(
            f"{base}/authority-grants",
            headers=headers,
            json={
                "actor_id": headers["X-VAI-Actor-ID"],
                "authority_type": "BUDGET_APPROVAL",
                **changes,
            },
        )
        assert grant.status_code == 201, grant.text
        identifier = grant.json()["id"]
        if name == "INACTIVE":
            with sessions() as session:
                session.get(AuthorityGrant, uuid.UUID(identifier)).active = False
                session.commit()
        denied = activate({**body, "authority_grant_id": identifier}, name)
        assert denied.status_code == 403, f"{name}: {denied.status_code} {denied.text}"
    with sessions() as session:
        assert (
            list(
                session.scalars(
                    select(AuthorizedContextVersion).where(
                        AuthorizedContextVersion.semantic_state == "CURRENT_AUTHORIZED"
                    )
                )
            )
            == []
        )

    grant = client.post(
        f"{base}/authority-grants",
        headers=headers,
        json={"actor_id": headers["X-VAI-Actor-ID"], "authority_type": "BUDGET_APPROVAL"},
    )
    assert grant.status_code == 201
    approved_body = {**body, "authority_grant_id": grant.json()["id"]}
    approved = activate(approved_body, "initial-approval")
    assert approved.status_code == 201, approved.text
    initial = approved.json()
    assert activate(approved_body, "initial-approval").json()["id"] == initial["id"]
    assert (
        activate({**approved_body, "reason": "Changed intent"}, "initial-approval").status_code
        == 409
    )
    second = source("second", "200")
    replacement = {**approved_body, "source_version_id": second["id"]}
    assert activate(replacement, "stale-predecessor").status_code == 409
    accepted = activate(
        {**replacement, "expected_current_context_id": initial["id"]}, "replace-budget"
    )
    assert accepted.status_code == 201, accepted.text
    with sessions() as session:
        session.get(AuthorityGrant, uuid.UUID(grant.json()["id"])).active = False
        session.commit()
    replay = activate(approved_body, "initial-approval")
    assert replay.status_code == 201 and replay.json()["id"] == initial["id"]
    assert replay.json()["semantic_state"] == "SUPERSEDED"
    assert (
        activate(
            {**replacement, "expected_current_context_id": accepted.json()["id"]},
            "new-revoked-approval",
        ).status_code
        == 403
    )
    current = client.get(f"{base}/authorized-context/current/BUDGET", headers=headers)
    assert current.json()["id"] == accepted.json()["id"]
    with sessions() as session:
        events = list(
            session.scalars(
                select(AuditEvent).where(AuditEvent.action == "AUTHORIZED_CONTEXT_ACTIVATED")
            )
        )
        assert len(events) == 2
        assert all(event.details["authority_grant_id"] == grant.json()["id"] for event in events)
        assert all(
            event.details["authority_scope"]["actor_id"] == headers["X-VAI-Actor-ID"]
            for event in events
        )
