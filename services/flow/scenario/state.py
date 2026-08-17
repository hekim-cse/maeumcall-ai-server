from __future__ import annotations

from typing import Any, TypedDict


class ScenarioConversationState(TypedDict, total=False):
    request_payload: dict[str, Any]
    category: str
    title: str
    scenario_key: str
    user_message: str
    history: list[dict[str, str]]
    conversation_state: str
    turn_count: int
    ai_message: str | None
    last_ai_message: str | None
    etiquette_tip: str | None
    recommended_replies: list[str]
    should_end_call: bool
