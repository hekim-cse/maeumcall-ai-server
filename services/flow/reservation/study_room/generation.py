from __future__ import annotations

from services.flow.reservation.study_room.response_policy import build_study_room_response


def generate_study_room_ai_message(state: dict) -> str:
    conversation_state = state.get("conversation_state") or "collecting_reservation_info"
    return build_study_room_response(conversation_state, state)
