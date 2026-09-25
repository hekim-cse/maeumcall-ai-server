from __future__ import annotations

from collections.abc import Collection

HOSPITAL_ALTERNATIVE_SELECTION_STATES = frozenset(
    {"reservation_unavailable", "suggest_alternative"}
)
STANDARD_ALTERNATIVE_SELECTION_STATES = frozenset({"reservation_unavailable"})


def validate_alternative_time_selection(
    *,
    conversation_state: str,
    alternative_states: Collection[str],
    user_action: str,
    selected_time: str | None,
    alternative_times: Collection[str] | None,
) -> None:
    """Validate an alternative selection against the exact server-offered values."""
    in_alternative_state = conversation_state in alternative_states
    selects_alternative = user_action == "select_alternative_time"

    if not in_alternative_state and selected_time is not None:
        raise ValueError("selected_time is allowed only while selecting an alternative")
    if in_alternative_state and selects_alternative != (selected_time is not None):
        raise ValueError("select_alternative_time and selected_time must be provided together")
    if selected_time is not None and selected_time not in (alternative_times or ()):
        raise ValueError("selected_time must exactly match one of the offered alternatives")
