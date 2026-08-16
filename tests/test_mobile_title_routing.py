import pytest

from schemas.chat_models import ChatRequest
from services.flow.reservation.hair_salon.response import is_hair_salon_reservation_request
from services.flow.reservation.hospital.response import is_hospital_reservation_request
from services.flow.reservation.restaurant.response import is_restaurant_reservation_request
from services.flow.reservation.study_room.response import is_study_room_reservation_request
from services.flow.professor.appointment.response import is_professor_appointment_request
from services.flow.professor.assignment.response import is_professor_assignment_request
from services.flow.professor.absence.response import is_professor_absence_request


pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("title", "matcher"),
    [
        ("🍽 식당 예약", is_restaurant_reservation_request),
        ("🏥 병원 예약", is_hospital_reservation_request),
        ("💇 미용실 예약", is_hair_salon_reservation_request),
        ("📚 스터디룸 예약", is_study_room_reservation_request),
    ],
)
def test_mobile_reservation_titles_route_after_emoji_normalization(title, matcher):
    request = ChatRequest(
        category="예약",
        title=title,
        description="모바일 실제 제목",
        userMessage="예약하고 싶습니다.",
    )

    assert matcher(request) is True


@pytest.mark.parametrize(
    ("title", "matcher"),
    [
        ("👨‍🏫 면담 예약", is_professor_appointment_request),
        ("📝 과제 문의", is_professor_assignment_request),
        ("📚 결석 사유 전달", is_professor_absence_request),
    ],
)
def test_mobile_professor_titles_use_exact_registered_label(title, matcher):
    request = ChatRequest(
        category="교수님",
        title=title,
        description="모바일 실제 제목",
        userMessage="문의드리고 싶습니다.",
    )

    assert matcher(request) is True


def test_professor_title_does_not_route_by_partial_words():
    request = ChatRequest(
        category="교수님",
        title="면담 취소 후 다시 예약",
        description="등록되지 않은 제목",
        userMessage="문의드리고 싶습니다.",
    )

    assert is_professor_appointment_request(request) is False
