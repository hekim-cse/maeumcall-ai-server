from __future__ import annotations

from langgraph.graph import StateGraph, START, END

from services.flow.reservation.study_room.state import StudyRoomReservationState
from services.flow.reservation.study_room.nodes import (
    extract_study_room_info_node,
    decide_study_room_state_node,
    check_study_room_availability_node,
    generate_study_room_response_node,
    attach_study_room_recommended_replies_node,
)


def route_after_study_room_decide(state: StudyRoomReservationState) -> str:
    """
    상태 결정 후 다음 노드를 선택한다.
    """
    if state.get("conversation_state") == "checking_availability":
        return "check_availability"

    return "generate_response"


def build_study_room_reservation_graph():
    builder = StateGraph(StudyRoomReservationState)

    builder.add_node("extract_info", extract_study_room_info_node)
    builder.add_node("decide_state", decide_study_room_state_node)
    builder.add_node("check_availability", check_study_room_availability_node)
    builder.add_node("generate_response", generate_study_room_response_node)
    builder.add_node("attach_replies", attach_study_room_recommended_replies_node)

    builder.add_edge(START, "extract_info")
    builder.add_edge("extract_info", "decide_state")
    builder.add_conditional_edges(
        "decide_state",
        route_after_study_room_decide,
        {
            "check_availability": "check_availability",
            "generate_response": "generate_response",
        },
    )
    builder.add_edge("check_availability", "generate_response")
    builder.add_edge("generate_response", "attach_replies")
    builder.add_edge("attach_replies", END)

    return builder.compile()


study_room_reservation_graph = build_study_room_reservation_graph()
