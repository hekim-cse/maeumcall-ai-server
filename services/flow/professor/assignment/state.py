from __future__ import annotations

from typing import TypedDict


class ProfessorAssignmentState(TypedDict, total=False):
    user_message: str
    conversation_state: str

    professor_name: str | None
    intent: str | None
    course_name: str | None
    assignment_topic: str | None
    question: str | None
    user_name: str | None

    user_action: str | None
    missing_fields: list[str]

    ai_message: str | None
    last_ai_message: str | None

    history: list[dict[str, str]]

    recommended_replies: list[str]
    should_end_call: bool
