from schemas.chat_models import ChatRequest
from services.flow.reservation.study_room.response import is_study_room_reservation_request


def _req(category: str, title: str) -> ChatRequest:
    return ChatRequest(
        category=category,
        title=title,
        description="",
        userMessage="예약하고 싶습니다.",
    )


def test_study_room_reservation_routes_to_study_room_graph():
    req = _req("예약", "스터디룸 예약")

    assert is_study_room_reservation_request(req) is True


def test_hospital_reservation_does_not_route_to_study_room_graph():
    req = _req("예약", "병원 예약")

    assert is_study_room_reservation_request(req) is False


def test_restaurant_reservation_does_not_route_to_study_room_graph():
    req = _req("예약", "식당 예약")

    assert is_study_room_reservation_request(req) is False


def test_hair_salon_reservation_does_not_route_to_study_room_graph():
    req = _req("예약", "미용실 예약")

    assert is_study_room_reservation_request(req) is False


def test_non_reservation_category_does_not_route_to_study_room_graph():
    req = _req("가족", "스터디룸 예약")

    assert is_study_room_reservation_request(req) is False
