import pytest

from services.flow.reservation.hair_salon.response_policy import (
    build_hair_salon_response,
)
from services.flow.reservation.study_room.response_policy import (
    build_study_room_response,
)


pytestmark = pytest.mark.unit


def test_hair_salon_policy_asks_only_for_missing_user_name():
    message = build_hair_salon_response(
        "collecting_reservation_info",
        {
            "date": "내일",
            "time": "오후 4시",
            "service_type": "커트",
            "designer": "수진",
            "user_name": None,
        },
    )

    assert "성함" in message
    assert "날짜" not in message


def test_study_room_policy_asks_only_for_missing_party_size():
    message = build_study_room_response(
        "collecting_reservation_info",
        {
            "date": "내일",
            "start_time": "오후 2시",
            "duration": "2시간",
            "party_size": None,
            "user_name": "김개굴",
        },
    )

    assert "인원" in message
    assert "이용 날짜" not in message
