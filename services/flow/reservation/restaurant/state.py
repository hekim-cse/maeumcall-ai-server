from __future__ import annotations

from typing import TypedDict


class RestaurantReservationState(TypedDict, total=False):
    user_message: str
    conversation_state: str
    service_name: str | None

    intent: str | None
    date: str | None
    time: str | None
    party_size: str | None
    user_name: str | None

    user_action: str | None
    selected_time: str | None

    availability_status: str | None
    availability_reason: str | None
    available_time: str | None
    alternative_times: list[str]
    availability_message_hint: str | None
    reservation_confirmed: bool | None
    ai_message: str | None
    last_ai_message: str | None

    history: list[dict[str, str]]

    recommended_replies: list[str]
    should_end_call: bool
