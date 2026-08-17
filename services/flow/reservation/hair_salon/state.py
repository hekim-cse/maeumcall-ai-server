from __future__ import annotations

from typing import TypedDict, Optional, Dict, List, Any


class HairSalonReservationState(TypedDict, total=False):
    user_message: str
    conversation_state: str
    service_name: Optional[str]

    intent: Optional[str]
    date: Optional[str]
    time: Optional[str]
    service_type: Optional[str]
    designer: Optional[str]
    user_name: Optional[str]

    user_action: Optional[str]
    selected_time: Optional[str]

    availability_status: Optional[str]
    availability_reason: Optional[str]
    available_time: Optional[str]
    alternative_times: List[str]
    availability_message_hint: Optional[str]
    reservation_confirmed: Optional[bool]
    ai_message: Optional[str]
    last_ai_message: Optional[str]

    history: List[Dict[str, str]]

    recommended_replies: List[str]
    should_end_call: bool
