from __future__ import annotations

from typing import Dict, List, Optional, TypedDict


class ServiceWorkflowState(TypedDict, total=False):
    user_message: str
    conversation_state: str
    intent: str
    fields: Dict[str, Optional[str]]
    missing_fields: List[str]
    user_action: str
    change_field: Optional[str]
    workflow_status: str
    ai_message: str
    last_ai_message: str
    history: List[Dict[str, str]]
    recommended_replies: List[str]
    should_end_call: bool
