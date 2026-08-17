import pytest

from schemas.chat_models import ChatRequest
from services.flow.professor.assignment.response import is_professor_assignment_request

pytestmark = pytest.mark.unit


def _req(category: str, title: str) -> ChatRequest:
    return ChatRequest(
        category=category,
        title=title,
        description="",
        userMessage="과제 제출 형식을 여쭤보고 싶습니다.",
    )


def test_professor_assignment_routes_to_professor_assignment_graph():
    req = _req("교수님", "과제 문의")

    assert is_professor_assignment_request(req) is True


def test_professor_appointment_does_not_route_to_assignment_graph():
    req = _req("교수님", "면담 예약")

    assert is_professor_assignment_request(req) is False


def test_professor_absence_does_not_route_to_assignment_graph():
    req = _req("교수님", "결석 사유 전달")

    assert is_professor_assignment_request(req) is False


def test_reservation_assignment_does_not_route_to_professor_assignment_graph():
    req = _req("예약", "과제 문의")

    assert is_professor_assignment_request(req) is False


def test_non_professor_category_does_not_route_to_assignment_graph():
    req = _req("회사", "과제 문의")

    assert is_professor_assignment_request(req) is False
