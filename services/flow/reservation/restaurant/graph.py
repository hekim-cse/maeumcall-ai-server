from __future__ import annotations

from services.flow.reservation.common.graph_builder import (
    build_availability_reservation_graph,
    route_after_availability_decide,
)
from services.flow.reservation.restaurant.nodes import (
    attach_restaurant_recommended_replies_node,
    check_restaurant_availability_node,
    decide_restaurant_state_node,
    extract_restaurant_info_node,
    generate_restaurant_response_node,
)
from services.flow.reservation.restaurant.state import RestaurantReservationState


def route_after_restaurant_decide(state: RestaurantReservationState) -> str:
    """
    decide_state 이후 다음 노드를 결정한다.
    """
    return route_after_availability_decide(state)


def build_restaurant_reservation_graph():
    return build_availability_reservation_graph(
        state_type=RestaurantReservationState,
        graph_name="restaurant_reservation",
        extract_info=extract_restaurant_info_node,
        decide_state=decide_restaurant_state_node,
        check_availability=check_restaurant_availability_node,
        generate_response=generate_restaurant_response_node,
        attach_replies=attach_restaurant_recommended_replies_node,
        route_after_decide=route_after_restaurant_decide,
    )


restaurant_reservation_graph = build_restaurant_reservation_graph()
