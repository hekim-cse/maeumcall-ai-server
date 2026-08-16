from __future__ import annotations

from typing import Dict

from services.flow.reservation.hospital.state import HospitalReservationState
from services.flow.reservation.hospital.response_policy import build_hospital_response


def generate_ai_message_node(state: HospitalReservationState) -> Dict:
    """Render the current graph state through the hospital response policy."""
    conversation_state = state.get("conversation_state") or "asking_purpose"
    message = build_hospital_response(conversation_state, state)
    result = {"ai_message": message, "last_ai_message": message}
    if conversation_state == "END":
        result["should_end_call"] = True
    return result
