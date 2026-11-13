from __future__ import annotations

from services.flow.reservation.common.graph_builder import (
    build_availability_reservation_graph,
    route_after_availability_decide,
)
from services.flow.reservation.study_room.nodes import (
    attach_study_room_recommended_replies_node,
    check_study_room_availability_node,
    decide_study_room_state_node,
    extract_study_room_info_node,
    generate_study_room_response_node,
)
from services.flow.reservation.study_room.state import StudyRoomReservationState


def route_after_study_room_decide(state: StudyRoomReservationState) -> str:
    """
    상태 결정 후 다음 노드를 선택한다.
    """
    return route_after_availability_decide(state)


def build_study_room_reservation_graph():
    return build_availability_reservation_graph(
        state_type=StudyRoomReservationState,
        graph_name="study_room_reservation",
        extract_info=extract_study_room_info_node,
        decide_state=decide_study_room_state_node,
        check_availability=check_study_room_availability_node,
        generate_response=generate_study_room_response_node,
        attach_replies=attach_study_room_recommended_replies_node,
        route_after_decide=route_after_study_room_decide,
    )


study_room_reservation_graph = build_study_room_reservation_graph()
