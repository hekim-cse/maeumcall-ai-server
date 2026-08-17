from __future__ import annotations

from services.flow.reservation.restaurant.response_policy import build_restaurant_response
from services.flow.reservation.restaurant.state import RestaurantReservationState


def generate_restaurant_ai_message(state: RestaurantReservationState) -> dict:
    conversation_state = state.get("conversation_state") or "collecting_reservation_info"
    return {"ai_message": build_restaurant_response(conversation_state, state)}
