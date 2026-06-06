from __future__ import annotations

from typing import Dict

from langgraph.graph import StateGraph, START, END

from services.flow.reservation.study_room.state import StudyRoomReservationState


def study_room_greeting_node(state: StudyRoomReservationState) -> Dict:
    """
    스터디룸 예약 LangGraph 최소 진입 확인용 노드이다.
    이후 날짜, 시작 시간, 이용 시간, 인원 등 정보 수집 흐름으로 확장한다.
    """
    service_name = state.get("service_name") or "마음스터디룸"

    return {
        "intent": "reservation",
        "service_name": service_name,
        "conversation_state": "collecting_reservation_info",
        "ai_message": (
            f"네, {service_name}입니다. "
            "스터디룸 예약 도와드리겠습니다. 이용하실 날짜, 시작 시간, 이용 시간을 말씀해주시겠어요?"
        ),
        "recommended_replies": [
            "내일 두 시간 예약하고 싶습니다.",
            "오늘 오후 두 시부터 이용하고 싶습니다.",
            "내일 오후 두 시부터 두 시간 가능할까요?",
        ],
        "should_end_call": False,
    }


def build_study_room_reservation_graph():
    builder = StateGraph(StudyRoomReservationState)

    builder.add_node("study_room_greeting", study_room_greeting_node)

    builder.add_edge(START, "study_room_greeting")
    builder.add_edge("study_room_greeting", END)

    return builder.compile()


study_room_reservation_graph = build_study_room_reservation_graph()
