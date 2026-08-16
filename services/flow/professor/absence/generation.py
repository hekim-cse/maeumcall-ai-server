from __future__ import annotations

from typing import Dict

from services.flow.professor.absence.response_policy import build_professor_absence_response


def generate_professor_absence_ai_message(state: Dict) -> str:
    conversation_state = state.get("conversation_state") or "collecting_absence_info"
    return build_professor_absence_response(conversation_state, state)
