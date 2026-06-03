from __future__ import annotations

from typing import Dict

from langgraph.graph import StateGraph, START, END

from services.flow.reservation.restaurant.state import RestaurantReservationState


def restaurant_greeting_node(state: RestaurantReservationState) -> Dict:
    """
    식당 예약 LangGraph 최소 진입 확인용 노드이다.
    이후 식당 예약 상태 흐름을 구현하면서 세부 노드로 분리할 예정이다.
    """
    service_name = state.get("service_name") or "마음식당"

    return {
        "intent": "reservation",
        "service_name": service_name,
        "conversation_state": "asking_date",
        "ai_message": f"네, {service_name}입니다. 예약 도와드리겠습니다. 예약 날짜는 언제가 괜찮으세요?",
        "recommended_replies": [
            "오늘 저녁으로 예약하고 싶습니다.",
            "내일 저녁으로 예약하고 싶습니다.",
            "이번 주말로 예약하고 싶습니다.",
        ],
        "should_end_call": False,
    }


def build_restaurant_reservation_graph():
    builder = StateGraph(RestaurantReservationState)

    builder.add_node("restaurant_greeting", restaurant_greeting_node)

    builder.add_edge(START, "restaurant_greeting")
    builder.add_edge("restaurant_greeting", END)

    return builder.compile()


restaurant_reservation_graph = build_restaurant_reservation_graph()
