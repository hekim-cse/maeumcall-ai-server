from __future__ import annotations

from langgraph.graph import StateGraph, START, END

from services.flow.reservation.study_room.state import StudyRoomReservationState
from services.flow.reservation.study_room.nodes import (
    extract_study_room_info_node,
    decide_study_room_state_node,
    generate_study_room_response_node,
    attach_study_room_recommended_replies_node,
)


def build_study_room_reservation_graph():
    builder = StateGraph(StudyRoomReservationState)

    builder.add_node("extract_info", extract_study_room_info_node)
    builder.add_node("decide_state", decide_study_room_state_node)
    builder.add_node("generate_response", generate_study_room_response_node)
    builder.add_node("attach_replies", attach_study_room_recommended_replies_node)

    builder.add_edge(START, "extract_info")
    builder.add_edge("extract_info", "decide_state")
    builder.add_edge("decide_state", "generate_response")
    builder.add_edge("generate_response", "attach_replies")
    builder.add_edge("attach_replies", END)

    return builder.compile()


study_room_reservation_graph = build_study_room_reservation_graph()
