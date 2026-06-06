from __future__ import annotations

from typing import Dict

from langgraph.graph import StateGraph, START, END

from services.flow.reservation.hair_salon.state import HairSalonReservationState


def hair_salon_greeting_node(state: HairSalonReservationState) -> Dict:
    """
    미용실 예약 LangGraph 최소 진입 확인용 노드이다.
    이후 날짜, 시간, 시술 종류, 예약자 이름 수집 흐름으로 확장한다.
    """
    service_name = state.get("service_name") or "마음헤어"

    return {
        "intent": "reservation",
        "service_name": service_name,
        "conversation_state": "collecting_reservation_info",
        "ai_message": (
            f"네, {service_name}입니다. "
            "미용실 예약 도와드리겠습니다. 원하시는 날짜, 시간, 시술 종류를 말씀해주시겠어요?"
        ),
        "recommended_replies": [
            "내일 오후에 커트 예약 가능할까요?",
            "오늘 저녁에 펌 예약하고 싶습니다.",
            "이번 주말에 염색 예약 가능할까요?",
        ],
        "should_end_call": False,
    }


def build_hair_salon_reservation_graph():
    builder = StateGraph(HairSalonReservationState)

    builder.add_node("hair_salon_greeting", hair_salon_greeting_node)

    builder.add_edge(START, "hair_salon_greeting")
    builder.add_edge("hair_salon_greeting", END)

    return builder.compile()


hair_salon_reservation_graph = build_hair_salon_reservation_graph()
