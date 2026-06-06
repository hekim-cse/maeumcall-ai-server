from __future__ import annotations

from typing import Optional

from schemas.chat_models import ChatRequest, ChatResponse
from services.flow.reservation.hospital.response import (
    is_hospital_reservation_request,
    complete_hospital_reservation_with_graph,
)
from services.flow.reservation.restaurant.response import (
    is_restaurant_reservation_request,
    complete_restaurant_reservation_with_graph,
)
from services.flow.reservation.hair_salon.response import (
    is_hair_salon_reservation_request,
    complete_hair_salon_reservation_with_graph,
)
from services.flow.reservation.study_room.response import (
    is_study_room_reservation_request,
    complete_study_room_reservation_with_graph,
)


def complete_reservation_graph_if_supported(req: ChatRequest) -> Optional[ChatResponse]:
    """
    예약 카테고리 안에서 LangGraph로 처리할 수 있는 시나리오를 분기한다.

    현재 지원하는 graph:
    - 예약 / 병원 예약
    - 예약 / 식당 예약
    - 예약 / 스터디룸 예약
    - 예약 / 미용실 예약

    아직 지원하지 않는 예약 시나리오:

    지원하지 않는 시나리오는 None을 반환하여 기존 LLM/fallback 흐름으로 넘긴다.
    """
    if is_hospital_reservation_request(req):
        return complete_hospital_reservation_with_graph(req)

    if is_restaurant_reservation_request(req):
        return complete_restaurant_reservation_with_graph(req)

    if is_study_room_reservation_request(req):
        return complete_study_room_reservation_with_graph(req)

    if is_hair_salon_reservation_request(req):
        return complete_hair_salon_reservation_with_graph(req)

    return None
