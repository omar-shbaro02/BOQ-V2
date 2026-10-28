"""External commands reserved to humans, independently of role or grant ownership."""

import re

PREFIX = "/api/v1/projects/{project_id}"
HUMAN_COMMANDS = frozenset(
    {
        "/api/v1/organizations/{organization_id}/memberships",
        *[
            PREFIX + suffix
            for suffix in (
                "/memberships",
                "/authority-grants",
                "/authorized-context/activate",
                "/activate",
                "/progress/policies",
                "/schedule/policies",
                "/cost/policies",
                "/forecast/policies",
                "/impact/policies",
                "/evidence/reliability",
                "/bootstrap/planning-structures/{structure_id}/revisions",
                "/bootstrap/schedule-drafts/{generation_id}/corrections",
                "/bootstrap/schedule-calculations/{calculation_id}/reviews",
                "/bootstrap/schedule-releases/{release_id}/approve",
                "/evidence/items/{item_id}/verify",
                "/evidence/contradictions/{contradiction_id}/resolve",
                "/decision-cases/{case_id}/limitations/{limitation_id}/resolve",
                "/decision-cases/{case_id}/transition",
                "/decision-cases/{case_id}/block",
                "/decision-cases/{case_id}/resume",
                "/decision-cases/{case_id}/close",
                "/decision-cases/{case_id}/reopen",
                "/decision-cases/{case_id}/human-decisions",
                "/decision-cases/{case_id}/active-responses",
                "/correlation-suggestions/{suggestion_id}/review",
                "/decision-cases/{case_id}/response-proposals/{proposal_id}/authorization",
                "/decision-cases/{case_id}/confidence-overrides",
                "/decision-cases/{case_id}/orchestration-runs/{run_id}/contradiction-resolutions",
                "/project-context/records/{record_id}/transitions",
                "/decision-center/report-snapshots/{report_id}/lifecycle-events",
                "/decision-center/presentations/{presentation_id}/lifecycle-events",
            )
        ],
    }
)
MATCHERS = tuple(re.compile("^" + re.sub(r"{\w+}", "[^/]+", path) + "$") for path in HUMAN_COMMANDS)


def is_human_command(method: str, path: str) -> bool:
    return method == "POST" and any(pattern.fullmatch(path) for pattern in MATCHERS)
