# LangGraph 실행 결과를 ChatResponse로 바꾸는 파일

from __future__ import annotations

from typing import Dict, Any

from schemas.chat_models import ChatRequest, ChatResponse
from services.flow.reservation.hospital.graph import hospital_reservation_graph
from services.flow.common.scenario_keys import scenario_matches


def is_hospital_reservation_request(req: ChatRequest) -> bool:
    """
    병원 예약 LangGraph 라우팅 여부를 판단한다.

    등록된 category/title 키를 사용해
    category/title의 명시적인 시나리오 매핑만 사용한다.

    이유:
    - "예약"이라는 단어만으로 병원 예약 graph에 보내면
      식당 예약, 스터디룸 예약, 미용실 예약도 병원 graph로 잘못 들어갈 수 있다.
    - LangGraph case는 시나리오 단위로 명확하게 분리되어야 한다.
    """
    return scenario_matches(
        getattr(req, "category", ""),
        getattr(req, "title", ""),
        expected_category="예약",
        expected_title="병원 예약",
    )


def _compact_scenario_state(result: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "intent": result.get("intent"),
        "service_name": result.get("service_name"),
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
        "service_name": previous_state.get("service_name") or "마음병원",
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
        scenarioState=_compact_scenario_state(result),
    )
