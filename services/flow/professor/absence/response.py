from __future__ import annotations

from schemas.chat_models import ChatRequest, ChatResponse
from services.flow.professor.absence.graph import professor_absence_graph
from services.flow.professor.absence.policy import compact_professor_absence_state


def is_professor_absence_request(req: ChatRequest) -> bool:
    """
    교수님 / 결석 사유 전달 시나리오인지 판단한다.
    """
    category = (getattr(req, "category", "") or "").strip()
    title = (getattr(req, "title", "") or "").strip()

    return category == "교수님" and "결석" in title and "사유" in title


def complete_professor_absence_with_graph(req: ChatRequest) -> ChatResponse:
    previous_state = getattr(req, "scenarioState", None) or {}
    history = getattr(req, "history", None) or previous_state.get("history") or []

    initial_state = {
        **previous_state,
        "user_message": getattr(req, "userMessage", "") or "",
        "professor_name": previous_state.get("professor_name") or "교수님",
        "conversation_state": (
            getattr(req, "conversationState", None)
            or previous_state.get("conversation_state")
            or "greeting"
        ),
        "history": history,
        "recommended_replies": [],
        "should_end_call": False,
    }

    result = professor_absence_graph.invoke(initial_state)

    ai_message = result.get("ai_message") or "네, 결석 사유와 관련해서 말씀해주시겠습니까?"
    conversation_state = result.get("conversation_state") or "collecting_absence_info"
    recommended_replies = result.get("recommended_replies") or []
    should_end_call = bool(result.get("should_end_call", False))

    return ChatResponse(
        response=ai_message,
        etiquetteTip=None,
        recommendedReplies=recommended_replies,
        conversationState=conversation_state,
        shouldEndCall=should_end_call,
        scenarioState=compact_professor_absence_state(result),
    )
