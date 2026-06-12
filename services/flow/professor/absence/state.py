from __future__ import annotations

from typing import TypedDict, Optional, Dict, List, Any


class ProfessorAbsenceState(TypedDict, total=False):
    user_message: str
    conversation_state: str

    professor_name: Optional[str]
    intent: Optional[str]
    class_name: Optional[str]
    absence_date: Optional[str]
    absence_reason: Optional[str]
    user_name: Optional[str]

    user_action: Optional[str]
    missing_fields: List[str]

    ai_message: Optional[str]
    last_ai_message: Optional[str]

    history: List[Dict[str, str]]

    recommended_replies: List[str]
    should_end_call: bool

    simulation_result: Optional[Dict[str, Any]]
