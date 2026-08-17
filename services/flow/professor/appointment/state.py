from __future__ import annotations

from typing import TypedDict


class ProfessorAppointmentState(TypedDict, total=False):
    user_message: str
    conversation_state: str

    professor_name: str | None
    intent: str | None
    appointment_purpose: str | None
    date: str | None
    time: str | None
    user_name: str | None

    user_action: str | None
    missing_fields: list[str]

    ai_message: str | None
    last_ai_message: str | None

    history: list[dict[str, str]]

    recommended_replies: list[str]
    should_end_call: bool
