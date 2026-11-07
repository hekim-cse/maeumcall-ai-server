from __future__ import annotations

from typing import TypedDict


class ServiceWorkflowState(TypedDict, total=False):
    user_message: str
    conversation_state: str
    intent: str
    fields: dict[str, str | None]
    missing_fields: list[str]
    user_action: str
    change_field: str | None
    workflow_status: str
    ai_message: str
    last_ai_message: str
    history: list[dict[str, str]]
    recommended_replies: list[str]
    should_end_call: bool
