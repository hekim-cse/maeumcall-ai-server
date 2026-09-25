from __future__ import annotations

from enum import StrEnum
from types import MappingProxyType


class DifficultyTag(StrEnum):
    SINGLE_FIELD = "single_field"
    MULTI_FIELD = "multi_field"
    CORRECTION = "correction"
    NEGATION = "negation"
    ELLIPSIS = "ellipsis"
    COLLOQUIAL = "colloquial"
    AMBIGUOUS = "ambiguous"
    HARD_NEGATIVE = "hard_negative"
    CONFIRMATION = "confirmation"
    CANCELLATION = "cancellation"
    CLOSING = "closing"
    SAFETY = "safety"


OBJECTIVE_DIFFICULTY_TAGS_V1 = frozenset(
    {
        DifficultyTag.CORRECTION,
        DifficultyTag.CONFIRMATION,
        DifficultyTag.CANCELLATION,
        DifficultyTag.CLOSING,
    }
)


# This is a versioned semantic declaration, not a name-prefix classifier. Every live
# structured-NLU action must appear exactly once; contracts.py enforces that exact set.
ACTION_OBJECTIVE_TAGS_V1 = MappingProxyType(
    {
        "ask_follow_up": frozenset(),
        "ask_other_time": frozenset(),
        "cancel_workflow": frozenset({DifficultyTag.CANCELLATION}),
        "change_absence_date": frozenset({DifficultyTag.CORRECTION}),
        "change_absence_reason": frozenset({DifficultyTag.CORRECTION}),
        "change_class_name": frozenset({DifficultyTag.CORRECTION}),
        "change_date": frozenset({DifficultyTag.CORRECTION}),
        "change_department": frozenset({DifficultyTag.CORRECTION}),
        "change_designer": frozenset({DifficultyTag.CORRECTION}),
        "change_detail": frozenset({DifficultyTag.CORRECTION}),
        "change_duration": frozenset({DifficultyTag.CORRECTION}),
        "change_info": frozenset({DifficultyTag.CORRECTION}),
        "change_party_size": frozenset({DifficultyTag.CORRECTION}),
        "change_purpose": frozenset({DifficultyTag.CORRECTION}),
        "change_service_type": frozenset({DifficultyTag.CORRECTION}),
        "change_start_time": frozenset({DifficultyTag.CORRECTION}),
        "change_time": frozenset({DifficultyTag.CORRECTION}),
        "change_user_name": frozenset({DifficultyTag.CORRECTION}),
        "complete_simulation": frozenset(),
        "confirm": frozenset({DifficultyTag.CONFIRMATION}),
        "confirm_available_time": frozenset({DifficultyTag.CONFIRMATION}),
        "confirm_details": frozenset({DifficultyTag.CONFIRMATION}),
        "confirm_info": frozenset({DifficultyTag.CONFIRMATION}),
        "confirm_reservation": frozenset({DifficultyTag.CONFIRMATION}),
        "confirm_reservation_info": frozenset({DifficultyTag.CONFIRMATION}),
        "continue_collecting": frozenset(),
        "end_call": frozenset({DifficultyTag.CLOSING}),
        "go_closing": frozenset({DifficultyTag.CLOSING}),
        "lookup_availability": frozenset(),
        "provide_absence_info": frozenset(),
        "provide_appointment_info": frozenset(),
        "provide_assignment_info": frozenset(),
        "provide_details": frozenset(),
        "select_alternative_time": frozenset(),
        "unknown": frozenset(),
    }
)

_declared_objective_tags = frozenset().union(*ACTION_OBJECTIVE_TAGS_V1.values())
if _declared_objective_tags != OBJECTIVE_DIFFICULTY_TAGS_V1:
    raise RuntimeError(
        "action objective semantics must cover the versioned objective tag set exactly: "
        f"missing={sorted(OBJECTIVE_DIFFICULTY_TAGS_V1 - _declared_objective_tags)}, "
        f"unknown={sorted(_declared_objective_tags - OBJECTIVE_DIFFICULTY_TAGS_V1)}"
    )
