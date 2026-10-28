"""Explicit synthetic human authority for positive authorized-context fixture setup."""


def activate_with_authority(client, url, *, headers, json):
    project_id = url.split("/")[4]
    versions = client.get(
        f"/api/v1/projects/{project_id}/authorized-context/versions", headers=headers
    )
    assert versions.status_code == 200, versions.text
    source = next(item for item in versions.json() if item["id"] == json["source_version_id"])
    authority = {
        "SCHEDULE": "BASELINE_SCHEDULE_APPROVAL"
        if source["semantic_state"] == "BASELINE"
        else "CURRENT_SCHEDULE_APPROVAL",
        "BUDGET": "BUDGET_APPROVAL",
        "BOQ": "BOQ_APPROVAL",
        "PROGRESS_WEIGHTING": "PROGRESS_WEIGHTING_APPROVAL",
    }[source["context_type"]]
    grant = client.post(
        f"/api/v1/projects/{project_id}/authority-grants",
        headers=headers,
        json={"actor_id": headers["X-VAI-Actor-ID"], "authority_type": authority},
    )
    assert grant.status_code == 201, grant.text
    current = next(
        (
            item
            for item in versions.json()
            if item["context_type"] == source["context_type"]
            and item["semantic_state"] == "CURRENT_AUTHORIZED"
        ),
        None,
    )
    return client.post(
        url,
        headers={**headers, "Idempotency-Key": f"fixture-activation-{source['id']}"},
        json={
            **json,
            "authority_grant_id": grant.json()["id"],
            "expected_current_context_id": current["id"] if current else None,
        },
    )
