from __future__ import annotations

from services.flow.reservation.hair_salon.response_policy import build_hair_salon_response
from services.flow.reservation.hair_salon.state import HairSalonReservationState


def generate_hair_salon_ai_message(state: HairSalonReservationState) -> str:
    conversation_state = state.get("conversation_state") or "collecting_reservation_info"
    return build_hair_salon_response(conversation_state, state)
