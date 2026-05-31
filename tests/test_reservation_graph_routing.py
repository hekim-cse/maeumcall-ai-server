from schemas.chat_models import ChatRequest
from services.flow.hospital_reservation_response import is_hospital_reservation_request


def make_request(title: str) -> ChatRequest:
    return ChatRequest(
        category="예약",
        title=title,
        description=f"{title} 전화 상황",
        userMessage="예약하고 싶습니다.",
    )


def test_hospital_reservation_routes_to_hospital_graph():
    req = make_request("병원 예약")

    assert is_hospital_reservation_request(req) is True


def test_restaurant_reservation_does_not_route_to_hospital_graph():
    req = make_request("식당 예약")

    assert is_hospital_reservation_request(req) is False


def test_study_room_reservation_does_not_route_to_hospital_graph():
    req = make_request("스터디룸 예약")

    assert is_hospital_reservation_request(req) is False


def test_hair_salon_reservation_does_not_route_to_hospital_graph():
    req = make_request("미용실 예약")

    assert is_hospital_reservation_request(req) is False
