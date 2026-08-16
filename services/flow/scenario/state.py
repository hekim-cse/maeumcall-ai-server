from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict


class ScenarioConversationState(TypedDict, total=False):
    request_payload: Dict[str, Any]
    category: str
    title: str
    scenario_key: str
    user_message: str
    history: List[Dict[str, str]]
    conversation_state: str
    turn_count: int
    ai_message: Optional[str]
    last_ai_message: Optional[str]
    etiquette_tip: Optional[str]
    recommended_replies: List[str]
    should_end_call: bool
