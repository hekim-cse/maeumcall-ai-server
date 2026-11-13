from __future__ import annotations

from services.flow.reservation.common.graph_builder import (
    build_availability_reservation_graph,
    route_after_availability_decide,
)
from services.flow.reservation.hair_salon.nodes import (
    attach_hair_salon_recommended_replies_node,
    check_hair_salon_availability_node,
    decide_hair_salon_state_node,
    extract_hair_salon_info_node,
    generate_hair_salon_response_node,
)
from services.flow.reservation.hair_salon.state import HairSalonReservationState


def route_after_hair_salon_decide(state: HairSalonReservationState) -> str:
    """
    상태 결정 후 다음 노드를 선택한다.
    """
    return route_after_availability_decide(state)


def build_hair_salon_reservation_graph():
    return build_availability_reservation_graph(
        state_type=HairSalonReservationState,
        graph_name="hair_salon_reservation",
        extract_info=extract_hair_salon_info_node,
        decide_state=decide_hair_salon_state_node,
        check_availability=check_hair_salon_availability_node,
        generate_response=generate_hair_salon_response_node,
        attach_replies=attach_hair_salon_recommended_replies_node,
        route_after_decide=route_after_hair_salon_decide,
    )


hair_salon_reservation_graph = build_hair_salon_reservation_graph()
