# LangGraph 실행 결과를 ChatResponse로 바꾸는 파일

from __future__ import annotations

from typing import Dict, Any

from schemas.chat_models import ChatRequest, ChatResponse
from services.flow.hospital_reservation_graph import hospital_reservation_graph


def is_hospital_reservation_request(req: ChatRequest) -> bool:
    """
    병원 예약 LangGraph 라우팅 여부를 판단한다.

    휴리스틱 키워드 매칭을 사용하지 않고,
    category/title의 명시적인 시나리오 매핑만 사용한다.

    이유:
    - "예약"이라는 단어만으로 병원 예약 graph에 보내면
      식당 예약, 스터디룸 예약, 미용실 예약도 병원 graph로 잘못 들어갈 수 있다.
    - LangGraph case는 시나리오 단위로 명확하게 분리되어야 한다.
    """
    category = (getattr(req, "category", "") or "").strip()
    title = (getattr(req, "title", "") or "").strip()

    return category == "예약" and title == "병원 예약"


def _compact_scenario_state(result: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "intent": result.get("intent"),
        "department": result.get("department"),
        "date": result.get("date"),
        "time": result.get("time"),
        "conversation_state": result.get("conversation_state"),
        "last_ai_message": result.get("ai_message"),

        "user_action": result.get("user_action"),
        "selected_time": result.get("selected_time"),
        
        "availability_status": result.get("availability_status"),
        "availability_reason": result.get("availability_reason"),
        "available_time": result.get("available_time"),
        "alternative_times": result.get("alternative_times") or [],
        "availability_message_hint": result.get("availability_message_hint"),
        "reservation_confirmed": result.get("reservation_confirmed"),
        "simulation_result": result.get("simulation_result"),
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