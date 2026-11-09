"""Conservative A/S safety consensus for two bounded prompts."""

from __future__ import annotations

DIRECT = "safety_action_required"
CONFIRM = "confirming_safety_status"
NORMAL = "collecting_service_request"
ROUTES = {DIRECT, CONFIRM, NORMAL}


def consensus_route(baseline: str | None, relation: str | None) -> str:
    """Act immediately only on agreement; never hide a missing arm as normal."""
    if baseline not in ROUTES | {None} or relation not in ROUTES | {None}:
        raise ValueError("unrecognized model route")
    if baseline == relation == DIRECT:
        return DIRECT
    if baseline == relation == NORMAL:
        return NORMAL
    return CONFIRM
