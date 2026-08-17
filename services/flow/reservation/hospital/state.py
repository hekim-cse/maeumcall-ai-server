from __future__ import annotations

from typing import TypedDict, Optional, Dict, List


class HospitalReservationState(TypedDict, total=False):
    user_message: str
    conversation_state: str
    service_name: Optional[str]

    intent: Optional[str]
    department: Optional[str]
    date: Optional[str]
    time: Optional[str]
    user_name: Optional[str]
    phone_number: Optional[str]

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
