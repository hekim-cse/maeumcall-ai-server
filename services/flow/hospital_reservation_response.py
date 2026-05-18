# LangGraph 실행 결과를 ChatResponse로 바꾸는 파일

from __future__ import annotations

from typing import Dict, Any

from schemas.chat_models import ChatRequest, ChatResponse
from services.flow.hospital_reservation_graph import hospital_reservation_graph


def is_hospital_reservation_request(req: ChatRequest) -> bool:
    category = (getattr(req, "category", "") or "").strip()
    title = (getattr(req, "title", "") or "").strip()
    description = (getattr(req, "description", "") or "").strip()

    if category != "예약":
        return False

    target_text = f"{title} {description}"

    return any(word in target_text for word in ["병원", "진료", "내과", "예약"])


def _compact_scenario_state(result: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "intent": result.get("intent"),
        "department": result.get("department"),
        "date": result.get("date"),
        "time": result.get("time"),
        "conversation_state": result.get("conversation_state"),
        "last_ai_message": result.get("ai_message"),
    }


def complete_hospital_reservation_with_graph(req: ChatRequest) -> ChatResponse:
    previous_state = getattr(req, "scenarioState", None) or {}

    history = getattr(req, "history", None) or previous_state.get("history") or []

    initial_state = {
        **previous_state,
        "user_message": getattr(req, "userMessage", "") or "",
        "conversation_state": (
            getattr(req, "conversationState", None)
            or previous_state.get("conversation_state")
            or "greeting"
        ),
        "history": history,
        "recommended_replies": [],
        "should_end_call": False,
    }

    result = hospital_reservation_graph.invoke(initial_state)

    ai_message = result.get("ai_message") or "네, 확인해드리겠습니다. 조금만 더 말씀해주시겠어요?"
    conversation_state = result.get("conversation_state") or "asking_purpose"
    recommended_replies = result.get("recommended_replies") or []
    should_end_call = bool(result.get("should_end_call", False))

    return ChatResponse(
        response=ai_message,
        etiquetteTip=None,
        recommendedReplies=recommended_replies,
        conversationState=conversation_state,
        shouldEndCall=should_end_call,
        scenarioState=_compact_scenario_state(result),
    )