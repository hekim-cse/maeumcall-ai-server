from __future__ import annotations

from typing import Dict

from services.flow.professor.assignment.response_policy import build_professor_assignment_response


def generate_professor_assignment_ai_message(state: Dict) -> str:
    conversation_state = state.get("conversation_state") or "collecting_assignment_info"
    return build_professor_assignment_response(conversation_state, state)
