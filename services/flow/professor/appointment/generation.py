from __future__ import annotations

from services.flow.professor.appointment.response_policy import build_professor_appointment_response


def generate_professor_appointment_ai_message(state: dict) -> str:
    conversation_state = state.get("conversation_state") or "collecting_appointment_info"
    return build_professor_appointment_response(conversation_state, state)
