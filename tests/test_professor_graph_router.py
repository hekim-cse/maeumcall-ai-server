from schemas.chat_models import ChatRequest
from services.flow.professor.router import complete_professor_graph_if_supported


def make_request(title: str, category: str = "교수님") -> ChatRequest:
    return ChatRequest(
        category=category,
        title=title,
        description="",
        userMessage="면담 예약하고 싶습니다.",
    )


def test_professor_graph_router_handles_appointment_booking():
    req = make_request("면담 예약")

    result = complete_professor_graph_if_supported(req)

    assert result is not None
    assert result.conversationState == "collecting_appointment_info"
    assert result.shouldEndCall is False
    assert "면담" in result.response or "예약" in result.response


def test_professor_graph_router_ignores_assignment_inquiry():
    req = make_request("과제 문의")

    result = complete_professor_graph_if_supported(req)

    assert result is None


def test_professor_graph_router_ignores_absence_notice():
    req = make_request("결석 사유 전달")

    result = complete_professor_graph_if_supported(req)

    assert result is None


def test_professor_graph_router_ignores_non_professor_category():
    req = make_request("면담 예약", category="예약")

    result = complete_professor_graph_if_supported(req)

    assert result is None
