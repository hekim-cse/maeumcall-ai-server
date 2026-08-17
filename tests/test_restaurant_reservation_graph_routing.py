import pytest

from schemas.chat_models import ChatRequest
from services.flow.reservation.restaurant.response import is_restaurant_reservation_request

pytestmark = pytest.mark.unit


def _req(category: str, title: str) -> ChatRequest:
    return ChatRequest(
        category=category,
        title=title,
        description="",
        userMessage="예약하고 싶습니다.",
    )


def test_restaurant_reservation_routes_to_restaurant_graph():
    req = _req("예약", "식당 예약")

    assert is_restaurant_reservation_request(req) is True


def test_hospital_reservation_does_not_route_to_restaurant_graph():
    req = _req("예약", "병원 예약")

    assert is_restaurant_reservation_request(req) is False


def test_study_room_reservation_does_not_route_to_restaurant_graph():
    req = _req("예약", "스터디룸 예약")

    assert is_restaurant_reservation_request(req) is False


def test_hair_salon_reservation_does_not_route_to_restaurant_graph():
    req = _req("예약", "미용실 예약")

    assert is_restaurant_reservation_request(req) is False


def test_non_reservation_category_does_not_route_to_restaurant_graph():
    req = _req("가족", "식당 예약")

    assert is_restaurant_reservation_request(req) is False
