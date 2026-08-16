from __future__ import annotations

from typing import Dict, Any

from schemas.chat_models import ChatRequest, ChatResponse
from services.flow.reservation.restaurant.graph import restaurant_reservation_graph
from services.flow.common.scenario_keys import scenario_matches
from services.flow.reservation.restaurant.policy import compact_restaurant_state


def is_restaurant_reservation_request(req: ChatRequest) -> bool:
    """
    식당 예약 LangGraph 라우팅 여부를 판단한다.

    등록된 category/title 키를 사용해
    category/title의 명시적인 시나리오 매핑만 사용한다.
    """
    return scenario_matches(
        getattr(req, "category", ""),
        getattr(req, "title", ""),
        expected_category="예약",
        expected_title="식당 예약",
    )



def complete_restaurant_reservation_with_graph(req: ChatRequest) -> ChatResponse:
    previous_state = getattr(req, "scenarioState", None) or {}

    history = getattr(req, "history", None) or previous_state.get("history") or []

    initial_state = {
        **previous_state,
        "user_message": getattr(req, "userMessage", "") or "",
        "service_name": previous_state.get("service_name") or "마음식당",
        "conversation_state": (
            getattr(req, "conversationState", None)
            or previous_state.get("conversation_state")
            or "greeting"
        ),
        "history": history,
        "recommended_replies": [],
        "should_end_call": False,
    }

    result = restaurant_reservation_graph.invoke(initial_state)

    ai_message = result["ai_message"]
    conversation_state = result["conversation_state"]
    recommended_replies = result["recommended_replies"]
    should_end_call = result["should_end_call"]

    return ChatResponse(
        response=ai_message,
        etiquetteTip=None,
        recommendedReplies=recommended_replies,
        conversationState=conversation_state,
        shouldEndCall=should_end_call,
        scenarioState=compact_restaurant_state(result),
    )
