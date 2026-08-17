from __future__ import annotations

from typing import Any, Dict, Optional

from schemas.chat_models import ChatRequest, ChatResponse
from services.flow.scenario.graph import scenario_conversation_graph
from services.flow.scenario.registry import get_scenario_config
from services.flow.common.state_contract import envelope_state, validate_client_state


def complete_scenario_graph_if_supported(req: ChatRequest) -> Optional[ChatResponse]:
    config = get_scenario_config(req.category, req.title)
    if config is None:
        return None

    previous = validate_client_state(
        req,
        category=config.category,
        title=config.title,
        allowed_fields={"conversation_state", "turn_count", "last_ai_message"},
        allowed_conversation_states={"greeting", "opening", "active", "END"},
    )
    history = req.serialized_history()
    payload = req.model_dump()
    initial_state: Dict[str, Any] = {
        **previous,
        "request_payload": payload,
        "category": req.category,
        "title": req.title,
        "scenario_key": config.key,
        "user_message": req.userMessage,
        "history": history,
        "conversation_state": req.conversationState or previous.get("conversation_state") or "opening",
        "turn_count": previous.get("turn_count") or 0,
        "recommended_replies": [],
        "should_end_call": False,
    }
    result = scenario_conversation_graph.invoke(initial_state)
    scenario_state = envelope_state(
        {
            "conversation_state": result["conversation_state"],
            "turn_count": result["turn_count"],
            "last_ai_message": result["ai_message"],
        },
        category=config.category,
        title=config.title,
    )
    return ChatResponse(
        response=result["ai_message"],
        etiquetteTip=result.get("etiquette_tip"),
        recommendedReplies=result["recommended_replies"],
        conversationState=result["conversation_state"],
        shouldEndCall=result["should_end_call"],
        scenarioState=scenario_state,
    )
