from __future__ import annotations

from typing import Dict

from services.flow.reservation.restaurant.state import RestaurantReservationState
from services.flow.reservation.restaurant.response_policy import build_restaurant_response


def generate_restaurant_ai_message(state: RestaurantReservationState) -> Dict:
    conversation_state = state.get("conversation_state") or "collecting_reservation_info"
    return {"ai_message": build_restaurant_response(conversation_state, state)}
