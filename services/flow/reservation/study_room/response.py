from __future__ import annotations

from schemas.chat_models import ChatRequest, ChatResponse
from services.flow.reservation.study_room.graph import study_room_reservation_graph
from services.flow.reservation.study_room.policy import compact_study_room_state


def is_study_room_reservation_request(req: ChatRequest) -> bool:
    """
    스터디룸 예약 LangGraph 라우팅 여부를 판단한다.

    휴리스틱 키워드 매칭을 사용하지 않고,
    category/title의 명시적인 시나리오 매핑만 사용한다.
    """
    category = (getattr(req, "category", "") or "").strip()
    title = (getattr(req, "title", "") or "").strip()

    return category == "예약" and title == "스터디룸 예약"


def complete_study_room_reservation_with_graph(req: ChatRequest) -> ChatResponse:
    previous_state = getattr(req, "scenarioState", None) or {}

    history = getattr(req, "history", None) or previous_state.get("history") or []

    initial_state = {
        **previous_state,
        "user_message": getattr(req, "userMessage", "") or "",
        "service_name": previous_state.get("service_name") or "마음스터디룸",
        "conversation_state": (
            getattr(req, "conversationState", None)
            or previous_state.get("conversation_state")
            or "greeting"
        ),
        "history": history,
        "recommended_replies": [],
        "should_end_call": False,
    }

    result = study_room_reservation_graph.invoke(initial_state)

    ai_message = result.get("ai_message") or "네, 스터디룸 예약 도와드리겠습니다."
    conversation_state = result.get("conversation_state") or "collecting_reservation_info"
    recommended_replies = result.get("recommended_replies") or []
    should_end_call = bool(result.get("should_end_call", False))

    return ChatResponse(
        response=ai_message,
        etiquetteTip=None,
        recommendedReplies=recommended_replies,
        conversationState=conversation_state,
        shouldEndCall=should_end_call,
        scenarioState=compact_study_room_state(result),
    )
