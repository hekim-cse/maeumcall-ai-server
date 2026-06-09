from __future__ import annotations

from typing import TypedDict, Optional, Dict, List, Any


class ProfessorAppointmentState(TypedDict, total=False):
    user_message: str
    conversation_state: str

    professor_name: Optional[str]
    intent: Optional[str]
    appointment_purpose: Optional[str]
    date: Optional[str]
    time: Optional[str]
    user_name: Optional[str]

    user_action: Optional[str]

    ai_message: Optional[str]
    last_ai_message: Optional[str]

    history: List[Dict[str, str]]

    recommended_replies: List[str]
    should_end_call: bool

    simulation_result: Optional[Dict[str, Any]]
