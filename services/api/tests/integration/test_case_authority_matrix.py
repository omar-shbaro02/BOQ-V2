import uuid

from app.models import (
    AuthorityGrant,
    DecisionCaseControlledObject,
    HumanDecision,
    ResponseAuthorization,
)
from sqlalchemy import func, select
from test_decision_case_api import (
    add_evidence,
    bootstrap,
    open_case,
    snapshot,
)
from test_decision_case_api import (
    case_api as case_api,
)


def test_human_disposition_grants_fail_closed_for_actor_tenant_scope_dates_and_amounts(case_api):
    client, sessions = case_api
    organization, project, headers, first_object = bootstrap(client)
    evidence = add_evidence(client, project, headers, first_object)
    case = open_case(client, project, headers, evidence, "authority-matrix")
    second = client.post(
        f"/api/v1/projects/{project}/controlled-objects",
        headers=headers,
        json={"object_type": "WORK_PACKAGE", "code": "WP-SECOND", "name": "Second case package"},
    )
    outside = client.post(
        f"/api/v1/projects/{project}/controlled-objects",
        headers=headers,
        json={"object_type": "WORK_PACKAGE", "code": "WP-OUTSIDE", "name": "Outside case scope"},
    )
    assert second.status_code == outside.status_code == 201
    # Freeze an explicit two-package fixture before any disposition or response.
    with sessions() as session:
        session.add(
            DecisionCaseControlledObject(
                case_id=uuid.UUID(case["id"]), controlled_object_id=uuid.UUID(second.json()["id"])
            )
        )
        session.commit()
    frozen = snapshot(client, project, headers, case, "authority-matrix-snapshot")
    base = f"/api/v1/projects/{project}/decision-cases/{case['id']}"
    run = client.post(
        f"{base}/orchestration-runs",
        headers={**headers, "Idempotency-Key": "authority-matrix-run"},
        json={
            "expected_version": frozen["case"]["version"],
            "snapshot_id": frozen["snapshot"]["id"],
        },
    )
    assert run.status_code == 201, run.text
    assert run.json()["run"]["recommended_disposition"] == "VERIFY"
    version = run.json()["case"]["version"]
    body = {
        "expected_version": version,
        "orchestration_run_id": run.json()["run"]["id"],
        "disposition": "VERIFY",
        "recommendation_agreement": "AGREE",
        "rationale": "Human review requests verification without authorizing an intervention",
        "decision_amount": "50",
        "currency": "USD",
    }
    other_project = client.post(
        f"/api/v1/organizations/{organization}/projects",
        headers=headers,
        json={
            "code": "GRANT-OTHER",
            "name": "Other authority project",
            "timezone": "UTC",
            "currency": "USD",
            "delivery_model": "DESIGN_BID_BUILD",
            "reporting_cadence": "WEEKLY",
        },
    )
    assert other_project.status_code == 201, other_project.text
    variants = {
        "WRONG_ACTOR": {"actor_id": "different-approver"},
        "WRONG_AUTHORITY_TYPE": {"authority_type": "REPORT_APPROVAL"},
        "EXPIRED": {"valid_until": "2000-01-01"},
        "NOT_YET_VALID": {"valid_from": "2099-01-01"},
        "WRONG_CURRENCY": {"currency": "EUR"},
        "AMOUNT_EXCEEDED": {"max_amount": "49"},
        "NO_AMOUNT_AUTHORITY": {"max_amount": None},
        "PARTIAL_CASE_SCOPE": {"controlled_object_id": first_object},
        "OUTSIDE_CASE_SCOPE": {"controlled_object_id": outside.json()["id"]},
        "INACTIVE": {},
        "FOREIGN_PROJECT": {},
        "UNKNOWN_GRANT": {},
    }
    original_ledger = client.get(f"{base}/ledger", headers=headers).json()
    for name, overrides in variants.items():
        if name == "UNKNOWN_GRANT":
            identifier = str(uuid.uuid4())
        else:
            grant_project = other_project.json()["id"] if name == "FOREIGN_PROJECT" else project
            created = client.post(
                f"/api/v1/projects/{grant_project}/authority-grants",
                headers=headers,
                json={
                    "actor_id": headers["X-VAI-Actor-ID"],
                    "authority_type": "CASE_DISPOSITION",
                    "max_amount": "100",
                    "currency": "USD",
                    **overrides,
                },
            )
            assert created.status_code == 201, created.text
            identifier = created.json()["id"]
            if name == "INACTIVE":
                with sessions() as session:
                    session.get(AuthorityGrant, uuid.UUID(identifier)).active = False
                    session.commit()
        denied = client.post(
            f"{base}/human-decisions",
            headers={**headers, "Idempotency-Key": "denied-" + name},
            json={**body, "authority_grant_id": identifier},
        )
        assert denied.status_code == 403, f"{name}: {denied.status_code} {denied.text}"
        assert client.get(base, headers=headers).json()["version"] == version
    assert client.get(f"{base}/ledger", headers=headers).json() == original_ledger
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(HumanDecision)) == 0
    granted = client.post(
        f"/api/v1/projects/{project}/authority-grants",
        headers=headers,
        json={
            "actor_id": headers["X-VAI-Actor-ID"],
            "authority_type": "CASE_DISPOSITION",
            "max_amount": "100",
            "currency": "USD",
        },
    )
    assert granted.status_code == 201, granted.text
    accepted = client.post(
        f"{base}/human-decisions",
        headers={**headers, "Idempotency-Key": "human-verification-decision"},
        json={**body, "authority_grant_id": granted.json()["id"]},
    )
    assert accepted.status_code == 201, accepted.text
    assert accepted.json()["decision"]["decided_by"] == headers["X-VAI-Actor-ID"]
    assert accepted.json()["decision"]["authority_scope"]["controlled_object_id"] is None
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(ResponseAuthorization)) == 0
