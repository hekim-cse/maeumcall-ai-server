from __future__ import annotations

from typing import Any, Dict, List

from llm.errors import ScenarioStateValidationError


AVAILABILITY_FIELDS = {
    "availability_status",
    "availability_reason",
    "available_time",
    "alternative_times",
}


def validate_availability_result(value: Any) -> Dict[str, Any]:
    """Validate an externally supplied reservation simulation outcome."""
    if not isinstance(value, dict):
        raise ScenarioStateValidationError("simulation_result must be an object")
    if set(value) != AVAILABILITY_FIELDS:
        raise ScenarioStateValidationError(
            "simulation_result must contain the exact availability fields"
        )

    status = value["availability_status"]
    reason = value["availability_reason"]
    available_time = value["available_time"]
    alternative_times = value["alternative_times"]

    if status not in {"available", "unavailable"}:
        raise ScenarioStateValidationError("availability_status is invalid")
    if reason is not None and (not isinstance(reason, str) or not reason.strip()):
        raise ScenarioStateValidationError("availability_reason must be a string or null")
    if available_time is not None and (
        not isinstance(available_time, str) or not available_time.strip()
    ):
        raise ScenarioStateValidationError("available_time must be a string or null")
    if not isinstance(alternative_times, list) or any(
        not isinstance(item, str) or not item.strip() for item in alternative_times
    ):
        raise ScenarioStateValidationError("alternative_times must be a string array")

    normalized_alternatives: List[str] = [item.strip() for item in alternative_times]
    if len(normalized_alternatives) != len(set(normalized_alternatives)):
        raise ScenarioStateValidationError("alternative_times must be unique")

    if status == "available":
        if not available_time or reason is not None or normalized_alternatives:
            raise ScenarioStateValidationError(
                "available result requires available_time and no reason or alternatives"
            )
    elif available_time is not None or not reason:
        raise ScenarioStateValidationError(
            "unavailable result requires a reason and null available_time"
        )

    return {
        "availability_status": status,
        "availability_reason": reason.strip() if isinstance(reason, str) else None,
        "available_time": (
            available_time.strip() if isinstance(available_time, str) else None
        ),
        "alternative_times": normalized_alternatives,
    }
